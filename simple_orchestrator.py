#!/usr/bin/env python3
# simple_orchestrator.py - Simplified orchestrator with UI-compatible output format

import json
import os
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def simple_orchestrate(items: List[str], city: str, vendors: List[str], method: str = "greedy") -> Dict[str, Any]:
    """
    Simplified orchestrator that returns UI-compatible format
    """
    logger.info(f"Starting orchestration for items: {items}")

    try:
        # Try to import and use the tools
        from lc_tools import PriceCheckerTool, OptimizerTool

        price_checker = PriceCheckerTool()
        optimizer = OptimizerTool()

        price_results = {}

        # Step 1: Get prices with timeout and error handling
        for item in items:
            logger.info(f"Checking prices for: {item}")

            query = json.dumps({
                "item": item,
                "location": city,
                "stores": vendors,
                "cache_ttl": 0  # Disable cache to force fresh lookup
            })

            try:
                result_str = price_checker._run(query)
                item_prices = json.loads(result_str)
                price_results[item] = item_prices
                logger.info(f"Got prices for {item}")

                # Check if we got any valid prices
                has_valid_price = any(
                    store_info.get('available') and store_info.get('price') is not None
                    for store_info in item_prices.values()
                )

                if not has_valid_price:
                    logger.warning(f"No valid prices found for {item}")

            except Exception as e:
                logger.error(f"Error getting prices for {item}: {e}")
                price_results[item] = {store: {"price": None, "available": False, "name": None} for store in vendors}

        logger.info(f"Final price_results collected")

        # Step 2: Optimize if we have any valid prices
        has_any_prices = any(
            any(store_info.get('available') and store_info.get('price') is not None
                for store_info in item_prices.values())
            for item_prices in price_results.values()
        )

        if not has_any_prices:
            logger.warning("No valid prices found for any items")
            # Return UI-compatible format even when no prices found
            return {
                "price_results": price_results,
                "assigned_cart": {},
                "total": 0,
                "unavailable": items,
                "summary": "No prices found - web scraping may have failed or items not available"
            }

        # Proceed with optimization
        opt_query = json.dumps({
            "price_results": price_results,
            "method": method,
            "delivery_fees": {}
        })

        result_str = optimizer._run(opt_query)
        optimized = json.loads(result_str)

        logger.info(f"Optimization completed")

        # Transform result to UI-compatible format
        assigned_cart = {}
        total = 0
        unavailable = []
        item_details = []

        for item, assignment in optimized.items():
            if assignment is None:
                unavailable.append(item)
            else:
                store, price = assignment
                if store not in assigned_cart:
                    assigned_cart[store] = []

                # Get item name from price results
                item_name = price_results.get(item, {}).get(store, {}).get('name') or item

                assigned_cart[store].append({
                    "item": item,
                    "name": item_name,
                    "price": price
                })
                item_details.append({
                    "item": item,
                    "name": item_name,
                    "store": store,
                    "price": price
                })
                total += price

        # Return UI-compatible format (same as AI agent)
        return {
            "price_results": price_results,  # UI expects this key
            "assigned_cart": assigned_cart,
            "total": round(total, 2),
            "unavailable": unavailable,
            "item_details": item_details,
            "summary": f"Found items across {len(assigned_cart)} stores. Total: ₹{total:.2f}",
            "optimization_method": method
        }

    except ImportError as e:
        logger.error(f"Import error: {e}")
        # Return UI-compatible error format
        return {
            "price_results": {},
            "assigned_cart": {},
            "total": 0,
            "unavailable": items,
            "summary": f"Import error: {e}"
        }
    except Exception as e:
        logger.exception(f"Orchestration failed: {e}")
        # Return UI-compatible error format
        return {
            "price_results": {},
            "assigned_cart": {},
            "total": 0,
            "unavailable": items,
            "summary": f"Orchestration failed: {e}"
        }

if __name__ == "__main__":
    # Test with sample data
    sample_items = ["milk", "bread"]
    sample_city = "Mumbai"
    sample_vendors = ["Blinkit"]

    print("=== Simple Orchestrator Test ===")
    result = simple_orchestrate(sample_items, sample_city, sample_vendors)
    print("\nResult:")
    print(json.dumps(result, indent=2))
