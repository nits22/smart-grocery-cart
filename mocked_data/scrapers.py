# scrapers.py
import random
import time

# Example store list
STORES = ["BigBasket", "Blinkit", "Zepto", "AmazonFresh"]

# Mock database of prices
SAMPLE_PRICES = {
    "milk 1l": {"BigBasket": 55, "Blinkit": 60, "Zepto": 58, "AmazonFresh": 62},
    "eggs 12": {"BigBasket": 120, "Blinkit": 125, "Zepto": 118, "AmazonFresh": 130},
    "rice 5kg": {"BigBasket": 420, "Blinkit": 450, "Zepto": 435, "AmazonFresh": 440},
    "atta 5kg": {"BigBasket": 400, "Blinkit": 410, "Zepto": 405, "AmazonFresh": 415},
}

def get_price(store, item_text):
    """Simulate a store lookup. Returns price or None if unavailable."""
    time.sleep(0.1)  # simulate latency
    item_key = item_text.lower().strip()
    if item_key in SAMPLE_PRICES:
        return SAMPLE_PRICES[item_key].get(store)
    # For missing items, return randomized price or None
    if random.random() < 0.2:
        return None
    return round(random.uniform(30, 500), 2)

def fetch_prices_for_list(items, stores=STORES):
    """Return dict: item -> {store: price}"""
    results = {}
    for it in items:
        row = {}
        for s in stores:
            p = get_price(s, it)
            row[s] = {"price": p, "available": p is not None}
        results[it] = row
    return results
