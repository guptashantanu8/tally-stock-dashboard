import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import uuid
import time
from datetime import datetime

# --- CONFIGURATION ---
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSGCN0vX5T-HTyvx1Bkbm8Jm8QlQrZRgYj_0_E2kKX7UKQvE12oVQ0s-QZqkct7Ev6c0sp3Bqx82JQR/pub?output=csv" # Put your CSV link here!
SHEET_NAME = "Tally Live Stock"

st.set_page_config(page_title="Manglam Tradelink Portal", layout="wide", page_icon="🏭")

# --- CUSTOM STYLE ---
st.markdown("""
    <style>
    .stApp { background-color: #ffffff; color: #000000; }
    .order-card { padding: 15px; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #007bff; background-color: #f8f9fa;}
    .completed-card { border-left: 5px solid #28a745; background-color: #f8f9fa; margin-bottom: 10px;}
    </style>
    """, unsafe_allow_html=True)

# --- GOOGLE SHEETS CONNECTION ---
@st.cache_resource
def get_gspread_client():
    try:
        raw_secrets = st.secrets["GOOGLE_CREDENTIALS"]
        creds_dict = json.loads(raw_secrets, strict=False)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open(SHEET_NAME).worksheet("Orders")
    except Exception as e:
        st.error(f"Could not connect to Google Sheets for orders. Error: {e}")
        return None

orders_sheet = get_gspread_client()

# --- LOAD INVENTORY DATA ---
@st.cache_data(ttl=60)
def load_data():
    try:
        df = pd.read_csv(SHEET_CSV_URL)
        df.columns = df.columns.str.strip()
        if 'Quantity' in df.columns:
            df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0)
            df['Unit'] = df['Unit'].fillna('units')
            df['Item'] = df['Item Name']
            df['Group'] = df['Group']
            df['Display Qty'] = df['Quantity'].map('{:,.0f}'.format) + " " + df['Unit']
        return df
    except:
        return pd.DataFrame()

df = load_data()

# --- APP NAVIGATION ---
st.sidebar.title("🏢 Nyc Brand Portal")
page = st.sidebar.radio("Navigate", ["📦 Inventory Dashboard", "📝 Order Desk"])

st.sidebar.divider()
if st.sidebar.button("🔄 Force Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# ==========================================
# PAGE 1: INVENTORY DASHBOARD
# ==========================================
if page == "📦 Inventory Dashboard":
    st.title("📦 Live Physical Inventory")
    
    if not df.empty:
        col_search, col_filter = st.columns(2)
        with col_search:
            search_text = st.text_input("🔍 Search Item...", "")
        with col_filter:
            groups = ["All Groups"] + df['Group'].dropna().unique().tolist()
            selected_group = st.selectbox("📂 Filter Group:", groups)

        filtered_df = df.copy()
        if search_text:
            filtered_df = filtered_df[filtered_df['Item'].str.contains(search_text, case=False, na=False)]
        if selected_group != "All Groups":
            filtered_df = filtered_df[filtered_df['Group'] == selected_group]

        total_qty = filtered_df['Quantity'].sum()
        
        m1, m2 = st.columns(2)
        m1.metric("📦 Volume (Filtered)", f"{total_qty:,.0f} units")
        m2.metric("📋 Items Found", len(filtered_df))

        st.divider()
        tab1, tab2 = st.tabs(["📊 Bar Chart", "📋 Stock List"])

        with tab1:
            if not filtered_df.empty:
                chart_df = filtered_df.sort_values('Quantity', ascending=False)
                fig = px.bar(chart_df, x='Item', y='Quantity', color='Group', hover_data=['Display Qty'])
                fig.update_layout(xaxis_tickangle=-45, height=500, plot_bgcolor="white")
                st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.dataframe(
                filtered_df[['Group', 'Item', 'Quantity', 'Unit']].sort_values("Quantity", ascending=False),
                use_container_width=True, hide_index=True
            )
    else:
        st.warning("Waiting for inventory sync...")

# ==========================================
# PAGE 2: ORDER DESK
# ==========================================
elif page == "📝 Order Desk":
    st.title("📝 Order Management")
    
    order_tab1, order_tab2, order_tab3 = st.tabs(["➕ Place New Order", "⏳ Pending Orders", "✅ Completed Orders"])
    
    # --- TAB 1: PLACE ORDER ---
    with order_tab1:
        st.subheader("Create a New Order")
        
        customer_name = st.text_input("👤 Customer Name", placeholder="e.g. Sharma Traders")
        
        st.write("🛒 Select Items & Quantities")
        item_list = df['Item'].tolist() if not df.empty else []
        
        # You can select multiple items at once here!
        selected_items = st.multiselect("Choose Items from Inventory", item_list)
        
        order_details_dict = {}
        if selected_items:
            st.markdown("---")
            st.markdown("#### Specify Quantities")
            
            # This creates a dedicated input row for EVERY item selected
            for item in selected_items:
                st.markdown(f"**{item}**")
                col1, col2, col3 = st.columns([1, 1, 1])
                
                unit = df[df['Item'] == item]['Unit'].iloc[0] if not df.empty else "units"
                
                with col1:
                    qty = st.number_input(f"Primary Qty ({unit})", min_value=1.0, value=1.0, step=1.0, key=f"p_qty_{item}")
                with col2:
                    # Optional Alternate Quantity
                    alt_qty = st.number_input(f"Alt Qty (Optional)", min_value=0.0, value=0.0, step=1.0, key=f"a_qty_{item}")
                with col3:
                    # Optional Alternate Unit (e.g., Rolls, Boxes)
                    alt_unit = st.text_input(f"Alt Unit (e.g. Rolls, Boxes)", key=f"a_unit_{item}")
                
                # Combine the inputs into a clean string
                detail_str = f"{qty} {unit}"
                if alt_qty > 0 and alt_unit:
                    detail_str += f" (Alt: {alt_qty} {alt_unit})"
                    
                order_details_dict[item] = detail_str
                st.markdown("---")
        
        st.write("") 
        if st.button("🚀 Submit Order", type="primary"):
            if not customer_name:
                st.error("Please enter a customer name.")
            elif not selected_items:
                st.error("Please select at least one item.")
            else:
                order_id = str(uuid.uuid4())[:8].upper()
                order_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # Format the final order string neatly
                details_str = " | ".join([f"{k}: {v}" for k, v in order_details_dict.items()])
                
                try:
                    orders_sheet.append_row([order_id, order_date, customer_name, details_str, "Pending"])
                    st.success(f"✅ Order #{order_id} placed successfully! Refreshing in 5 seconds...")
                    
                    time.sleep(5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to save order: {e}")

    # --- FETCH LIVE ORDERS FROM SHEET ---
    try:
        all_orders = orders_sheet.get_all_records()
        orders_df = pd.DataFrame(all_orders)
    except:
        orders_df = pd.DataFrame()

    # --- TAB 2: PENDING ORDERS ---
    with order_tab2:
        st.subheader("⏳ Pending Orders")
        if not orders_df.empty and 'Status' in orders_df.columns:
            pending_df = orders_df[orders_df['Status'] == 'Pending']
            
            if pending_df.empty:
                st.info("No pending orders right now. Great job!")
            else:
                pending_df = pending_df.sort_values(by='Date', ascending=False)
                
                for index, row in pending_df.iterrows():
                    with st.container():
                        st.markdown(f"""
                        <div class="order-card">
                            <b>Order ID:</b> {row['Order ID']} <br>
                            <b>Date:</b> {row['Date']} <br>
                            <b>Customer:</b> {row['Customer Name']} <br>
                            <b>Items:</b> {row['Order Details']}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if st.button(f"✅ Mark Order {row['Order ID']} Complete", key=f"btn_{row['Order ID']}"):
                            try:
                                cell = orders_sheet.find(row['Order ID'])
                                orders_sheet.update_cell(cell.row, 5, 'Completed')
                                st.success(f"Marked {row['Order ID']} as completed! Refreshing...")
                                time.sleep(2)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error updating: {e}")
                        st.write("")
        else:
            st.info("No orders found.")

    # --- TAB 3: COMPLETED ORDERS ---
    with order_tab3:
        st.subheader("✅ Completed Orders")
        if not orders_df.empty and 'Status' in orders_df.columns:
            completed_df = orders_df[orders_df['Status'] == 'Completed']
            
            if completed_df.empty:
                st.info("No completed orders yet.")
            else:
                completed_df = completed_df.sort_values(by='Date', ascending=False)
                for index, row in completed_df.iterrows():
                    st.markdown(f"""
                    <div class="completed-card order-card">
                        <b>Order ID:</b> {row['Order ID']} <br>
                        <b>Date:</b> {row['Date']} <br>
                        <b>Customer:</b> {row['Customer Name']} <br>
                        <b>Items:</b> {row['Order Details']}
                    </div>
                    """, unsafe_allow_html=True)
