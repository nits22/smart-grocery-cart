from playwright.sync_api import sync_playwright
import json
from typing import Dict, Any, Optional

# sensible defaults
DEFAULT_LAT = 28.7041
DEFAULT_LON = 77.1025

def call_blinkit_api(search_query: str = "milk", location_lat: Optional[float] = None, location_lon: Optional[float] = None) -> Dict[str, Any]:
    """
    Call Blinkit API using Playwright to bypass anti-bot protection.
    This version ensures lat/lon are numeric and encodes the search query safely.
    """
    # coerce lat/lon to numeric defaults
    try:
        lat_val = float(location_lat) if location_lat is not None else DEFAULT_LAT
        lon_val = float(location_lon) if location_lon is not None else DEFAULT_LON
    except Exception:
        lat_val, lon_val = DEFAULT_LAT, DEFAULT_LON

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ]
        )

        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
            extra_http_headers={"accept-language": "en-US,en;q=0.9"}
        )

        page = context.new_page()
        try:
            # initial navigation to set cookies/session
            page.goto("https://blinkit.com", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)

            # grant geolocation if possible (optional)
            try:
                context.grant_permissions(["geolocation"], origin="https://blinkit.com")
                context.set_geolocation({"latitude": lat_val, "longitude": lon_val})
            except Exception:
                pass

            # Use encodeURIComponent for the query inside the JS
            safe_query = json.dumps(search_query)  # safe Python -> JS string literal
            js = f"""
            (async () => {{
                try {{
                    const q = encodeURIComponent({safe_query});
                    const url = `https://blinkit.com/v1/layout/search?q=${{q}}&search_type=type_to_search`;
                    const response = await fetch(url, {{
                        method: 'POST',
                        headers: {{
                            'accept': '*/*',
                            'accept-language': 'en-US,en;q=0.9',
                            'access_token': 'null',
                            'app_client': 'consumer_web',
                            'app_version': '1010101010',
                            'content-type': 'application/json',
                            'origin': 'https://blinkit.com',
                            'referer': `https://blinkit.com/s/?q=${{q}}`,
                            'user-agent': navigator.userAgent,
                            // add lat/lon here if present as numbers
                            'lat': '{lat_val}',
                            'lon': '{lon_val}',
                        }},
                        body: JSON.stringify({{
                            "applied_filters": null,
                            "monet_assets": [{{"name":"ads_vertical_banner","processed":0,"total":0}}],
                            "postback_meta": {{
                                "processedGroupIds": [],
                                "pageMeta": {{"scrollMeta":[{{"entitiesCount":95}}]}}
                            }},
                            "previous_search_query": {safe_query},
                            "processed_rails": {{}},
                            "vertical_cards_processed": 12
                        }})
                    }});
                    if (!response.ok) {{
                        return {{ success:false, status:response.status, error: 'HTTP ' + response.status, text: await response.text() }};
                    }}
                    const data = await response.json();
                    return {{ success:true, status: response.status, data }};
                }} catch (err) {{
                    return {{ success:false, status:'eval_error', error: err.message }};
                }}
            }})();
            """
            api_response = page.evaluate(js)
            return api_response

        except Exception as e:
            return {"success": False, "error": f"Playwright error: {e}", "status": "playwright_error"}
        finally:
            try:
                context.close()
                browser.close()
            except Exception:
                pass


def extract_products_from_blinkit_response(api_response: Dict[str, Any]) -> list:
    """
    Extract product information from Blinkit API response
    """
    products = []

    if not api_response.get("success") or not api_response.get("data"):
        return products

    data = api_response["data"]

    # Look for products in various possible locations in the response
    product_containers = []

    # Common paths where products might be stored
    possible_paths = [
        data.get("entities", []),
        data.get("vertical_cards", []),
        data.get("products", []),
        data.get("items", []),
        data.get("results", [])
    ]

    for container in possible_paths:
        if isinstance(container, list) and container:
            product_containers.extend(container)

    # If no products found in standard locations, search recursively
    if not product_containers:
        def find_products_recursive(obj):
            found = []
            if isinstance(obj, dict):
                # Look for product-like objects
                if "name" in obj and ("price" in obj or "mrp" in obj):
                    found.append(obj)
                # Recurse into nested objects
                for value in obj.values():
                    found.extend(find_products_recursive(value))
            elif isinstance(obj, list):
                for item in obj:
                    found.extend(find_products_recursive(item))
            return found

        product_containers = find_products_recursive(data)

    # Extract product information
    for product in product_containers:
        if not isinstance(product, dict):
            continue

        # Extract name
        name = (product.get("name") or
                product.get("title") or
                product.get("display_name") or
                (product.get("item") or {}).get("name"))

        if not name:
            continue

        # Extract price - look in multiple possible locations
        price = None
        price_fields = ["price", "selling_price", "offer_price", "final_price", "mrp"]

        for field in price_fields:
            if field in product:
                price_val = product[field]
                if isinstance(price_val, dict):
                    # Sometimes price is nested like {"value": 50, "currency": "INR"}
                    price = price_val.get("value") or price_val.get("amount")
                else:
                    price = price_val
                if price is not None:
                    break

        # Try to convert price to float
        try:
            price = float(price) if price is not None else None
        except (ValueError, TypeError):
            price = None

        # Extract other details
        quantity = (product.get("quantity") or
                   product.get("pack_size") or
                   product.get("unit") or "")

        available = product.get("in_stock", True)  # Assume available if not specified

        products.append({
            "name": name,
            "price": price,
            "quantity": quantity,
            "available": available,
            "store": "Blinkit",
            "raw": product
        })

    return products


def search_blinkit_products(search_query: str, location_lat: float = 28.4652382, location_lon: float = 77.0615957) -> Dict[str, Any]:
    """
    Complete function to search Blinkit products and return structured results
    """
    # Call the API
    api_response = call_blinkit_api(search_query, location_lat, location_lon)

    # Extract products
    products = extract_products_from_blinkit_response(api_response)

    # Find best match for the search query
    best_match = None
    if products:
        # Simple scoring based on name similarity
        query_words = set(search_query.lower().split())
        best_score = 0

        for product in products:
            if not product.get("available") or product.get("price") is None:
                continue

            name_words = set(product["name"].lower().split())
            score = len(query_words.intersection(name_words))

            if query_words.issubset(name_words):
                score += 10  # Bonus for containing all query words

            if score > best_score:
                best_score = score
                best_match = product

    return {
        "success": api_response.get("success", False),
        "search_query": search_query,
        "total_products": len(products),
        "best_match": best_match,
        "all_products": products[:10],  # Return top 10
        "api_status": api_response.get("status"),
        "error": api_response.get("error")
    }


# Test the function
if __name__ == "__main__":
    print("Testing Blinkit API call...")

    # Test with milk
    result = search_blinkit_products("milk")
    print(f"\nSearch Results for 'milk':")
    print(f"Success: {result['success']}")
    print(f"Total products found: {result['total_products']}")

    if result['best_match']:
        best = result['best_match']
        print(f"\nBest match:")
        print(f"  Name: {best['name']}")
        print(f"  Price: ₹{best['price']}")
        print(f"  Available: {best['available']}")

    if result['error']:
        print(f"\nError: {result['error']}")

    # Show all products found
    print(f"\nAll products:")
    for i, product in enumerate(result['all_products'], 1):
        print(f"  {i}. {product['name']} - ₹{product['price']}")