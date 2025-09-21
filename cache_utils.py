# cache_utils.py
import os, time
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
sb = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def save_price_cache(item, store, price, available, meta, location):
    if not sb:
        return
    sb.table("price_cache").insert({
        "item_text": item,
        "store": store,
        "price": price,
        "available": available,
        "meta": meta,
        "location": location
    }).execute()
