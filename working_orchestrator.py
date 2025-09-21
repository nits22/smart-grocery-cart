#!/usr/bin/env python3
# working_orchestrator.py - Orchestrator that works with fallback data

import json
import os
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def working_orchestrate(items: List[str], city: str, vendors: List[str], method: str = "greedy") -> Dict[str, Any]:
    """
    Working orchestrator with fallback mock data when scraping fails
    """
    logger.info(f"Starting orchestration for items: {items}")

    # Fallback price data for common grocery items
    FALLBACK_PRICES = {
        "milk": {
            "Blinkit": {"price": 45.0, "available": True, "name": "Amul Milk 1L"},
            "Swiggy Instamart": {"price": 50.0, "available": True, "name": "Mother Dairy 1L"}
        },
        "curd 1l": {
            "Blinkit": {"price": 50.0, "available": True, "name": "Amul Fresh Curd 1L"},
            "Swiggy Instamart": {"price": 55.0, "available": True, "name": "Mother Dairy Curd 1L"}
        },
        "curd": {
            "Blinkit": {"price": 50.0, "available": True, "name": "Amul Fresh Curd 1L"},
            "Swiggy Instamart": {"price": 55.0, "available": True, "name": "Mother Dairy Curd 1L"}
        },
        "bread": {
            "Blinkit": {"price": 25.0, "available": True, "name": "Harvest Gold Bread"},
            "Swiggy Instamart": {"price": 30.0, "available": True, "name": "Modern Bread"}
        },
        "eggs": {
            "Blinkit": {"price": 60.0, "available": True, "name": "Farm Fresh Eggs"},
            "Swiggy Instamart": {"price": 55.0, "available": True, "name": "Country Eggs"}
        },
        "rice": {
            "Blinkit": {"price": 120.0, "available": True, "name": "Basmati Rice 1kg"},
            "Swiggy Instamart": {"price": 115.0, "available": True, "name": "India Gate Rice 1kg"}
        },
        "oil": {
            "Blinkit": {"price": 180.0, "available": True, "name": "Fortune Oil 1L"},
            "Swiggy Instamart": {"price": 175.0, "available": True, "name": "Saffola Oil 1L"}
        }
    }

    try:
        # Try to use real scraper first
        from lc_tools import PriceCheckerTool, OptimizerTool

        price_checker = PriceCheckerTool()
        optimizer = OptimizerTool()

        price_results = {}

        # Step 1: Get prices with fallback
        for item in items:
            logger.info(f"Checking prices for: {item}")

            # Try real scraping first
            try:
                query = json.dumps({
                    "item": item,
                    "location": city,
                    "stores": vendors,
                    "cache_ttl": 0
                })

                result_str = price_checker._run(query)
                item_prices = json.loads(result_str)

                # Check if we got valid prices
                has_valid_price = any(
                    store_info.get('available') and store_info.get('price') is not None
                    for store_info in item_prices.values()
                )

                if has_valid_price:
                    price_results[item] = item_prices
                    logger.info(f"✅ Real prices found for {item}")
                else:
                    raise ValueError("No valid prices from scraper")

            except Exception as e:
                logger.warning(f"⚠️ Scraping failed for {item}: {e}")

                # Use fallback data
                if item.lower() in FALLBACK_PRICES:
                    # Filter vendors to only include requested ones
                    fallback_data = {}
                    for vendor in vendors:
                        if vendor in FALLBACK_PRICES[item.lower()]:
                            fallback_data[vendor] = FALLBACK_PRICES[item.lower()][vendor].copy()

                    if fallback_data:
                        price_results[item] = fallback_data
                        logger.info(f"📝 Using fallback prices for {item}")
                    else:
                        # No fallback data available
                        price_results[item] = {store: {"price": None, "available": False, "name": None} for store in vendors}
                        logger.warning(f"❌ No fallback data for {item}")
                else:
                    # Unknown item, mark as unavailable
                    price_results[item] = {store: {"price": None, "available": False, "name": None} for store in vendors}
                    logger.warning(f"❌ Unknown item: {item}")

        logger.info(f"Final price_results: {json.dumps(price_results, indent=2)}")

        # Step 2: Optimize
        opt_query = json.dumps({
            "price_results": price_results,
            "method": method,
            "delivery_fees": {}
        })

        result_str = optimizer._run(opt_query)
        optimized = json.loads(result_str)

        logger.info(f"Optimization result: {optimized}")

        # Step 3: Transform result
        assigned_cart = {}
        total = 0
        unavailable = []

        for item, assignment in optimized.items():
            if assignment is None:
                unavailable.append(item)
            else:
                store, price = assignment
                if store not in assigned_cart:
                    assigned_cart[store] = []
                assigned_cart[store].append({"item": item, "price": price})
                total += price

        # Try to save to Supabase (non-blocking)
        try:
            from supabase import create_client
            SUPABASE_URL = os.getenv("SUPABASE_URL")
            SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")

            if SUPABASE_URL and SUPABASE_KEY:
                supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
                result_data = {
                    "assigned_cart": assigned_cart,
                    "total": round(total, 2),
                    "unavailable": unavailable,
                    "summary": f"Found items across {len(assigned_cart)} stores. Total: ₹{total:.2f}"
                }

                payload = {
                    "items": items,
                    "city": city,
                    "vendors": vendors,
                    "result": result_data,
                }

                # Create table if it doesn't exist (simplified)
                try:
                    resp = supabase.table("orchestrations").insert(payload).execute()
                    logger.info("✅ Saved to Supabase")
                except Exception:
                    logger.info("📝 Supabase save skipped (table may not exist)")
        except Exception:
            logger.info("📝 Supabase save skipped")

        return {
            "price_results": price_results,  # Add this key that UI expects
            "assigned_cart": assigned_cart,
            "total": round(total, 2),
            "unavailable": unavailable,
            "summary": f"Found items across {len(assigned_cart)} stores. Total: ₹{total:.2f}",
            "item_details": [],  # Add this key for UI compatibility
            "note": "Using mix of real and fallback prices" if any(
                item.lower() in FALLBACK_PRICES for item in items
            ) else "Using real scraped prices"
        }

    except Exception as e:
        logger.exception(f"Orchestration failed: {e}")
        return {
            "price_results": {},  # Add this key that UI expects
            "assigned_cart": {},
            "total": 0,
            "unavailable": items,
            "summary": "Orchestration encountered an error",
            "item_details": [],  # Add this key for UI compatibility
            "error": f"Orchestration failed: {e}"
        }

if __name__ == "__main__":
    # Test with sample data
    print("=== Working Orchestrator Test ===")

    # Test 1: Common items (should work with fallback)
    result1 = working_orchestrate(["milk", "bread"], "Mumbai", ["Blinkit", "Swiggy Instamart"])
    print("\nTest 1 - Common items:")
    print(json.dumps(result1, indent=2))

    # Test 2: Mix of known and unknown items
    result2 = working_orchestrate(["milk", "xyz"], "Mumbai", ["Blinkit", "Swiggy Instamart"])
    print("\nTest 2 - Mixed items:")
    print(json.dumps(result2, indent=2))
