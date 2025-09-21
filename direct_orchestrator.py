#!/usr/bin/env python3
# direct_orchestrator.py - Direct approach without complex instructions

import json
import os
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv
load_dotenv()

from lc_tools import PriceCheckerTool, OptimizerTool

# Direct tool usage without agent
def direct_orchestrate(items: List[str], city: str, vendors: List[str], method: str = "greedy") -> Dict[str, Any]:
    """
    Direct orchestration without LangChain agent - calls tools directly
    """
    print(f"Starting direct orchestration for items: {items}")

    # Initialize tools
    price_tool = PriceCheckerTool()
    opt_tool = OptimizerTool()

    # Step 1: Get prices for each item
    price_results = {}
    for item in items:
        print(f"Checking prices for: {item}")
        query = {
            "item": item,
            "location": city,
            "stores": vendors,
            "cache_ttl": 600
        }
        try:
            result_str = price_tool._run(json.dumps(query))
            item_prices = json.loads(result_str)
            # Fix: PriceCheckerTool returns {store: {price, available, ...}}
            # but OptimizerTool expects {item: {store: {price, available, ...}}}
            price_results[item] = item_prices
            print(f"Prices for {item}: {item_prices}")
        except Exception as e:
            print(f"Error getting prices for {item}: {e}")
            price_results[item] = {}

    print(f"Final price_results structure: {price_results}")

    # Step 2: Optimize cart
    print("Optimizing cart...")
    opt_query = {
        "price_results": price_results,
        "method": method,
        "delivery_fees": {}
    }

    try:
        result_str = opt_tool._run(json.dumps(opt_query))
        optimized = json.loads(result_str)
        print(f"Optimization result: {optimized}")

        # Transform the optimizer result to a more useful format
        if isinstance(optimized, dict) and not optimized.get("error"):
            # greedy_optimize returns {item: (store, price)} or {item: None}
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

            return {
                "assigned_cart": assigned_cart,
                "total": round(total, 2),
                "unavailable": unavailable,
                "summary": f"Found items across {len(assigned_cart)} stores. Total: ₹{total:.2f}"
            }

        return optimized
    except Exception as e:
        print(f"Error optimizing cart: {e}")
        return {
            "error": f"Optimization failed: {e}",
            "assigned_cart": {},
            "total": 0,
            "unavailable": items,
            "summary": "Direct optimization failed"
        }

if __name__ == "__main__":
    sample_items = ["milk", "bread"]
    sample_city = "Mumbai"
    sample_vendors = ["Blinkit", "Swiggy Instamart"]

    result = direct_orchestrate(sample_items, sample_city, sample_vendors)
    print("\nDirect Orchestrator result:")
    print(json.dumps(result, indent=2))
