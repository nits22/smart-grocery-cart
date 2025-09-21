# streamlit_real_app_fixed.py - Only calls API when button is clicked
import streamlit as st
import pandas as pd
from scraper_real import fetch_prices_for_list_real_sync
from optimizer import greedy_optimize, ilp_optimize
import json
import time

st.set_page_config(
    page_title="Smart Grocery Cart - Real Prices",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state variables
if 'run_comparison' not in st.session_state:
    st.session_state.run_comparison = False
if 'comparison_done' not in st.session_state:
    st.session_state.comparison_done = False
if 'price_results' not in st.session_state:
    st.session_state.price_results = {}
if 'optimize_cart' not in st.session_state:
    st.session_state.optimize_cart = False

# Custom CSS for better UI
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1rem 0;
        color: #2E8B57;
    }
    .store-card {
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .price-comparison {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">🛒 Smart Grocery Cart - Real Time Price Comparison</h1>', unsafe_allow_html=True)

# Sidebar Configuration
with st.sidebar:
    st.header("🏙️ Location Settings")

    location_options = [
        "Mumbai", "Delhi", "Bangalore", "Hyderabad",
        "Chennai", "Kolkata", "Pune", "Gurgaon"
    ]
    selected_location = st.selectbox("Select Your City", location_options)

    area_pincode = st.text_input("Enter Area/Pincode", "400001")

    st.header("🏪 Store Selection")
    available_stores = ["Blinkit", "Instamart", "Zepto"]
    selected_stores = st.multiselect(
        "Choose stores to compare",
        available_stores,
        default=["Blinkit"]  # Start with just Blinkit
    )

    st.header("⚙️ Scraping Options")
    scraping_timeout = st.slider("Scraping timeout (seconds)", 30, 180, 90)
    max_products = st.slider("Max products per store", 5, 20, 10)

    st.header("💰 Optimization Settings")
    include_delivery = st.checkbox("Include delivery fees", value=True)

    if include_delivery:
        st.subheader("Delivery Fees")
        delivery_fees = {}
        for store in selected_stores:
            delivery_fees[store] = st.number_input(
                f"{store} delivery fee (₹)",
                min_value=0,
                max_value=100,
                value=30,
                step=5,
                key=f"delivery_{store}"
            )

    # Debug section
    st.header("🔧 Debug")
    debug_mode = st.checkbox("Show debug info", value=False)

# Main Content Area
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📝 Shopping List")

    # Predefined quick lists
    quick_lists = {
        "Test Items": ["milk", "bread"],  # Simple test
        "Basic Essentials": ["Milk 1L", "Bread", "Eggs 12", "Rice 5kg", "Oil 1L"],
        "Breakfast Items": ["Milk 1L", "Bread", "Butter", "Jam", "Cornflakes"],
        "Cooking Basics": ["Rice 5kg", "Dal 1kg", "Oil 1L", "Salt", "Sugar 1kg"],
        "Snacks & Beverages": ["Biscuits", "Tea", "Coffee", "Namkeen", "Cold Drink"]
    }

    selected_quick_list = st.selectbox("Quick Select:", ["Custom"] + list(quick_lists.keys()))

    if selected_quick_list != "Custom":
        default_items = "\n".join(quick_lists[selected_quick_list])
    else:
        default_items = "milk\nbread\neggs"  # Keep it simple

    shopping_list = st.text_area(
        "Enter your shopping items (one per line):",
        value=default_items,
        height=200,
        help="Enter each item on a new line. Start simple with 'milk', 'bread', 'eggs'"
    )

    items = [item.strip() for item in shopping_list.splitlines() if item.strip()]

    if items:
        st.info(f"📊 **{len(items)} items** in your shopping list")
        if len(items) > 5:
            st.warning("⚠️ Tip: Start with 2-3 items for faster testing")

with col2:
    st.subheader("🎯 Quick Actions")

    # Compare Prices Button - This should be the ONLY trigger
    compare_button_clicked = st.button(
        "🔍 Compare Prices",
        type="primary",
        use_container_width=True,
        disabled=not items or not selected_stores,
        help="Click to start price comparison"
    )

    # Set the flag when button is clicked
    if compare_button_clicked:
        st.session_state.run_comparison = True
        st.session_state.comparison_done = False  # Reset previous results
        st.session_state.price_results = {}

    if st.button("💾 Save Shopping List", use_container_width=True):
        if items:
            st.session_state['saved_items'] = items
            st.success("Shopping list saved!")

    if 'saved_items' in st.session_state:
        if st.button("📋 Load Saved List", use_container_width=True):
            st.rerun()

    # Clear results button
    if st.session_state.get('comparison_done', False):
        if st.button("🗑️ Clear Results", use_container_width=True):
            st.session_state.comparison_done = False
            st.session_state.price_results = {}
            st.session_state.run_comparison = False
            st.rerun()

# IMPORTANT: Only run API calls if the flag is set
if st.session_state.get('run_comparison', False):
    # Reset the flag immediately to prevent re-running
    st.session_state.run_comparison = False

    # Validation
    if not items:
        st.error("❌ Please add items to your shopping list!")
    elif not selected_stores:
        st.error("❌ Please select at least one store!")
    else:
        # Progress tracking
        progress_container = st.container()

        with progress_container:
            st.subheader("🔄 Fetching Real-Time Prices")
            progress_bar = st.progress(0, text="Initializing...")
            status_text = st.empty()

            if debug_mode:
                debug_container = st.expander("🔍 Debug Logs", expanded=True)

        try:
            status_text.info("🌐 Setting up browser and connecting...")
            progress_bar.progress(10, text="🚀 Starting Playwright browser...")

            start_time = time.time()

            with st.spinner(f"Scraping prices from {len(selected_stores)} stores for {len(items)} items..."):
                progress_bar.progress(30, text="🛒 Fetching product data...")

                # THIS IS THE ONLY PLACE WHERE API IS CALLED
                price_results = fetch_prices_for_list_real_sync(
                    items=items,
                    location=selected_location.lower(),
                    stores=selected_stores,
                    pincode=area_pincode if area_pincode else None,
                    timeout=scraping_timeout,
                    max_products=max_products,
                    parallelism=2  # Keep it conservative
                )

                progress_bar.progress(80, text="📊 Processing results...")

                # Immediately after price_results is available
                for item in price_results:
                    info = price_results[item].get("Blinkit", {})
                    # show top-level error if present
                    if info.get("error"):
                        st.warning(f"{item} — Blinkit error: {info.get('error')}")
                    # show any raw_text the adapter returned
                    meta = info.get("meta") or {}
                    # our new adapter puts raw_text under meta.get('raw_text') or meta itself might be the api response
                    raw_text = None
                    if isinstance(meta, dict):
                        raw_text = meta.get("raw_text") or meta.get("text") or meta.get("data") or None
                    elif isinstance(meta, str):
                        raw_text = meta
                    if raw_text:
                        st.markdown("**Raw response (first 2000 chars):**")
                        st.code(str(raw_text)[:2000])

            elapsed_time = time.time() - start_time
            progress_bar.progress(100, text="✅ Completed!")

            if debug_mode and 'debug_container' in locals():
                with debug_container:
                    st.write("**Raw API Results:**")
                    st.json(price_results)

            # Validate results
            if price_results and isinstance(price_results, dict) and price_results:
                # Store results in session state
                st.session_state.price_results = price_results
                st.session_state.comparison_done = True

                # Count successful results
                total_found = sum(
                    1 for item_data in price_results.values()
                    for store_data in item_data.values()
                    if store_data.get('price') is not None
                )

                status_text.success(f"🎉 Completed in {elapsed_time:.1f} seconds!")
                st.info(f"📈 Found {total_found} available products across {len(selected_stores)} stores")

            else:
                st.error("❌ No price data could be fetched. Please try again.")
                status_text.error("No valid results obtained")

        except Exception as e:
            progress_bar.progress(0, text="❌ Error occurred")
            st.error(f"❌ Error during price fetching: {str(e)}")
            status_text.error(f"Error: {str(e)}")

            if debug_mode:
                st.exception(e)

            st.info("""
            💡 **Troubleshooting Tips:**
            - Try with fewer items (just 'milk' and 'bread')
            - Use only Blinkit initially
            - Check your internet connection
            - Make sure blinkit_playwright_api.py is in the same folder
            """)

# Display Results Section - Only if we have completed results
if st.session_state.get('comparison_done', False) and st.session_state.get('price_results'):
    price_results = st.session_state.price_results

    st.markdown("---")
    st.header("📊 Price Comparison Results")

    if not isinstance(price_results, dict) or not price_results:
        st.error("Invalid price results format")
        st.stop()

    # Create comparison table
    comparison_data = []
    total_products_found = 0

    for item, stores_data in price_results.items():
        if not isinstance(stores_data, dict):
            continue

        row = {"Product": item}
        item_found_count = 0

        for store in selected_stores:
            if store in stores_data:
                store_data = stores_data[store]
                if store_data.get("price") is not None and store_data.get("available", True):
                    price = store_data["price"]
                    row[f"{store} Price"] = f"₹{price:.2f}"
                    row[f"{store} Status"] = "✅ Available"
                    if store_data.get("name"):
                        product_name = str(store_data["name"])
                        row[f"{store} Product"] = product_name[:40] + "..." if len(product_name) > 40 else product_name
                    item_found_count += 1
                    total_products_found += 1
                else:
                    row[f"{store} Price"] = "N/A"
                    row[f"{store} Status"] = "❌ Not available"
            else:
                row[f"{store} Price"] = "N/A"
                row[f"{store} Status"] = "❌ No Data"

        row["Found In"] = f"{item_found_count}/{len(selected_stores)} stores"
        comparison_data.append(row)

    if comparison_data:
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Items Searched", len(items))
        with col2:
            st.metric("Products Found", total_products_found)
        with col3:
            success_rate = (total_products_found / (len(items) * len(selected_stores))) * 100 if items and selected_stores else 0
            st.metric("Success Rate", f"{success_rate:.1f}%")

        # Display comparison table
        df_comparison = pd.DataFrame(comparison_data)
        st.dataframe(df_comparison, use_container_width=True, hide_index=True)

        # Optimization Section
        st.header("🎯 Optimized Shopping Cart")

        col1, col2 = st.columns(2)

        with col1:
            optimization_method = st.radio(
                "Choose optimization method:",
                ["Greedy (Fast)", "Linear Programming (Optimal)"],
                help="Greedy is faster and works well for most cases"
            )

        with col2:
            # Optimize button - another controlled action
            optimize_button_clicked = st.button("🚀 Optimize Cart", type="primary")
            if optimize_button_clicked:
                st.session_state.optimize_cart = True

        # Perform optimization only if button was clicked
        if st.session_state.get('optimize_cart', False):
            st.session_state.optimize_cart = False  # Reset flag

            try:
                with st.spinner("Optimizing your cart..."):
                    if optimization_method == "Greedy (Fast)":
                        optimization_result = greedy_optimize(
                            price_results,
                            delivery_fees=delivery_fees if include_delivery else None
                        )
                    else:
                        optimization_result = ilp_optimize(
                            price_results,
                            delivery_fees=delivery_fees if include_delivery else None
                        )

                # Display optimized results
                st.subheader("🛍️ Your Optimized Cart")

                cart_data = []
                total_cost = 0
                used_stores = set()
                unavailable_items = []

                for item, assignment in optimization_result.items():
                    if assignment and len(assignment) == 2 and assignment[0]:  # Valid assignment
                        store, price = assignment
                        cart_data.append({
                            "Product": item,
                            "Best Store": store,
                            "Price": f"₹{price:.2f}",
                            "Status": "✅ Added to Cart"
                        })
                        total_cost += float(price)
                        used_stores.add(store)
                    else:
                        unavailable_items.append(item)
                        cart_data.append({
                            "Product": item,
                            "Best Store": "None",
                            "Price": "N/A",
                            "Status": "❌ Unavailable"
                        })

                # Display cart table
                if cart_data:
                    df_cart = pd.DataFrame(cart_data)
                    st.dataframe(df_cart, use_container_width=True, hide_index=True)

                    # Cost summary
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        items_in_cart = len([x for x in cart_data if "✅" in x["Status"]])
                        st.metric("Items in Cart", items_in_cart)

                    with col2:
                        delivery_cost = 0
                        if include_delivery and used_stores:
                            delivery_cost = sum(delivery_fees.get(store, 0) for store in used_stores)

                        total_with_delivery = total_cost + delivery_cost
                        st.metric("Total Cost", f"₹{total_with_delivery:.2f}")

                        if include_delivery and delivery_cost > 0:
                            st.caption(f"Includes ₹{delivery_cost:.2f} delivery")

                    with col3:
                        st.metric("Stores Used", len(used_stores))

                    # Store distribution
                    if used_stores:
                        st.subheader("🏪 Store Distribution")

                        store_breakdown = {}
                        for item, assignment in optimization_result.items():
                            if assignment and len(assignment) == 2 and assignment[0]:
                                store = assignment[0]
                                store_breakdown[store] = store_breakdown.get(store, 0) + 1

                        for store, count in store_breakdown.items():
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.write(f"**{store}**: {count} items")
                            with col2:
                                if include_delivery:
                                    st.write(f"₹{delivery_fees.get(store, 0)} delivery")

                    # Unavailable items warning
                    if unavailable_items:
                        st.warning(f"⚠️ **{len(unavailable_items)} items unavailable**: {', '.join(unavailable_items)}")

                    # Export options
                    st.subheader("📤 Export Options")

                    col1, col2 = st.columns(2)

                    with col1:
                        # Download cart as CSV
                        csv = df_cart.to_csv(index=False)
                        st.download_button(
                            "📄 Download Cart (CSV)",
                            csv,
                            "smart_grocery_cart.csv",
                            "text/csv"
                        )

                    with col2:
                        # Generate shopping summary
                        summary = {
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "location": selected_location,
                            "total_items": len(items),
                            "available_items": items_in_cart,
                            "total_cost": total_with_delivery,
                            "delivery_cost": delivery_cost,
                            "stores_used": list(used_stores),
                            "unavailable_items": unavailable_items,
                            "cart_details": cart_data
                        }

                        summary_json = json.dumps(summary, indent=2)
                        st.download_button(
                            "📋 Download Summary (JSON)",
                            summary_json,
                            "cart_summary.json",
                            "application/json"
                        )

            except Exception as e:
                st.error(f"❌ Optimization failed: {str(e)}")
                if debug_mode:
                    st.exception(e)
                st.info("Try using the Greedy method or check your data.")

    else:
        st.warning("No valid comparison data available.")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 1rem;'>
    <p>🛒 Smart Grocery Cart - Compare prices across grocery delivery platforms</p>
    <p style='font-size: 0.8rem;'>⚠️ Prices are fetched in real-time and may vary. Always verify on the store website.</p>
    <p style='font-size: 0.7rem;'>Powered by Playwright for reliable web scraping</p>
</div>
""", unsafe_allow_html=True)
