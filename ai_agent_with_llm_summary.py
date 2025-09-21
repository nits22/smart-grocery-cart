#!/usr/bin/env python3
# ai_agent_with_llm_summary.py - AI Agent with LLM summarization for grocery cart optimization

import json
import os
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv
load_dotenv()

from agent_runner import create_agent
from lc_tools import PriceCheckerTool, OptimizerTool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GroceryCartAIAgent:
    """
    AI Agent that orchestrates grocery cart optimization and uses LLM to summarize results
    """

    def __init__(self):
        try:
            logger.info("🔧 Initializing GroceryCartAIAgent...")
            # Reset any cached agent to use new LLM priority (OpenAI first)
            from agent_runner import reset_agent
            reset_agent()

            # Use lazy initialization instead of creating agent immediately
            self.agent = None  # Will be created only when needed
            self.llm = None    # Will be created only when needed
        except Exception as e:
            logger.error(f"❌ Error creating LLM agent: {e}")
            self.agent = None
            self.llm = None

        self.price_checker = PriceCheckerTool()
        self.optimizer = OptimizerTool()

    def _get_agent_lazy(self):
        """Get agent using lazy initialization - only creates when first needed"""
        if self.agent is None:
            try:
                from agent_runner import get_agent
                logger.info("🔄 Attempting to get agent from agent_runner...")
                self.agent = get_agent()

                if self.agent and hasattr(self.agent, 'llm'):
                    self.llm = self.agent.llm
                    logger.info("✅ Agent and LLM successfully initialized")
                elif not self.llm:
                    # Try to get LLM directly if agent approach fails
                    try:
                        from agent_runner import build_hf_llm
                        logger.info("🔄 Attempting direct LLM creation...")
                        self.llm = build_hf_llm()
                        if self.llm:
                            logger.info("✅ Direct LLM created successfully")
                        else:
                            logger.warning("❌ Direct LLM creation returned None")
                    except Exception as e:
                        logger.warning(f"⚠️ Direct LLM creation failed: {e}")
                        self.llm = None

            except Exception as e:
                logger.error(f"❌ Failed to get agent: {e}")
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")
                self.agent = None
                self.llm = None

        return self.agent

    def find_optimal_cart(self, items: List[str], city: str, vendors: List[str], method: str = "greedy") -> Dict[str, Any]:
        """
        Find optimal grocery cart and generate LLM summary
        """
        logger.info(f"🤖 AI Agent processing {len(items)} items across {len(vendors)} stores")

        # Step 1: Get prices for all items
        logger.info("📊 Step 1: Gathering price data...")
        price_results = {}

        for item in items:
            query = json.dumps({
                "item": item,
                "location": city,
                "stores": vendors,
                "cache_ttl": 600
            })

            try:
                result_str = self.price_checker._run(query)
                item_prices = json.loads(result_str)
                price_results[item] = item_prices
                logger.info(f"✅ Got prices for {item}")
            except Exception as e:
                logger.error(f"❌ Failed to get prices for {item}: {e}")
                price_results[item] = {store: {"price": None, "available": False, "name": None} for store in vendors}

        # Step 2: Optimize cart
        logger.info("🎯 Step 2: Optimizing cart allocation...")
        opt_query = json.dumps({
            "price_results": price_results,
            "method": method,
            "delivery_fees": {}
        })

        try:
            result_str = self.optimizer._run(opt_query)
            optimized = json.loads(result_str)
            logger.info("✅ Cart optimization complete")
        except Exception as e:
            logger.error(f"❌ Optimization failed: {e}")
            optimized = {item: None for item in items}

        # Step 3: Transform to structured result
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

        # Step 4: Generate LLM summary
        logger.info("🧠 Step 4: Generating AI summary...")
        summary = self._generate_llm_summary(items, assigned_cart, total, unavailable, item_details, city, vendors)

        return {
            "assigned_cart": assigned_cart,
            "total": round(total, 2),
            "unavailable": unavailable,
            "item_details": item_details,
            "ai_summary": summary,
            "raw_price_data": price_results,
            "optimization_method": method
        }

    def _generate_llm_summary(self, items: List[str], assigned_cart: Dict, total: float,
                             unavailable: List[str], item_details: List[Dict],
                             city: str, vendors: List[str]) -> str:
        """
        Use LLM to generate intelligent summary of the cart optimization
        """
        # Only create LLM when actually needed for summary generation
        if self.llm is None:
            self._get_agent_lazy()  # This will initialize LLM only when needed

        # Add debugging output to console/logs
        logger.info(f"🔍 LLM Debug: LLM object type: {type(self.llm)}")
        logger.info(f"🔍 LLM Debug: LLM is None: {self.llm is None}")

        # Prepare data for LLM
        cart_data = {
            "requested_items": items,
            "city": city,
            "available_stores": vendors,
            "found_items": len(item_details),
            "total_stores_used": len(assigned_cart),
            "total_cost": total,
            "unavailable_items": unavailable,
            "store_breakdown": {}
        }

        # Add store breakdown
        for store, store_items in assigned_cart.items():
            store_total = sum(item["price"] for item in store_items)
            cart_data["store_breakdown"][store] = {
                "items": [f"{item['name']} (₹{item['price']})" for item in store_items],
                "item_count": len(store_items),
                "store_total": store_total
            }

        # Use the LLM directly instead of going through the agent
        if self.llm:
            logger.info("🧠 Attempting LLM summary generation...")
            logger.info(f"🔍 LLM Debug: LLM object: {self.llm}")

            # Create instruction for LLM
            instruction = f"""Analyze this grocery cart optimization result and provide a helpful summary:

SHOPPING REQUEST:
- Items requested: {', '.join(items)}
- Location: {city}
- Stores checked: {', '.join(vendors)}

OPTIMIZATION RESULT:
- Items found: {len(item_details)}/{len(items)}
- Total cost: ₹{total:.2f}
- Stores to visit: {len(assigned_cart)}
- Unavailable items: {', '.join(unavailable) if unavailable else 'None'}

STORE BREAKDOWN:
{json.dumps(cart_data['store_breakdown'], indent=2)}

Please provide a concise, helpful summary that includes:
1. How much money this saves compared to shopping at just one store
2. Practical shopping advice (which store to visit first, etc.)
3. Alternatives for unavailable items if any
4. Overall assessment of the deal

Keep the response under 150 words and make it actionable for the shopper."""

            try:
                logger.info("🔄 Invoking LLM directly...")
                logger.info(f"🔍 LLM Debug: Instruction length: {len(instruction)} chars")

                # Use LLM directly instead of agent
                response = self.llm.invoke(instruction)
                logger.info(f"🔍 LLM Debug: Raw response type: {type(response)}")

                # Handle different response formats
                if hasattr(response, 'content'):
                    summary = response.content
                elif isinstance(response, str):
                    summary = response
                else:
                    summary = str(response)

                logger.info(f"🔍 LLM Debug: Extracted summary: '{summary}'")
                logger.info(f"🔍 LLM Debug: Summary length: {len(summary.strip()) if summary else 0}")

                # Clean up the response
                if summary and len(summary.strip()) > 20:  # Ensure we got a meaningful response
                    # Remove any JSON or code formatting
                    summary = summary.replace("```", "").replace("json", "").strip()
                    logger.info("✅ LLM summary generated successfully")
                    return f"🤖 AI Analysis: {summary}"
                else:
                    logger.warning("⚠️ LLM returned empty or invalid response, using enhanced fallback")
                    logger.warning(f"🔍 LLM Debug: Fallback reason - summary empty or too short: '{summary}'")
                    return self._enhanced_fallback_summary(cart_data)

            except Exception as e:
                logger.error(f"⚠️ LLM summary generation failed: {e}")
                logger.error(f"🔍 LLM Debug: Exception type: {type(e).__name__}")
                import traceback
                logger.error(f"🔍 LLM Debug: Full traceback: {traceback.format_exc()}")
                return self._enhanced_fallback_summary(cart_data)
        else:
            logger.warning("🤖 No LLM available, using enhanced summary")
            logger.warning("🔍 LLM Debug: self.llm is None - check LLM initialization logs above")
            return self._enhanced_fallback_summary(cart_data)

    def _enhanced_fallback_summary(self, cart_data: Dict) -> str:
        """Enhanced fallback summary when LLM is unavailable"""
        total = cart_data["total_cost"]
        stores = cart_data["total_stores_used"]
        found = cart_data["found_items"]
        requested = len(cart_data["requested_items"])
        store_breakdown = cart_data["store_breakdown"]

        # Calculate savings estimate (assume single store would be 10-15% more expensive)
        estimated_savings = total * 0.12  # 12% estimated savings

        # Build enhanced summary
        summary = f"🛒 Smart Cart Summary: Found {found}/{requested} items across {stores} store{'s' if stores != 1 else ''}. "
        summary += f"Total cost: ₹{total:.2f}. "

        if stores > 1:
            summary += f"💰 Estimated savings: ~₹{estimated_savings:.0f} vs single-store shopping. "

            # Find store with most items for recommendation
            max_items = 0
            primary_store = None
            for store, info in store_breakdown.items():
                if info["item_count"] > max_items:
                    max_items = info["item_count"]
                    primary_store = store

            if primary_store:
                summary += f"🎯 Tip: Start at {primary_store} ({max_items} items), then visit others. "

        if cart_data["unavailable_items"]:
            summary += f"❌ Items not found: {', '.join(cart_data['unavailable_items'])}. "
            summary += "💡 Try checking BigBasket or local stores for missing items. "
        else:
            summary += "✅ All items found! "

        # Add practical advice
        if stores > 1:
            summary += "🚗 Consider delivery fees when deciding between stores."
        else:
            summary += "🎉 One-stop shopping - convenient and efficient!"

        return summary

# Main function for testing
def main():
    """Test the AI agent with sample data"""
    print("🤖 AI Agent with LLM Summary - Grocery Cart Optimizer")
    print("=" * 60)

    # Initialize agent
    agent = GroceryCartAIAgent()

    if not agent.agent:
        print("❌ LLM agent not available. Please check HUGGINGFACEHUB_API_TOKEN")
        return

    # Test cases
    test_cases = [
        {
            "items": ["milk", "bread", "eggs"],
            "city": "Mumbai",
            "vendors": ["Blinkit", "Swiggy Instamart"],
            "description": "Basic grocery essentials"
        },
        {
            "items": ["milk", "bread", "chicken", "rice"],
            "city": "Delhi",
            "vendors": ["Blinkit", "Swiggy Instamart"],
            "description": "Weekly grocery shopping"
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 Test Case {i}: {test_case['description']}")
        print(f"Items: {', '.join(test_case['items'])}")
        print(f"Location: {test_case['city']}")
        print(f"Stores: {', '.join(test_case['vendors'])}")
        print("-" * 40)

        try:
            result = agent.find_optimal_cart(
                items=test_case['items'],
                city=test_case['city'],
                vendors=test_case['vendors']
            )

            print("🎯 OPTIMIZATION RESULT:")
            print(f"💰 Total Cost: ₹{result['total']}")
            print(f"🏪 Stores to Visit: {len(result['assigned_cart'])}")

            print("\n📦 SHOPPING LIST:")
            for store, items in result['assigned_cart'].items():
                store_total = sum(item['price'] for item in items)
                print(f"  🏪 {store} (₹{store_total:.2f}):")
                for item in items:
                    print(f"    • {item['name']} - ₹{item['price']}")

            if result['unavailable']:
                print(f"\n❌ Unavailable: {', '.join(result['unavailable'])}")

            print(f"\n🧠 AI SUMMARY:")
            print(f"   {result['ai_summary']}")

        except Exception as e:
            print(f"❌ Test failed: {e}")

        print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
