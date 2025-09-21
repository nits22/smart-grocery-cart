# scrapers_real.py - Integrated with working Playwright APIs for both Blinkit and Instamart
import os
import time
import math
import re
from typing import List, Dict, Any, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import the working Playwright APIs
try:
    from blinkit_playwright_api import search_blinkit_products
    BLINKIT_AVAILABLE = True
except ImportError:
    BLINKIT_AVAILABLE = False
    search_blinkit_products = None
    print("Warning: blinkit_playwright_api not found. Blinkit scraping disabled.")

try:
    from instamart_playwright_api import search_instamart_products
    INSTAMART_AVAILABLE = True
except ImportError:
    INSTAMART_AVAILABLE = False
    search_instamart_products = None
    print("Warning: instamart_playwright_api not found. Instamart scraping disabled.")

PLAYWRIGHT_AVAILABLE = BLINKIT_AVAILABLE or INSTAMART_AVAILABLE

# Always import requests since it's used in both fallback and geocoding
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --------- Helpers ----------------------------------------------------------

def _safe_float(x) -> Optional[float]:
    if x is None: return None
    if isinstance(x, (int, float)): return float(x)
    s = str(x)
    s = re.sub(r"[^\d.\-]", "", s)
    try:
        return float(s)
    except Exception:
        return None

def _find_price_candidates(obj: Any, path: str = "") -> List[Tuple[str, float]]:
    candidates = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = k.lower()
            if kl in ("price", "mrp", "selling_price", "offer_price", "final_price", "amount", "value"):
                val = _safe_float(v)
                if val is not None:
                    candidates.append((f"{path}/{k}", val))
            if isinstance(v, (dict, list)):
                candidates += _find_price_candidates(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, el in enumerate(obj):
            candidates += _find_price_candidates(el, f"{path}[{i}]")
    return candidates

def _get_products_with_prices(json_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Heuristic discovery of products in Blinkit-like responses.
    Returns list of dicts: { 'name': str | None, 'min_price': float | None, 'prices': [..], 'raw': el }
    """
    products = []
    list_keys = ["entities", "items", "products", "vertical_cards", "results", "data", "payload"]
    for key in list_keys:
        node = json_data.get(key)
        if isinstance(node, list) and node:
            for el in node:
                if not isinstance(el, dict):
                    continue
                # find name
                name = el.get("name") or el.get("title") or el.get("display_name") or (el.get("item") or {}).get("name")
                prices = [p for (_, p) in _find_price_candidates(el)]
                min_price = min(prices) if prices else None
                products.append({"name": name, "prices": prices, "min_price": min_price, "raw": el})
            if products:
                return products

    # fallback: search any nested object for price candidates and names
    price_cands = _find_price_candidates(json_data)
    name_cands = []
    def _collect_names(o):
        if isinstance(o, dict):
            for k,v in o.items():
                if isinstance(v, str) and k.lower() in ("name","title","display_name","label","product_name"):
                    name_cands.append(v)
                _collect_names(v)
        elif isinstance(o, list):
            for el in o:
                _collect_names(el)
    _collect_names(json_data)
    if price_cands:
        _, p = min(price_cands, key=lambda x: x[1])
        name = name_cands[0] if name_cands else None
        products.append({"name": name, "prices":[p], "min_price": p, "raw": json_data})
    return products

# --------- HTTP session with retries (fallback only) ----------------------

def _create_session(retries: int = 3, backoff: float = 0.3, status_forcelist=(429, 500, 502, 503, 504)):
    if not PLAYWRIGHT_AVAILABLE:
        s = requests.Session()
        retry = Retry(total=retries, backoff_factor=backoff, status_forcelist=status_forcelist, allowed_methods=("GET","POST"))
        adapter = HTTPAdapter(max_retries=retry)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        return s
    return None

# --------- Geocoding helper -------------------------------------------------

def _geocode_location(location: str, pincode: Optional[str] = None, timeout: int = 8) -> Tuple[Optional[float], Optional[float]]:
    """
    Use Nominatim as a fallback to turn a city/pincode into lat/lon.
    For pincode (all digits), we query postalcode; otherwise we query the city name.
    """
    # Default coordinates for major cities (fallback if geocoding fails)
    default_coords = {
        "mumbai": (19.0760, 72.8777),
        "delhi": (28.7041, 77.1025),
        "bangalore": (12.9716, 77.5946),
        "hyderabad": (17.3850, 78.4867),
        "chennai": (13.0827, 80.2707),
        "kolkata": (22.5726, 88.3639),
        "pune": (18.5204, 73.8567),
        "gurgaon": (28.4595, 77.0266)
    }

    # Try geocoding first
    try:
        if PLAYWRIGHT_AVAILABLE:
            import requests
        headers = {"User-Agent": "smart-grocery-cart/1.0"}
        if pincode and re.fullmatch(r"\d{4,6}", str(pincode)):
            params = {"postalcode": pincode, "country": "India", "format": "json"}
        else:
            params = {"q": location, "country": "India", "format": "json", "limit": 1}
        resp = requests.get("https://nominatim.openstreetmap.org/search", params=params, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass

    # Fallback to default coordinates
    location_key = location.lower().strip()
    return default_coords.get(location_key, (28.7041, 77.1025))  # Default to Delhi

# --------- Blinkit search call with Playwright integration -----------------

def _blinkit_search_item_playwright(item_text: str, lat: Optional[float], lon: Optional[float],
                                   headers: Dict[str, str], timeout: int = 20, max_products: int = 5) -> Dict[str, Any]:
    """
    Simple direct call to your working Blinkit API
    """
    if not PLAYWRIGHT_AVAILABLE or not BLINKIT_AVAILABLE:
        return {"price": None, "available": False, "meta": None, "error": "Playwright API for Blinkit not available"}

    try:
        # Use default coordinates if not provided
        search_lat = 28.7041
        search_lon = 77.1025

        # Direct call to your working API - no processing, just pass through
        result = search_blinkit_products(search_query=item_text, location_lat=search_lat, location_lon=search_lon)


        # Simple passthrough - if your API works standalone, just use its results directly
        if result.get('success') and result.get('best_match'):
            best_match = result['best_match']
            return {
                "price": best_match.get('price'),
                "available": best_match.get('available', True),
                "name": best_match.get('name', ''),
                "quantity": best_match.get('quantity', ''),
                "meta": best_match,
                "error": None
            }
        else:
            # Return the exact error from your working API
            return {
                "price": None,
                "available": False,
                "meta": result,
                "error": result.get('error', 'No products found')
            }

    except Exception as e:
        return {"price": None, "available": False, "meta": None, "error": f"Integration error: {str(e)}"}

def _blinkit_search_item_fallback(session, item_text: str, lat: Optional[float], lon: Optional[float],
                                 headers: Dict[str, str], timeout: int = 20, max_products: int = 5) -> Dict[str, Any]:
    """
    Original requests-based method (fallback when Playwright not available)
    Call Blinkit /v1/layout/search and parse minimum price for the item_text.
    Returns: {"price": float|None, "available": bool, "meta": {...}, "error": str|None}
    """
    url = "https://blinkit.com/v1/layout/search"
    # Minimal payload - Blinkit's endpoint tolerates previous_search_query in many examples
    payload = {
        "applied_filters": None,
        "previous_search_query": item_text,
        "processed_rails": {},
        "postback_meta": {"pageMeta": {"scrollMeta": [{"entitiesCount": 0}]}}
    }
    # include lat/lon in headers if available (some Blinkit endpoints accept them as headers)
    if lat is not None:
        headers = dict(headers)
        headers.setdefault("lat", str(lat))
    if lon is not None:
        headers = dict(headers)
        headers.setdefault("lon", str(lon))

    try:
        r = session.post(url, json=payload, headers=headers, timeout=timeout)
    except Exception as e:
        return {"price": None, "available": False, "meta": None, "error": f"HTTP error: {e}"}

    # 403 handling
    if r.status_code == 403:
        sample = (r.text or "")[:400]
        return {"price": None, "available": False, "meta": sample, "error": "403 Forbidden - endpoint refused request (auth/csrf/cors/cookies may be required)"}

    if not r.ok:
        return {"price": None, "available": False, "meta": r.text[:400], "error": f"HTTP {r.status_code}"}

    # try parse JSON; handle non-JSON safely
    try:
        j = r.json()
    except ValueError:
        # server returned non-JSON (HTML error page or text) -> return snippet to help debug
        return {"price": None, "available": False, "meta": r.text[:1000], "error": "Invalid JSON response from Blinkit (unexpected content)"}

    # inspect response and find products/prices heuristically
    products = _get_products_with_prices(j)
    if not products:
        return {"price": None, "available": False, "meta": j, "error": "No product nodes found in response"}

    # match best candidate by name similarity + price
    q_low = item_text.lower().strip()
    scored = []
    for p in products:
        name = (p.get("name") or "").lower() if p.get("name") else ""
        score = 0
        if q_low and name:
            if q_low in name:
                score += 2
            q_tokens = set(q_low.split())
            name_tokens = set(name.split())
            score += len(q_tokens.intersection(name_tokens))
        price = p.get("min_price") if p.get("min_price") is not None else math.inf
        scored.append((score, price, p))

    # prefer high score, then low price
    scored.sort(key=lambda x: (-x[0], x[1]))
    best = scored[0][2]
    best_price = best.get("min_price")
    if best_price is None:
        return {"price": None, "available": False, "meta": best.get("raw"), "error": "No numeric price parsed for matched product"}
    # return best result
    return {"price": float(best_price), "available": True, "meta": best.get("raw"), "error": None}

# --------- Instamart search call with Playwright integration -----------------

def _instamart_search_item_playwright(item_text: str, lat: Optional[float], lon: Optional[float],
                                      headers: Dict[str, str], timeout: int = 20, max_products: int = 5) -> Dict[str, Any]:
    """
    Simple direct call to your working Instamart API
    """
    if not PLAYWRIGHT_AVAILABLE or not INSTAMART_AVAILABLE:
        return {"price": None, "available": False, "meta": None, "error": "Playwright API for Instamart not available"}

    try:
        # Use default coordinates if not provided
        search_lat = 28.7041
        search_lon = 77.1025

        # Direct call to your working API - no processing, just pass through
        result = search_instamart_products(search_query=item_text, location_lat=search_lat, location_lon=search_lon)


        # Simple passthrough - if your API works standalone, just use its results directly
        if result.get('success') and result.get('best_match'):
            best_match = result['best_match']
            return {
                "price": best_match.get('price'),
                "available": best_match.get('available', True),
                "name": best_match.get('name', ''),
                "quantity": best_match.get('quantity', ''),
                "meta": best_match,
                "error": None
            }
        else:
            # Return the exact error from your working API
            return {
                "price": None,
                "available": False,
                "meta": result,
                "error": result.get('error', 'No products found')
            }

    except Exception as e:
        return {"price": None, "available": False, "meta": None, "error": f"Integration error: {str(e)}"}

def _instamart_search_item_fallback(session, item_text: str, lat: Optional[float], lon: Optional[float],
                                    headers: Dict[str, str], timeout: int = 20, max_products: int = 5) -> Dict[str, Any]:
    """
    Original requests-based method (fallback when Playwright not available)
    Call Instamart /v1/layout/search and parse minimum price for the item_text.
    Returns: {"price": float|None, "available": bool, "meta": {...}, "error": str|None}
    """
    url = "https://instamart.com/v1/layout/search"
    # Minimal payload - Instamart's endpoint tolerates previous_search_query in many examples
    payload = {
        "applied_filters": None,
        "previous_search_query": item_text,
        "processed_rails": {},
        "postback_meta": {"pageMeta": {"scrollMeta": [{"entitiesCount": 0}]}}
    }
    # include lat/lon in headers if available (some Instamart endpoints accept them as headers)
    if lat is not None:
        headers = dict(headers)
        headers.setdefault("lat", str(lat))
    if lon is not None:
        headers = dict(headers)
        headers.setdefault("lon", str(lon))

    try:
        r = session.post(url, json=payload, headers=headers, timeout=timeout)
    except Exception as e:
        return {"price": None, "available": False, "meta": None, "error": f"HTTP error: {e}"}

    # 403 handling
    if r.status_code == 403:
        sample = (r.text or "")[:400]
        return {"price": None, "available": False, "meta": sample, "error": "403 Forbidden - endpoint refused request (auth/csrf/cors/cookies may be required)"}

    if not r.ok:
        return {"price": None, "available": False, "meta": r.text[:400], "error": f"HTTP {r.status_code}"}

    # try parse JSON; handle non-JSON safely
    try:
        j = r.json()
    except ValueError:
        # server returned non-JSON (HTML error page or text) -> return snippet to help debug
        return {"price": None, "available": False, "meta": r.text[:1000], "error": "Invalid JSON response from Instamart (unexpected content)"}

    # inspect response and find products/prices heuristically
    products = _get_products_with_prices(j)
    if not products:
        return {"price": None, "available": False, "meta": j, "error": "No product nodes found in response"}

    # match best candidate by name similarity + price
    q_low = item_text.lower().strip()
    scored = []
    for p in products:
        name = (p.get("name") or "").lower() if p.get("name") else ""
        score = 0
        if q_low and name:
            if q_low in name:
                score += 2
            q_tokens = set(q_low.split())
            name_tokens = set(name.split())
            score += len(q_tokens.intersection(name_tokens))
        price = p.get("min_price") if p.get("min_price") is not None else math.inf
        scored.append((score, price, p))

    # prefer high score, then low price
    scored.sort(key=lambda x: (-x[0], x[1]))
    best = scored[0][2]
    best_price = best.get("min_price")
    if best_price is None:
        return {"price": None, "available": False, "meta": best.get("raw"), "error": "No numeric price parsed for matched product"}
    # return best result
    return {"price": float(best_price), "available": True, "meta": best.get("raw"), "error": None}

# --------- Public function called by your UI -------------------------------

def fetch_prices_for_list_real_sync(items: List[str], location: str = "mumbai", stores: List[str] = None,
                                   pincode: Optional[str] = None, timeout: int = 60, max_products: int = 10,
                                   parallelism: int = 2) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    Fetch prices for a list of items from multiple stores.
    Fixed to prevent HTTP 400 errors by using sequential execution for Playwright.
    """
    if stores is None:
        stores = ["Blinkit"]

    print(f"🔍 Fetching prices for {len(items)} items from {len(stores)} stores...")

    if PLAYWRIGHT_AVAILABLE:
        print("✅ Using Playwright API (reliable method)")
    else:
        print("⚠️ Playwright not available, using fallback requests method")

    # ... existing code for coordinates ...
    lat, lon = _geocode_location(location, pincode)
    if lat is not None and lon is not None:
        print(f"📍 Using coordinates: {lat}, {lon} for location: {location}")
    else:
        print(f"⚠️ Could not get coordinates for {location}, using defaults")
        lat, lon = 28.7041, 77.1025  # Delhi defaults

    price_results = {}
    session = _create_session() if not PLAYWRIGHT_AVAILABLE else None
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    # FORCE SEQUENTIAL EXECUTION when using Playwright to prevent HTTP 400 errors
    if PLAYWRIGHT_AVAILABLE:
        print("🔄 Using sequential execution for reliability...")
        # Sequential execution to prevent browser instance conflicts
        for item in items:
            price_results[item] = {}
            print(f"  Searching for: {item}")

            for store in stores:
                if store.lower() == "blinkit":
                    try:
                        print(f"    🔍 Calling Playwright API for {item}...")
                        result = _blinkit_search_item_playwright(item, lat, lon, headers, timeout, max_products)
                        price_results[item][store] = result

                        # Enhanced logging
                        if result.get("price"):
                            print(f"    📊 API result: success=True, error=None")
                            print(f"    ✅ {store}: {result.get('name', item)} - ₹{result['price']}")
                        else:
                            print(f"    📊 API result: success=False, error={result.get('error')}")
                            print(f"    ❌ {store}: {result.get('error', 'Not found')}")

                    except Exception as e:
                        print(f"    ❌ {store}: Exception - {str(e)}")
                        price_results[item][store] = {
                            "price": None, "available": False, "meta": None,
                            "error": f"Exception: {e}"
                        }
                elif store.lower() == "instamart":
                    try:
                        print(f"    🔍 Calling Playwright API for {item}...")
                        result = _instamart_search_item_playwright(item, lat, lon, headers, timeout, max_products)
                        price_results[item][store] = result

                        # Enhanced logging
                        if result.get("price"):
                            print(f"    📊 API result: success=True, error=None")
                            print(f"    ✅ {store}: {result.get('name', item)} - ₹{result['price']}")
                        else:
                            print(f"    📊 API result: success=False, error={result.get('error')}")
                            print(f"    ❌ {store}: {result.get('error', 'Not found')}")

                    except Exception as e:
                        print(f"    ❌ {store}: Exception - {str(e)}")
                        price_results[item][store] = {
                            "price": None, "available": False, "meta": None,
                            "error": f"Exception: {e}"
                        }
                else:
                    # not implemented for other stores
                    price_results[item][store] = {
                        "price": None, "available": False, "meta": None,
                        "error": f"{store} scraping not implemented in this demo"
                    }

            # Small delay between items to be respectful and prevent rate limiting
            time.sleep(2.0)
    else:
        # Fallback method can still use parallel execution if needed
        if len(items) <= 5:
            # Sequential for small lists
            for item in items:
                price_results[item] = {}
                print(f"  Searching for: {item}")

                for store in stores:
                    if store.lower() == "blinkit":
                        try:
                            result = _blinkit_search_item_fallback(session, item, lat, lon, headers, timeout, max_products)
                            price_results[item][store] = result

                            if result.get("price"):
                                print(f"    ✅ {store}: ₹{result['price']}")
                            else:
                                print(f"    ❌ {store}: {result.get('error', 'Not found')}")

                        except Exception as e:
                            print(f"    ❌ {store}: Exception - {str(e)}")
                            price_results[item][store] = {
                                "price": None, "available": False, "meta": None,
                                "error": f"Exception: {e}"
                            }
                    elif store.lower() == "instamart":
                        try:
                            result = _instamart_search_item_fallback(session, item, lat, lon, headers, timeout, max_products)
                            price_results[item][store] = result

                            if result.get("price"):
                                print(f"    ✅ {store}: ₹{result['price']}")
                            else:
                                print(f"    ❌ {store}: {result.get('error', 'Not found')}")

                        except Exception as e:
                            print(f"    ❌ {store}: Exception - {str(e)}")
                            price_results[item][store] = {
                                "price": None, "available": False, "meta": None,
                                "error": f"Exception: {e}"
                            }
                    else:
                        price_results[item][store] = {
                            "price": None, "available": False, "meta": None,
                            "error": f"{store} scraping not implemented in this demo"
                        }

                time.sleep(1.5)
        else:
            # Parallel execution for larger lists (fallback method only)
            print(f"🚀 Using parallel execution with {parallelism} workers...")

            tasks = {}
            with ThreadPoolExecutor(max_workers=min(parallelism, len(items))) as ex:
                for item in items:
                    price_results[item] = {}
                    for store in stores:
                        if store.lower() == "blinkit":
                            fut = ex.submit(_blinkit_search_item_fallback, session, item, lat, lon, headers, int(timeout/len(items) if len(items) else timeout), max_products)
                            tasks[fut] = (item, store)
                        elif store.lower() == "instamart":
                            fut = ex.submit(_instamart_search_item_fallback, session, item, lat, lon, headers, int(timeout/len(items) if len(items) else timeout), max_products)
                            tasks[fut] = (item, store)
                        else:
                            price_results[item][store] = {"price": None, "available": False, "meta": None, "error": f"{store} scraping not implemented in this demo"}

                # collect
                for fut in as_completed(tasks):
                    item, store = tasks[fut]
                    try:
                        res = fut.result()
                        price_results[item][store] = res

                        if res.get("price"):
                            print(f"✅ {item} from {store}: ₹{res['price']}")
                        else:
                            print(f"❌ {item} from {store}: {res.get('error', 'Not found')}")

                    except Exception as e:
                        print(f"❌ {item} from {store}: Exception - {str(e)}")
                        res = {"price": None, "available": False, "meta": None, "error": f"Exception: {e}"}
                        price_results[item][store] = res

                    time.sleep(0.1)

    # Summary
    total_found = sum(
        1 for item_data in price_results.values()
        for store_data in item_data.values()
        if store_data.get("price") is not None
    )
    print(f"📊 Summary: Found prices for {total_found} items across all stores")

    if session:
        session.close()

    return price_results

# If run as script, quick smoke test (no secrets)
if __name__ == "__main__":
    print("🧪 Testing integrated scrapers_real with Playwright...")
    print("Smoke test (no auth key required):")
    result = fetch_prices_for_list_real_sync(["milk", "bread"], "Delhi", ["Blinkit"], pincode=None, timeout=30)

    print("\n📋 Results:")
    for item, stores in result.items():
        print(f"\n{item}:")
        for store, data in stores.items():
            if data.get('price'):
                print(f"  {store}: {data.get('name', 'Unknown')} - ₹{data['price']}")
            else:
                print(f"  {store}: {data.get('error', 'No data')}")
