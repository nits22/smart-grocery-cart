# scrapers_real.py  (debugging version - drop into your project)
import os
import time
import math
import re
import subprocess
import json
from typing import List, Dict, Any, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import pathlib


DEBUG_LOG_DIR = pathlib.Path("debug_logs")
DEBUG_LOG_DIR.mkdir(exist_ok=True)


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
    products = []
    list_keys = ["entities", "items", "products", "vertical_cards", "results", "data", "payload"]
    for key in list_keys:
        node = json_data.get(key)
        if isinstance(node, list) and node:
            for el in node:
                if not isinstance(el, dict):
                    continue
                name = el.get("name") or el.get("title") or el.get("display_name") or (el.get("item") or {}).get("name")
                prices = [p for (_, p) in _find_price_candidates(el)]
                min_price = min(prices) if prices else None
                products.append({"name": name, "prices": prices, "min_price": min_price, "raw": el})
            if products:
                return products
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


def _geocode_location(location: str, pincode: Optional[str] = None, timeout: int = 8) -> Tuple[Optional[float], Optional[float]]:
    try:
        headers = ["User-Agent: smart-grocery-cart/1.0"]
        if pincode and re.fullmatch(r"\d{4,6}", str(pincode)):
            params = f"postalcode={pincode}&country=India&format=json"
        else:
            params = f"q={location}&country=India&format=json&limit=1"

        # Use curl-impersonate for geocoding too
        cmd = [
            "curl_chrome130",  # or curl_chrome120, curl_firefox102, etc.
            f"https://nominatim.openstreetmap.org/search?{params}",
            "--timeout", str(timeout),
            "--silent",
            "--show-error"
        ]
        for header in headers:
            cmd.extend(["-H", header])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout+5)
        if result.returncode == 0 and result.stdout:
            data = json.loads(result.stdout)
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None, None


def _write_debug(item: str, status: int, headers: dict, snippet: str):
    fname = DEBUG_LOG_DIR / f"{re.sub(r'[^a-zA-Z0-9_-]', '_', item)[:40]}_blinkit_debug.txt"
    with fname.open("w", encoding="utf-8") as f:
        f.write(f"Status: {status}\n\n")
        f.write("Response headers:\n")
        for k,v in headers.items():
            f.write(f"{k}: {v}\n")
        f.write("\n\nResponse snippet:\n")
        f.write(snippet)


def _blinkit_search_item(item_text: str, lat: Optional[float], lon: Optional[float],
                         headers: Dict[str, str], timeout: int = 20, max_products: int = 5) -> Dict[str, Any]:
    url = "https://blinkit.com/v1/layout/search"
    payload = {
        "applied_filters": None,
        "previous_search_query": item_text,
        "processed_rails": {},
        "postback_meta": {"pageMeta": {"scrollMeta": [{"entitiesCount": 0}]}}
    }

    # Build curl-impersonate command
    cmd = [
        "curl_chrome130",  # Use Chrome 130 impersonation
        url,
        "-X", "POST",
        "--timeout", str(timeout),
        "--silent",
        "--show-error",
        "--write-out", "HTTP_CODE:%{http_code}",  # Get status code
        "--data", json.dumps(payload)
    ]

    # Add headers
    local_headers = dict(headers)
    if lat is not None:
        local_headers["lat"] = str(lat)
    if lon is not None:
        local_headers["lon"] = str(lon)

    for key, value in local_headers.items():
        cmd.extend(["-H", f"{key}: {value}"])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout+10)

        # Parse response
        if result.returncode != 0:
            error_msg = result.stderr or "curl command failed"
            return {"price": None, "available": False, "meta": None, "error": f"curl error: {error_msg}"}

        output = result.stdout

        # Extract status code and response body
        if "HTTP_CODE:" in output:
            parts = output.rsplit("HTTP_CODE:", 1)
            response_body = parts[0]
            status_code = int(parts[1].strip()) if parts[1].strip().isdigit() else 0
        else:
            response_body = output
            status_code = 200  # Assume OK if no status code

    except subprocess.TimeoutExpired:
        return {"price": None, "available": False, "meta": None, "error": "Request timeout"}
    except Exception as e:
        return {"price": None, "available": False, "meta": None, "error": f"curl execution error: {e}"}

    # Handle non-OK status codes
    if status_code == 403:
        snippet = response_body[:2000]
        _write_debug(item_text, status_code, {}, snippet)
        return {"price": None, "available": False, "meta": snippet, "error": "403 Forbidden - auth/cookies required (see debug log)"}

    if status_code >= 400:
        snippet = response_body[:2000]
        _write_debug(item_text, status_code, {}, snippet)
        return {"price": None, "available": False, "meta": snippet, "error": f"HTTP {status_code} - see debug log"}

    # Parse JSON response
    try:
        j = json.loads(response_body)
    except ValueError:
        snippet = response_body[:2000]
        _write_debug(item_text, status_code, {}, snippet)
        return {"price": None, "available": False, "meta": snippet, "error": "Invalid JSON response (see debug log)"}

    products = _get_products_with_prices(j)
    if not products:
        return {"price": None, "available": False, "meta": j, "error": "No product nodes found in JSON"}

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
    scored.sort(key=lambda x: (-x[0], x[1]))
    best = scored[0][2]
    best_price = best.get("min_price")
    if best_price is None:
        return {"price": None, "available": False, "meta": best.get("raw"), "error": "No numeric price parsed for matched product"}
    return {"price": float(best_price), "available": True, "meta": best.get("raw"), "error": None}


def fetch_prices_for_list_real_sync(items: List[str], location: str, stores: List[str],
                                    pincode: Optional[str] = None,
                                    timeout: int = 90, max_products: int = 10,
                                    parallelism: int = 3) -> Dict[str, Dict[str, Any]]:
    lat, lon = _geocode_location(location, pincode)
    if lat is None or lon is None:
        if pincode:
            lat, lon = _geocode_location("", pincode)

    headers = {
        "accept": "*/*",
        "app_client": "consumer_web",
        "content-type": "application/json",
        "user-agent": os.getenv("SMART_GROCERY_UA", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
    }
    auth = os.getenv("BLINKIT_AUTH_KEY")
    if auth:
        headers["auth_key"] = auth

    price_results: Dict[str, Dict[str, Any]] = {}
    tasks = {}
    with ThreadPoolExecutor(max_workers=parallelism) as ex:
        for item in items:
            price_results[item] = {}
            for store in stores:
                if store.lower() == "blinkit":
                    fut = ex.submit(_blinkit_search_item, item, lat, lon, headers, int(max(5, timeout//max(1,len(items)))), max_products)
                    tasks[fut] = (item, store)
                else:
                    price_results[item][store] = {"price": None, "available": False, "meta": None, "error": f"{store} not implemented"}
        for fut in as_completed(tasks):
            item, store = tasks[fut]
            try:
                res = fut.result()
            except Exception as e:
                res = {"price": None, "available": False, "meta": None, "error": f"Exception: {e}"}
            price_results[item][store] = res
            time.sleep(0.05)
    return price_results


if __name__ == "__main__":
    print("Debug smoke test with curl-impersonate")
    print(fetch_prices_for_list_real_sync(["milk 1l","eggs 12"], "Delhi", ["Blinkit"], pincode=None, timeout=20))
