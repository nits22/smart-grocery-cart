#!/usr/bin/env python3
# create_supabase_tables.py - Create missing Supabase tables

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

def create_orchestrations_table():
    """Create the orchestrations table in Supabase"""
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Supabase credentials not found in environment")
        return False
    
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Create orchestrations table SQL
        sql = """
        CREATE TABLE IF NOT EXISTS orchestrations (
            id SERIAL PRIMARY KEY,
            items JSONB NOT NULL,
            city TEXT NOT NULL,
            vendors JSONB NOT NULL,
            result JSONB NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        -- Also create price_cache table if it doesn't exist
        CREATE TABLE IF NOT EXISTS price_cache (
            id SERIAL PRIMARY KEY,
            item_text TEXT NOT NULL,
            store TEXT NOT NULL,
            price DECIMAL,
            available BOOLEAN DEFAULT TRUE,
            meta JSONB,
            location TEXT,
            scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        -- Create indexes for better performance
        CREATE INDEX IF NOT EXISTS idx_price_cache_item_store ON price_cache(item_text, store);
        CREATE INDEX IF NOT EXISTS idx_price_cache_scraped_at ON price_cache(scraped_at DESC);
        """
        
        # Execute the SQL using the rpc function
        result = supabase.rpc('exec_sql', {'sql': sql}).execute()
        
        print("✅ Successfully created Supabase tables")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create tables: {e}")
        print("Note: You may need to create these tables manually in your Supabase dashboard")
        return False

if __name__ == "__main__":
    print("Creating Supabase tables...")
    create_orchestrations_table()
