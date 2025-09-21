# streamlit_app.py
import streamlit as st
from scrapers import fetch_prices_for_list, STORES
from optimizer import greedy_optimize, ilp_optimize
from db import save_run, cache_price
import os, json

st.set_page_config(page_title="Smart Grocery Cart", layout="centered")

st.title("Smart Grocery Cart 🛒")
st.markdown("Enter your grocery list (one item per line). The app will compare sample prices across stores and suggest the cheapest cart.")

# Input area
items_text = st.text_area("Grocery items (one per line)", value="milk 1l\neggs 12\nrice 5kg\natta 5kg", height=150)
items = [i.strip() for i in items_text.splitlines() if i.strip()]

stores = st.multiselect("Stores to compare", options=STORES, default=STORES)
algo = st.radio("Optimization method", ["Greedy (fast)", "ILP (exact)"])
include_delivery = st.checkbox("Include sample delivery fees", value=False)
if include_delivery:
    st.markdown("Delivery fees (sample)")
    default_fees = {s: 30 for s in stores}
    fees = {}
    cols = st.columns(len(stores))
    for idx, s in enumerate(stores):
        fees[s] = st.number_input(f"{s} fee", min_value=0, value=default_fees[s], key=f"fee_{s}")
else:
    fees = {s: 0 for s in stores}

if st.button("Find cheapest cart"):
    with st.spinner("Fetching prices..."):
        price_table = fetch_prices_for_list(items, stores)
        # Show price table
        import pandas as pd
        rows = []
        for it, d in price_table.items():
            row = {"item": it}
            for s in stores:
                info = d.get(s, {"price": None, "available": False})
                row[f"{s} price"] = info["price"]
            rows.append(row)
        st.write("### Price table")
        st.dataframe(pd.DataFrame(rows))

        st.write("### Optimizing...")
        if algo == "Greedy (fast)":
            assignment = greedy_optimize(price_table, delivery_fees=fees)
        else:
            assignment = ilp_optimize(price_table, delivery_fees=fees)

        total = 0
        used_stores = set()
        st.write("### Suggested combined cart")
        for it, v in assignment.items():
            if v is None:
                st.write(f"- {it} → *Unavailable in selected stores*")
            else:
                s, p = v
                st.write(f"- **{it}** → {s} @ ₹{p}")
                total += float(p)
                used_stores.add(s)
        # add delivery fees
        total += sum(fees.get(s,0) for s in used_stores)
        st.write(f"**Estimated total**: ₹{total:.2f} (including delivery fees for selected stores)")

        # Save to supabase (optional)
        if os.getenv("SUPABASE_URL"):
            st.write("Saving run to Supabase...")
            try:
                save_run(None, items, assignment)
                st.success("Saved.")
            except Exception as e:
                st.error(f"Could not save: {e}")
