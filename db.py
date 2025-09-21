# db.py
from dotenv import load_dotenv
load_dotenv()
import os
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def save_run(user_id, items, results, assigned_cart=None, total=None):
    if not sb: return
    sb.table("run_history").insert({
        "user_id": user_id,
        "items": items,
        "results": results,
        "assigned_cart": assigned_cart,
        "total": total
    }).execute()

def cache_price(store, item_text, price, available=True):
    if not sb: return
    sb.table("price_cache").insert({
        "store": store,
        "item_text": item_text,
        "price": price,
        "available": available
    }).execute()

def save_price_cache(*args, **kwargs):
    """
    Flexible save_price_cache function that handles both parameter signatures:
    1. save_price_cache(store, item_text, price, available=True, meta=None)
    2. save_price_cache(item, store, price, available, meta, location)
    """
    if not sb:
        return

    try:
        # Handle positional arguments flexibly
        if len(args) >= 3:
            if len(args) == 6:
                # cache_utils.py signature: (item, store, price, available, meta, location)
                item_text, store, price, available, meta, location = args
            else:
                # scraper_real.py signature: (store, item_text, price, available=True, meta=None)
                store = args[0]
                item_text = args[1]
                price = args[2]
                available = args[3] if len(args) > 3 else kwargs.get('available', True)
                meta = args[4] if len(args) > 4 else kwargs.get('meta', None)
                location = kwargs.get('location', 'Mumbai')
        else:
            # Handle keyword arguments
            store = kwargs.get('store')
            item_text = kwargs.get('item_text') or kwargs.get('item')
            price = kwargs.get('price')
            available = kwargs.get('available', True)
            meta = kwargs.get('meta', {})
            location = kwargs.get('location', 'Mumbai')

        if not all([store, item_text, price is not None]):
            print(f"Warning: Missing required parameters for save_price_cache")
            return

        sb.table("price_cache").insert({
            "store": store,
            "item_text": item_text,
            "price": price,
            "available": available,
            "meta": meta or {},
            "location": location
        }).execute()

    except Exception as e:
        print(f"Warning: Could not save to price_cache: {e}")

# Also add alias for compatibility
save_price_cache_sync = save_price_cache
