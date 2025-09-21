# lc_tools.py
from typing import List, Dict, Any, Optional
from langchain.tools import BaseTool
import json
from scraper_real import fetch_prices_for_list_real_sync
from optimizer import greedy_optimize, ilp_optimize

# db tools (synchronous wrappers)
from db_tools import DBReaderTool, DBWriterTool

# instantiate DB tools (they handle missing config internally)
_db_reader = DBReaderTool()
_db_writer = DBWriterTool()


class PriceCheckerTool(BaseTool):
    """
    Tool: price_checker
    Input JSON example:
      {
        "item": "milk 1l",
        "location": "Mumbai",
        "stores": ["Blinkit"],
        "cache_ttl": 600  # seconds, optional; set to 0 to disable cache
      }
    Output: JSON string mapping store -> { price, available, name, meta }
    """
    name: str = "price_checker"
    description: str = "Given an item, location and stores, returns JSON of prices for that item. Checks Supabase cache if configured."

    def _check_cache(self, item: str, store: str, cache_ttl: int) -> Optional[Dict[str, Any]]:
        """
        Query price_cache for recent rows for item+store.
        Returns the latest cached row as a dict or None.
        """
        if cache_ttl <= 0:
            return None

        try:
            q = {"table": "price_cache", "filters": {"item_text": item, "store": store}, "limit": 5}
            resp_str = _db_reader._run(json.dumps(q))
            resp = json.loads(resp_str)
            if not resp.get("success"):
                return None
            rows = resp.get("result", {}).get("data", []) or []
            if not rows:
                return None

            # rows are ordered by scraped_at desc by db_tools.select default; pick first
            candidate = rows[0]
            # If scraped_at is present we could check age; db_tools orders by scraped_at desc.
            # To keep things simple, assume the cached item is valid (caller passes cache_ttl to control),
            # but you can expand to parse scraped_at and compute age if desired.
            return candidate
        except Exception:
            return None

    def _save_cache(self, item: str, store: str, result: Dict[str, Any], location: str = None):
        try:
            record = {
                "item_text": item,
                "store": store,
                "price": result.get("price"),
                "available": bool(result.get("available")),
                "meta": result.get("meta") or {},
                "location": location or "",
            }
            payload = {"table": "price_cache", "record": record}
            _db_writer._run(json.dumps(payload))
        except Exception:
            # failure to save cache should not break main flow
            pass

    def _run(self, query: str) -> str:
        """
        query expected as JSON string: {"item":"milk 1l","location":"Mumbai","stores":["Blinkit"], "cache_ttl":600}
        Returns JSON string with price_results for the single item (store->info)
        """
        obj = json.loads(query)
        item = obj.get("item")
        if not item:
            return json.dumps({"error": "Missing 'item' in request"})

        location = obj.get("location", "mumbai")
        stores = obj.get("stores", ["Blinkit"])
        cache_ttl = int(obj.get("cache_ttl", 600))  # default 10 minutes
        # results container for this item
        results: Dict[str, Dict[str, Any]] = {}

        # 1) check cache per store
        for store in stores:
            cached = None
            try:
                cached = self._check_cache(item, store, cache_ttl)
            except Exception:
                cached = None

            if cached:
                # Normalize cached row fields
                results[store] = {
                    "price": cached.get("price"),
                    "available": cached.get("available", True),
                    "name": (cached.get("meta") or {}).get("name") or cached.get("meta", {}).get("display_name") or None,
                    "meta": cached.get("meta") or cached
                }
                # skip live fetch for this store
                continue

            # 2) if not cached, call the live fetcher for this single item/store
            try:
                # fetch_prices_for_list_real_sync accepts a list of items and list of stores.
                # call with single-item list and single-store list to limit work.
                fetched = fetch_prices_for_list_real_sync([item], location, [store], pincode=None, timeout=30, max_products=5, parallelism=1)
                # fetched is shaped { item: { store: { ... } } }
                store_info = (fetched.get(item) or {}).get(store) or {}
                # store_info may include price, available, name, meta
                results[store] = {
                    "price": store_info.get("price"),
                    "available": store_info.get("available", False),
                    "name": store_info.get("name"),
                    "meta": store_info.get("meta") or store_info
                }
                # save to cache (best-effort)
                try:
                    self._save_cache(item, store, results[store], location)
                except Exception:
                    pass
            except Exception as e:
                # if fetch fails, include error in meta
                results[store] = {"price": None, "available": False, "name": None, "meta": {"error": str(e)}}

        return json.dumps(results, default=str)

    async def _arun(self, query: str) -> str:
        return self._run(query)


class OptimizerTool(BaseTool):
    name: str = "optimizer"
    description: str = "Given full price_results JSON, return assigned cart JSON using greedy or ilp. Input: { 'price_results':..., 'method':'greedy', 'delivery_fees': {...}}"

    def _run(self, query: str) -> str:
        obj = json.loads(query)
        price_results = obj.get("price_results", {})
        method = obj.get("method", "greedy")
        fees = obj.get("delivery_fees", {})
        if method.lower().startswith("ilp"):
            assigned = ilp_optimize(price_results, delivery_fees=fees)
        else:
            assigned = greedy_optimize(price_results, delivery_fees=fees)
        return json.dumps(assigned, default=str)

    async def _arun(self, query: str) -> str:
        return self._run(query)
