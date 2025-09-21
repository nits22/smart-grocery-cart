# streamlit_app.py - Updated with real scraping
import streamlit as st
import pandas as pd
from scrapers_real import fetch_prices_for_list_real_sync
from optimizer import greedy_optimize, ilp_optimize
import json
import time

st.set_page_config(
    page_title="Smart Grocery Cart - Real Prices",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
        default=available_stores
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

# Main Content Area
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📝 Shopping List")

    # Predefined quick lists
    quick_lists = {
        "Basic Essentials": ["Milk 1L", "Bread", "Eggs 12", "Rice 5kg", "Oil 1L"],
        "Breakfast Items": ["Milk 1L", "Bread", "Butter", "Jam", "Cornflakes"],
        "Cooking Basics": ["Rice 5kg", "Dal 1kg", "Oil 1L", "Salt", "Sugar 1kg"],
        "Snacks & Beverages": ["Biscuits", "Tea", "Coffee", "Namkeen", "Cold Drink"]
    }

    selected_quick_list = st.selectbox("Quick Select:", ["Custom"] + list(quick_lists.keys()))

    if selected_quick_list != "Custom":
        default_items = "\n".join(quick_lists[selected_quick_list])
    else:
        default_items = "Milk 1L\nBread\nEggs 12 pieces\nRice 5kg\nOil 1L"

    shopping_list = st.text_area(
        "Enter your shopping items (one per line):",
        value=default_items,
        height=200,
        help="Enter each item on a new line. Be specific about quantities (e.g., 'Milk 1L', 'Rice 5kg')"
    )

    items = [item.strip() for item in shopping_list.splitlines() if item.strip()]

    if items:
        st.info(f"📊 **{len(items)} items** in your shopping list")

with col2:
    st.subheader("🎯 Quick Actions")

    if st.button("🔍 Compare Prices", type="primary", use_container_width=True):
        if not items:
            st.error("Please add items to your shopping list!")
        elif not selected_stores:
            st.error("Please select at least one store!")
        else:
            st.session_state['run_comparison'] = True

    if st.button("💾 Save Shopping List", use_container_width=True):
        if items:
            st.session_state['saved_items'] = items
            st.success("Shopping list saved!")

    if 'saved_items' in st.session_state:
        if st.button("📋 Load Saved List", use_container_width=True):
            st.session_state['load_saved'] = True
            st.rerun()

# Main Processing Section
if st.session_state.get('run_comparison', False):
    st.session_state['run_comparison'] = False

    # Progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()

    with st.spinner("🔄 Fetching real-time prices from selected stores..."):
        try:
            status_text.text("🌐 Connecting to store websites...")
            progress_bar.progress(10)

            # Fetch real prices
            start_time = time.time()
            price_results = fetch_prices_for_list_real_sync(items, selected_location, selected_stores)


            elapsed_time = time.time() - start_time

            progress_bar.progress(100)
            status_text.text(f"✅ Completed in {elapsed_time:.1f} seconds!")

            if price_results:
                # Store results in session state
                st.session_state['price_results'] = price_results
                st.session_state['comparison_done'] = True

                # Display results
                st.success(f"🎉 Successfully fetched prices from {len(selected_stores)} stores!")

            else:
                st.error("❌ No price data could be fetched. Please try again or check your internet connection.")

        except Exception as e:
            st.error(f"❌ Error occurred during price fetching: {str(e)}")
            st.info("💡 Try reducing the number of items or selecting fewer stores.")

# Display Results Section
if st.session_state.get('comparison_done', False) and 'price_results' in st.session_state:
    price_results = st.session_state['price_results']

    st.markdown("---")
    st.header("📊 Price Comparison Results")

    # Create comparison table
    comparison_data = []

    for item, stores_data in price_results.items():
        row = {"Product": item}

        for store in selected_stores:
            if store in stores_data and stores_data[store]["available"]:
                price = stores_data[store]["price"]
                row[f"{store} Price"] = f"₹{price:.2f}" if price else "N/A"
                row[f"{store} Status"] = "✅ Available"
            else:
                row[f"{store} Price"] = "❌ N/A"
                row[f"{store} Status"] = "❌ Out of Stock"

        comparison_data.append(row)

    if comparison_data:
        df_comparison = pd.DataFrame(comparison_data)
        st.dataframe(df_comparison, use_container_width=True, hide_index=True)

        # Optimization Section
        st.header("🎯 Optimized Shopping Cart")

        col1, col2 = st.columns(2)

        with col1:
            optimization_method = st.radio(
                "Choose optimization method:",
                ["Greedy (Fast)", "Linear Programming (Optimal)"],
                help="Greedy is faster, LP finds the mathematically optimal solution"
            )

        with col2:
            if st.button("🚀 Optimize Cart", type="primary"):
                st.session_state['optimize_cart'] = True

        # Perform optimization
        if st.session_state.get('optimize_cart', False):
            st.session_state['optimize_cart'] = False

            try:
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
                    if assignment and assignment[0]:  # Store assigned
                        store, price = assignment
                        cart_data.append({
                            "Product": item,
                            "Store": store,
                            "Price": f"₹{price:.2f}",
                            "Status": "✅ Added to Cart"
                        })
                        total_cost += price
                        used_stores.add(store)
                    else:
                        unavailable_items.append(item)
                        cart_data.append({
                            "Product": item,
                            "Store": "N/A",
                            "Price": "N/A",
                            "Status": "❌ Unavailable"
                        })

                # Display cart table
                df_cart = pd.DataFrame(cart_data)
                st.dataframe(df_cart, use_container_width=True, hide_index=True)

                # Cost summary
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Items in Cart", len([x for x in cart_data if x["Status"] == "✅ Added to Cart"]))

                with col2:
                    delivery_cost = 0
                    if include_delivery:
                        delivery_cost = sum(delivery_fees.get(store, 0) for store in used_stores)

                    total_with_delivery = total_cost + delivery_cost
                    st.metric("Total Cost", f"₹{total_with_delivery:.2f}",
                              f"Delivery: ₹{delivery_cost:.2f}" if include_delivery else "")

                with col3:
                    st.metric("Stores Used", len(used_stores))

                # Store distribution
                if used_stores:
                    st.subheader("🏪 Store Distribution")

                    store_breakdown = {}
                    for item, assignment in optimization_result.items():
                        if assignment and assignment[0]:
                            store = assignment[0]
                            store_breakdown[store] = store_breakdown.get(store, 0) + 1

                    for store, count in store_breakdown.items():
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(f"**{store}**: {count} items")
                        with col2:
                            if include_delivery:
                                st.write(f"Delivery: ₹{delivery_fees.get(store, 0)}")

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
                        "total_items": len(items),
                        "available_items": len(cart_data) - len(unavailable_items),
                        "total_cost": total_with_delivery,
                        "stores_used": list(used_stores),
                        "cart": cart_data
                    }

                    summary_json = json.dumps(summary, indent=2)
                    st.download_button(
                        "📋 Download Summary (JSON)",
                        summary_json,
                        "cart_summary.json",
                        "application/json"
                    )

            except Exception as e:
                st.error(f"Optimization failed: {str(e)}")
                st.info("Try using the Greedy method or check your item list.")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 1rem;'>
    <p>🛒 Smart Grocery Cart - Compare prices across Blinkit, Instamart & Zepto</p>
    <p style='font-size: 0.8rem;'>⚠️ Prices are scraped in real-time and may vary. Always verify on the actual store website.</p>
</div>
""", unsafe_allow_html=True)
