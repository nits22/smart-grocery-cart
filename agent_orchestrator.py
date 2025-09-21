# agent_orchestrator.py
import json
import os
import logging
from typing import List, Dict, Any

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client  # if you use supabase to persist results
from agent_runner import create_agent, price_tool, opt_tool  # uses the runner's exports

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supabase init (expects SUPABASE_URL and SUPABASE_KEY in env)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        logger.warning("Could not initialize Supabase client: %s", e)

# Build or import an agent. Use create_agent() from agent_runner to keep config in one place.
_agent = create_agent()  # default HF LLM will be created inside create_agent()

def orchestrate(items: List[str], city: str, vendors: List[str], method: str = "min-price", delivery_fees: Dict[str, float] = None) -> Dict[str, Any]:
    """
    Top-level orchestrator: directly calls tools without complex agent instructions
    """
    if delivery_fees is None:
        delivery_fees = {}

    # Check if agent is available
    if _agent is None:
        logger.warning("Agent not available, using fallback orchestration...")
        # Don't return error format - use fallback instead
        try:
            from simple_orchestrator import simple_orchestrate
            return simple_orchestrate(items, city, vendors, "greedy")
        except Exception as e:
            # Return UI-compatible format even for errors
            return {
                "price_results": {},
                "assigned_cart": {},
                "total": 0,
                "unavailable": items,
                "summary": "Agent not available. Please check LLM configuration.",
                "item_details": []
            }

    # Instead of complex instructions, use direct tool calls
    logger.info("Starting direct tool orchestration...")

    try:
        # Step 1: Get prices for each item directly
        from lc_tools import PriceCheckerTool, OptimizerTool
        price_checker = PriceCheckerTool()
        optimizer = OptimizerTool()

        price_results = {}
        for item in items:
            query = json.dumps({
                "item": item,
                "location": city,
                "stores": vendors,
                "cache_ttl": 600
            })
            result_str = price_checker._run(query)
            item_prices = json.loads(result_str)
            # Fix: PriceCheckerTool returns {store: {price, available, ...}}
            # OptimizerTool expects {item: {store: {price, available, ...}}}
            price_results[item] = item_prices
            logger.info(f"Got prices for {item}: {item_prices}")

        logger.info(f"Final price_results structure: {price_results}")

        # Step 2: Optimize cart
        opt_query = json.dumps({
            "price_results": price_results,
            "method": method,
            "delivery_fees": delivery_fees
        })

        result_str = optimizer._run(opt_query)
        optimized = json.loads(result_str)
        logger.info(f"Optimization result: {optimized}")

        # Transform the optimizer result to UI-compatible format
        if isinstance(optimized, dict) and not optimized.get("error"):
            # greedy_optimize returns {item: (store, price)} or {item: None}
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

            # Return UI-compatible format (matches AI agent format)
            result = {
                "price_results": price_results,  # UI expects this key
                "assigned_cart": assigned_cart,
                "total": round(total, 2),
                "unavailable": unavailable,
                "item_details": item_details,
                "summary": f"Found items across {len(assigned_cart)} stores. Total: ₹{total:.2f}",
                "optimization_method": method
            }

            # Persist to supabase if configured
            if supabase:
                try:
                    payload = {
                        "items": items,
                        "city": city,
                        "vendors": vendors,
                        "result": result,
                    }
                    # Try to insert, but don't fail if table doesn't exist
                    resp = supabase.table("orchestrations").insert(payload).execute()
                    logger.info("Inserted orchestration into Supabase: %s", resp)
                except Exception as e:
                    logger.warning(f"Failed to insert orchestration into Supabase (table may not exist): {e}")
                    # Continue without failing

            return result

        # Return UI-compatible format even for optimizer errors
        return {
            "price_results": price_results,
            "assigned_cart": {},
            "total": 0,
            "unavailable": items,
            "summary": "Optimization failed",
            "item_details": []
        }

    except Exception as e:
        logger.exception(f"Direct orchestration failed: {e}")
        # Return UI-compatible format instead of error format
        return {
            "price_results": {},
            "assigned_cart": {},
            "total": 0,
            "unavailable": items,
            "summary": f"Orchestration failed: {e}",
            "item_details": []
        }
# Allow running this file directly for a quick smoke test
if __name__ == "__main__":
    # quick smoke test values - change as needed
    sample_items = ["milk", "bread"]
    sample_city = "Mumbai"
    sample_vendors = ["Blinkit", "Swiggy Instamart"]

    result = orchestrate(sample_items, sample_city, sample_vendors)
    print("Orchestrator result:")
    print(json.dumps(result, indent=2))
