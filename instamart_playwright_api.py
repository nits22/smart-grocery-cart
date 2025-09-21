from playwright.sync_api import sync_playwright
import json
from typing import Dict, Any, Optional

# Default location (Gurgaon coordinates from your curl)
DEFAULT_LAT = 28.4310129
DEFAULT_LON = 77.0601168
DEFAULT_STORE_ID = "1402609"
DEFAULT_PRIMARY_STORE_ID = "1402609"
DEFAULT_SECONDARY_STORE_ID = "1398454"

def call_instamart_api(search_query: str = "milk",
                      location_lat: Optional[float] = None,
                      location_lon: Optional[float] = None,
                      store_id: str = DEFAULT_STORE_ID) -> Dict[str, Any]:
    """
    Call Instamart (Swiggy) API using Playwright to bypass anti-bot protection.
    Based on the exact curl command provided for Instamart search.
    """
    # Use the exact coordinates from your working curl command
    lat_val = 28.43100375184627  # From your curl userLocation
    lon_val = 77.06019457429646  # From your curl userLocation

    # Use the exact store IDs from your curl command
    store_id = "1402609"
    primary_store_id = "1402609"
    secondary_store_id = "1398454"

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
            # Navigate to Swiggy Instamart first to establish session and cookies
            print(f"🌐 Navigating to Swiggy Instamart to establish session...")
            page.goto("https://www.swiggy.com/instamart", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)

            # Try to set location in the browser first
            try:
                print(f"📍 Setting location to {lat_val}, {lon_val}")
                context.grant_permissions(["geolocation"], origin="https://www.swiggy.com")
                context.set_geolocation({"latitude": lat_val, "longitude": lon_val})
                page.wait_for_timeout(2000)
            except Exception as e:
                print(f"⚠️ Could not set geolocation: {e}")

            # Navigate to a search page first to establish better session
            try:
                search_url = f"https://www.swiggy.com/stores/instamart/search?custom_back=true&query={search_query}"
                print(f"🔗 Navigating to search page: {search_url}")
                page.goto(search_url, wait_until="networkidle", timeout=20000)
                page.wait_for_timeout(2000)
            except Exception as e:
                print(f"⚠️ Could not navigate to search page: {e}")

            # Set essential cookies that might be needed (from your curl command)
            try:
                print(f"🍪 Setting location cookies...")
                page.context.add_cookies([
                    {
                        "name": "lat",
                        "value": f"s%3A{lat_val}.VHRw%2BP8XzYg%2BMH900XtRjjjRATsXw13H3UqVXAMvUZ8",
                        "domain": ".swiggy.com",
                        "path": "/"
                    },
                    {
                        "name": "lng",
                        "value": f"s%3A{lon_val}.ZkQBMduicVAJY5V1e%2BmGiJu0%2BHK2pZwQrxpHFI2bnwA",
                        "domain": ".swiggy.com",
                        "path": "/"
                    },
                    {
                        "name": "address",
                        "value": "s%3Afirst%20floor%2C%201568%2C%20Sector%2046%2C%20Huda%20Colony%2C%20Sector%20.JkOQdT2%2BT9x6BNPGiW9DpX72%2B%2BfET8X8CfZy0h74jnI",
                        "domain": ".swiggy.com",
                        "path": "/"
                    }
                ])
                page.wait_for_timeout(1000)
            except Exception as e:
                print(f"⚠️ Could not set cookies: {e}")

            # Prepare the API call using JavaScript with exact parameters from curl
            safe_query = json.dumps(search_query)
            js = f"""
            (async () => {{
                try {{
                    const searchQuery = {safe_query};
                    const url = 'https://www.swiggy.com/api/instamart/search/v2?offset=0&ageConsent=false&voiceSearchTrackingId=&storeId={store_id}&primaryStoreId={primary_store_id}&secondaryStoreId={secondary_store_id}';
                    
                    console.log('Making API call to:', url);
                    console.log('Search query:', searchQuery);
                    
                    const response = await fetch(url, {{
                        method: 'POST',
                        headers: {{
                            'accept': '*/*',
                            'accept-language': 'en-US,en;q=0.9',
                            'content-type': 'application/json',
                            'origin': 'https://www.swiggy.com',
                            'referer': `https://www.swiggy.com/stores/instamart/search?custom_back=true&query=${{encodeURIComponent(searchQuery)}}`,
                            'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
                            'sec-ch-ua-mobile': '?0',
                            'sec-ch-ua-platform': '"macOS"',
                            'sec-fetch-dest': 'empty',
                            'sec-fetch-mode': 'cors',
                            'sec-fetch-site': 'same-origin',
                            'user-agent': navigator.userAgent,
                            'x-build-version': '2.297.0'
                        }},
                        body: JSON.stringify({{
                            "facets": [],
                            "sortAttribute": "",
                            "query": searchQuery,
                            "search_results_offset": "0",
                            "page_type": "INSTAMART_AUTO_SUGGEST_PAGE",
                            "is_pre_search_tag": false
                        }})
                    }});
                    
                    console.log('Response status:', response.status);
                    
                    if (!response.ok) {{
                        const errorText = await response.text();
                        console.log('Error response:', errorText);
                        return {{ 
                            success: false, 
                            status: response.status, 
                            error: 'HTTP ' + response.status, 
                            text: errorText 
                        }};
                    }}
                    
                    const data = await response.json();
                    console.log('Response data keys:', Object.keys(data));
                    return {{ success: true, status: response.status, data }};
                    
                }} catch (err) {{
                    console.log('JavaScript error:', err);
                    return {{ success: false, status: 'eval_error', error: err.message }};
                }}
            }})();
            """

            print(f"🔄 Making API call for query: {search_query}")
            api_response = page.evaluate(js)
            print(f"📊 API response status: {api_response.get('status')}, success: {api_response.get('success')}")
            return api_response

        except Exception as e:
            print(f"❌ Playwright error: {e}")
            return {"success": False, "error": f"Playwright error: {e}", "status": "playwright_error"}
        finally:
            try:
                context.close()
                browser.close()
            except Exception:
                pass


def extract_products_from_instamart_response(api_response: Dict[str, Any]) -> list:
    """
    Extract product information from Instamart API response
    Updated to handle Swiggy's card-based response structure with correct nesting
    """
    products = []

    if not api_response.get("success") or not api_response.get("data"):
        print("❌ No success or data in API response")
        return products

    data = api_response["data"]

    # Fix: Instamart cards are nested in data['data']['cards'], not data['cards']
    if 'data' in data and isinstance(data['data'], dict):
        inner_data = data['data']
        cards = inner_data.get("cards", [])
    else:
        cards = data.get("cards", [])

    print(f"🔍 Searching through {len(cards)} cards for products...")

    for i, card_container in enumerate(cards):
        if not isinstance(card_container, dict):
            continue

        # Navigate through the nested card structure
        card = card_container.get("card", {})
        if isinstance(card, dict):
            inner_card = card.get("card", {})
            if isinstance(inner_card, dict):

                # Check card type to identify product cards
                card_type = inner_card.get("@type", "")
                print(f"  Card {i+1}: {card_type}")

                # Look for product grid widgets
                if "GridWidget" in card_type:
                    print(f"    🔍 Analyzing GridWidget structure...")

                    # Look for gridElements which contain products
                    grid_elements = inner_card.get("gridElements", {})
                    print(f"    gridElements type: {type(grid_elements)}")

                    if isinstance(grid_elements, dict):
                        print(f"    gridElements keys: {list(grid_elements.keys())}")

                        # Deep dive into infoWithStyle structure
                        info_with_style = grid_elements.get("infoWithStyle", {})
                        print(f"    infoWithStyle type: {type(info_with_style)}")

                        if isinstance(info_with_style, dict):
                            print(f"    infoWithStyle keys: {list(info_with_style.keys())}")

                            # Look for product arrays in all possible locations
                            for key, value in info_with_style.items():
                                print(f"      {key}: {type(value)}")

                                if isinstance(value, list) and len(value) > 0:
                                    print(f"        Found {len(value)} items in {key}")

                                    # Check if this is the 'items' array with products
                                    if key == 'items':
                                        print(f"        ✅ Processing {len(value)} products from items array")

                                        for item in value:
                                            if isinstance(item, dict):
                                                # Extract product name from displayName
                                                name = item.get('displayName')
                                                if name:
                                                    print(f"        📦 Product: {name}")

                                                    # Extract price from variations[0].price.mrp.units
                                                    price = None
                                                    variations = item.get('variations', [])

                                                    if isinstance(variations, list) and len(variations) > 0:
                                                        # Get the first variation
                                                        first_variation = variations[0]
                                                        if isinstance(first_variation, dict):
                                                            # Navigate to price.mrp.units
                                                            price_obj = first_variation.get('price', {})
                                                            if isinstance(price_obj, dict):
                                                                mrp_obj = price_obj.get('mrp', {})
                                                                if isinstance(mrp_obj, dict):
                                                                    price = mrp_obj.get('units')
                                                                    if price is not None:
                                                                        try:
                                                                            price = float(price)
                                                                            print(f"        💰 Price found at variations[0].price.mrp.units: ₹{price}")
                                                                        except (ValueError, TypeError):
                                                                            price = None

                                                            # Fallback: try other price locations if mrp.units not found
                                                            if price is None:
                                                                # Try direct price fields in variation
                                                                for price_field in ['price', 'finalPrice', 'mrp', 'sellingPrice']:
                                                                    if price_field in first_variation:
                                                                        try:
                                                                            price_val = first_variation[price_field]
                                                                            if isinstance(price_val, dict):
                                                                                price = price_val.get('units') or price_val.get('value')
                                                                            else:
                                                                                price = float(price_val)
                                                                            if price is not None:
                                                                                print(f"        💰 Fallback price found: ₹{price}")
                                                                                break
                                                                        except (ValueError, TypeError):
                                                                            pass

                                                    # Extract availability
                                                    available = item.get('inStock', True) and item.get('isAvail', True)

                                                    # Extract brand/quantity info
                                                    brand = item.get('brand', '')
                                                    quantity = brand  # Use brand as quantity info for now

                                                    # Only add product if we have a name (price can be None)
                                                    if name:
                                                        product_data = {
                                                            "name": name,
                                                            "price": price,
                                                            "quantity": quantity,
                                                            "available": available,
                                                            "store": "Instamart",
                                                            "raw": item
                                                        }
                                                        products.append(product_data)
                                                        print(f"        ✅ Added product: {name} - ₹{price}")

                                elif isinstance(value, dict):
                                    # Check if this dict contains an 'items' array
                                    if 'items' in value:
                                        items_array = value['items']
                                        if isinstance(items_array, list) and len(items_array) > 0:
                                            print(f"        Found items array in {key} with {len(items_array)} products")

                                            for item in items_array:
                                                if isinstance(item, dict):
                                                    # Extract product name from displayName
                                                    name = item.get('displayName')
                                                    if name:
                                                        print(f"        📦 Product: {name}")

                                                        # Extract price from variations[0].price.mrp.units
                                                        price = None
                                                        variations = item.get('variations', [])

                                                        if isinstance(variations, list) and len(variations) > 0:
                                                            first_variation = variations[0]
                                                            if isinstance(first_variation, dict):
                                                                # Navigate to price.mrp.units
                                                                price_obj = first_variation.get('price', {})
                                                                if isinstance(price_obj, dict):
                                                                    mrp_obj = price_obj.get('mrp', {})
                                                                    if isinstance(mrp_obj, dict):
                                                                        price = mrp_obj.get('units')
                                                                        if price is not None:
                                                                            try:
                                                                                price = float(price)
                                                                                print(f"        💰 Price found: ₹{price}")
                                                                            except (ValueError, TypeError):
                                                                                price = None

                                                        # Extract availability
                                                        available = item.get('inStock', True) and item.get('isAvail', True)

                                                        # Extract brand/quantity info
                                                        brand = item.get('brand', '')
                                                        quantity = brand

                                                        if name:
                                                            product_data = {
                                                                "name": name,
                                                                "price": price,
                                                                "quantity": quantity,
                                                                "available": available,
                                                                "store": "Instamart",
                                                                "raw": item
                                                            }
                                                            products.append(product_data)
                                                            print(f"        ✅ Added product: {name} - ₹{price}")

                                    # Keep existing debug logic for non-items structures
                                    else:
                                        print(f"        {key} is dict with keys: {list(value.keys())}")

                                        for nested_key, nested_value in value.items():
                                            if isinstance(nested_value, list) and len(nested_value) > 0:
                                                print(f"          {nested_key}: {len(nested_value)} items")

                                                # Check if these are products
                                                if isinstance(nested_value[0], dict):
                                                    first_nested = nested_value[0]
                                                    print(f"          First nested item keys: {list(first_nested.keys())}")

                                                    # Look for product patterns in nested items
                                                    if any(pk in first_nested for pk in ['name', 'title', 'productName', 'info', 'displayName']):
                                                        print(f"          ✅ Product-like structure found in {nested_key}")

                                                        # Try to extract product data
                                                        for item in nested_value[:3]:  # Check first 3 items
                                                            if isinstance(item, dict):
                                                                item_name = item.get('displayName') or item.get('name') or item.get('title')
                                                                if item_name:
                                                                    print(f"          Product found: {item_name}")

                                                                    # Extract price using the correct path
                                                                    item_price = None
                                                                    variations = item.get('variations', [])
                                                                    if isinstance(variations, list) and len(variations) > 0:
                                                                        first_var = variations[0]
                                                                        if isinstance(first_var, dict):
                                                                            price_obj = first_var.get('price', {})
                                                                            if isinstance(price_obj, dict):
                                                                                mrp_obj = price_obj.get('mrp', {})
                                                                                if isinstance(mrp_obj, dict):
                                                                                    item_price = mrp_obj.get('units')
                                                                                    try:
                                                                                        item_price = float(item_price)
                                                                                    except (ValueError, TypeError):
                                                                                        item_price = None

                                                                    if item_name:
                                                                        products.append({
                                                                            "name": item_name,
                                                                            "price": item_price,
                                                                            "quantity": item.get("brand", ""),
                                                                            "available": item.get("inStock", True) and item.get("isAvail", True),
                                                                            "store": "Instamart",
                                                                            "raw": item
                                                                        })
    print(f"📊 Total products extracted: {len(products)}")
    return products


def search_instamart_products(search_query: str,
                            location_lat: float = DEFAULT_LAT,
                            location_lon: float = DEFAULT_LON,
                            store_id: str = DEFAULT_STORE_ID) -> Dict[str, Any]:
    """
    Complete function to search Instamart products and return structured results
    """
    # Call the API
    api_response = call_instamart_api(search_query, location_lat, location_lon, store_id)

    # Extract products
    products = extract_products_from_instamart_response(api_response)

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
    print("Testing Instamart API call...")

    # Test with milk
    result = search_instamart_products("milk")
    print(f"\nSearch Results for 'milk':")
    print(f"Success: {result['success']}")
    print(f"Total products found: {result['total_products']}")

    if result['best_match']:
        best = result['best_match']
        print(f"\nBest match:")
        print(f"  Name: {best['name']}")
        print(f"  Price: ₹{best['price']}")
        print(f"  Quantity: {best['quantity']}")
        print(f"  Available: {best['available']}")

    if result['error']:
        print(f"\nError: {result['error']}")

    # Show all products found
    print(f"\nAll products:")
    for i, product in enumerate(result['all_products'], 1):
        print(f"  {i}. {product['name']} - ₹{product['price']} ({product['quantity']})")

    # Test with another query
    print("\n" + "="*60)
    result2 = search_instamart_products("bread")
    print(f"\nSearch Results for 'bread':")
    print(f"Success: {result2['success']}")
    print(f"Total products found: {result2['total_products']}")

    if result2['best_match']:
        best = result2['best_match']
        print(f"Best match: {best['name']} - ₹{best['price']}")
    else:
        print("No best match found for bread")
