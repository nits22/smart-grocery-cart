# db_tools.py
import os
import json
from typing import Any, Dict, Optional
from langchain.tools import BaseTool
from supabase import create_client, Client

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Initialize Supabase client (safe: will be None if not configured)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
sb: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        sb = None
        print(f"Warning: could not initialize Supabase client: {e}")

# Helper low-level functions (used by tools and also safe to import elsewhere)
def supabase_insert(table: str, row: Dict[str, Any]) -> Dict[str, Any]:
    if not sb:
        raise RuntimeError("Supabase client not configured (SUPABASE_URL / SUPABASE_KEY missing).")
    res = sb.table(table).insert(row).execute()
    # Supabase python client returns dict-like object; normalize result
    return {"status_code": getattr(res, "status_code", None), "data": res.data if hasattr(res, "data") else res}

def supabase_select(table: str, filters: Optional[Dict[str, Any]] = None, limit: int = 50, order_desc: bool = True):
    if not sb:
        raise RuntimeError("Supabase client not configured (SUPABASE_URL / SUPABASE_KEY missing).")
    q = sb.table(table).select("*")
    if filters:
        # apply simple equality filters: {"item_text": "milk", "store": "Blinkit"}
        for k, v in filters.items():
            q = q.eq(k, v)
    if order_desc:
        q = q.order("scraped_at", desc=True)
    if limit:
        q = q.limit(limit)
    res = q.execute()
    return {"status_code": getattr(res, "status_code", None), "data": res.data if hasattr(res, "data") else res}

# -------------------------
# DBWriterTool
# -------------------------
class DBWriterTool(BaseTool):
    name: str = "db_writer"
    description: str = (
        "Writes a single record to a specified Supabase table. "
        "Input: JSON string with keys: table (str), record (dict). "
        "Example: {\"table\":\"price_cache\",\"record\": {\"item_text\":\"milk\",\"store\":\"Blinkit\",\"price\":49.0}}"
    )

    def _run(self, query: str) -> str:
        try:
            payload = json.loads(query) if isinstance(query, str) else query
        except Exception as e:
            return json.dumps({"success": False, "error": f"Invalid JSON input: {e}"})

        table = payload.get("table")
        record = payload.get("record")
        if not table or not isinstance(record, dict):
            return json.dumps({"success": False, "error": "Missing 'table' or 'record' (dict) in input"})

        try:
            res = supabase_insert(table, record)
            return json.dumps({"success": True, "result": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    async def _arun(self, query: str) -> str:
        # synchronous implementation is fine for now; keep async wrapper
        return self._run(query)

# -------------------------
# DBReaderTool
# -------------------------
class DBReaderTool(BaseTool):
    name: str = "db_reader"
    description: str = (
        "Reads recent rows from a Supabase table with optional simple equality filters. "
        "Input: JSON string {\"table\":\"price_cache\",\"filters\":{\"item_text\":\"milk\"},\"limit\":10}. "
        "Returns JSON array of rows."
    )

    def _run(self, query: str) -> str:
        try:
            payload = json.loads(query) if isinstance(query, str) else query
        except Exception as e:
            return json.dumps({"success": False, "error": f"Invalid JSON input: {e}"})

        table = payload.get("table")
        filters = payload.get("filters", None)
        limit = int(payload.get("limit", 50))
        if not table:
            return json.dumps({"success": False, "error": "Missing 'table' in input"})

        try:
            res = supabase_select(table, filters=filters, limit=limit)
            return json.dumps({"success": True, "result": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    async def _arun(self, query: str) -> str:
        return self._run(query)
