# agent_core.py
from typing import Dict, Any, List, Tuple
import time

def get_min_price_for_item(price_row: Dict[str, Any]) -> Tuple[str, float]:
    """
    price_row: {"Blinkit": {"price":49,...}, "Zepto": {...}, ...}
    returns (store, price) for minimum available price, else (None, None)
    """
    best_store = None
    best_price = None
    for store, info in price_row.items():
        if info.get("available") and info.get("price") is not None:
            p = float(info["price"])
            if best_price is None or p < best_price:
                best_price = p
                best_store = store
    return best_store, best_price

def summarize_price_results(price_results: Dict[str, Dict[str, Any]]):
    rows = []
    for item, store_map in price_results.items():
        store, price = get_min_price_for_item(store_map)
        rows.append({"item": item, "best_store": store, "best_price": price})
    return rows

# wrapper to call optimizer already present in repo
def optimize_cart(price_results, method="greedy", delivery_fees=None):
    from optimizer import greedy_optimize, ilp_optimize
    if method == "greedy":
        return greedy_optimize(price_results, delivery_fees=delivery_fees or {})
    else:
        return ilp_optimize(price_results, delivery_fees=delivery_fees or {})
