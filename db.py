# db.py
import os
from supabase import create_client
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def save_run(user_id, input_list, result):
    data = {
        "user_id": user_id,
        "input_list": input_list,
        "result": result
    }
    resp = supabase.table("runs").insert(data).execute()
    return resp

def cache_price(store, item_text, price, available=True):
    supabase.table("price_cache").insert({
        "store": store,
        "item_text": item_text,
        "price": price,
        "available": available
    }).execute()
