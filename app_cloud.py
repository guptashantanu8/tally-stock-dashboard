import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import time
from datetime import datetime
import pytz

# --- CONFIGURATION ---
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSGCN0vX5T-HTyvx1Bkbm8Jm8QlQrZRgYj_0_E2kKX7UKQvE12oVQ0s-QZqkct7Ev6c0sp3Bqx82JQR/pub?output=csv" # Put your CSV link here!
SHEET_NAME = "Tally Live Stock"
IST = pytz.timezone('Asia/Kolkata') # Indian Standard Time

st.set_page_config(page_title="Manglam Tradelink Portal", layout="wide", page_icon="🏭")

# --- CUSTOM STYLE ---
st.markdown("""
    <style>
    .stApp { background-color: #ffffff; color: #000000; }
    .order-card { padding: 15px; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #007bff; background-color: #f8f9fa;}
    .completed-card { border-left: 5px solid #28a745; background-color: #f8f9fa; margin-bottom: 10px;}
    .item-banner { background-color: #e9ecef; padding: 12px 15px; border-radius: 8px 8px 0px 0px; border-left: 5px solid #17a2b8; margin-top: 20px;}
    .item-inputs { background-color: #f8f9fa; padding: 15px; border-radius: 0px 0px 8px 8px; border: 1px solid #e9ecef; border-top: none; margin-bottom: 10px;}
    .order-table { width: 100%; border-collapse: collapse; margin-top: 10px; margin-bottom: 10px; background-color: white; border-radius: 5px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .order-table th { background-color: #f1f3f5; padding: 8px 12px; text-align: left; border-bottom: 2px solid #ddd; font-size: 14px;}
    .order-table td { padding: 8px 12px; border-bottom: 1px solid #eee; font-size: 14px;}
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

# --- HELPER: HTML TABLE GENERATOR ---
def generate_html_table(details_str):
    # Splits the custom string (ItemA: Qty | ItemB: Qty) into a clean HTML table
    items = details_str.split(" | ")
    html = "<table class='order-table'><tr><th>Stock Item</th><th>Quantity Ordered</th></tr>"
    for item in items:
        if ": " in item:
            name, qty = item.split(": ", 1)
            html += f"<tr><td><b>{name}</b></td><td>{qty}</td></tr>"
        else:
            html += f"<tr><td colspan='2'>{item}</td></tr>"
    html += "</table>"
    return html

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
    
    # FETCH LIVE ORDERS EARLY (We need this to calculate the daily Order ID)
    try:
        all_orders = orders_sheet.get_all_records()
        orders_df = pd.DataFrame(all_orders)
    except:
        orders_df = pd.DataFrame()
        
    order_tab1, order_tab2, order_tab3 = st.tabs(["➕ Place New Order", "⏳ Pending Orders", "✅ Completed Orders"])
    
    # --- TAB 1: PLACE ORDER ---
    with order_tab1:
        st.subheader("Create a New Order")
        
        customer_name = st.text_input("👤 Customer Name", placeholder="e.g. Sharma Traders")
        
        st.write("🛒 Select Items to Add to Cart")
        item_list = df['Item'].tolist() if not df.empty else []
        selected_items = st.multiselect("Search and choose items...", item_list)
        
        order_details_dict = {}
        
        if selected_items:
            st.markdown("### 🛒 Cart Details")
            
            for item in selected_items:
                item_data = df[df['Item'] == item]
                avail_qty = item_data['Quantity'].iloc[0] if not item_data.empty else 0
                unit = item_data['Unit'].iloc[0] if not item_data.empty else "units"
                
                st.markdown(f"""
                <div class="item-banner">
                    <h4 style="margin:0; padding:0; color: #333;">{item}</h4>
                    <span style="color: #4CAF50; font-size: 15px; font-weight: bold;">📦 Available Stock: {avail_qty:,.0f} {unit}</span>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown('<div class="item-inputs">', unsafe_allow_html=True)
                c1, c2, c3 = st.columns([1, 1, 1])
                
                with c1:
                    qty = st.number_input(f"Order Qty ({unit})", min_value=1.0, value=1.0, step=1.0, key=f"p_qty_{item}")
                with c2:
                    alt_qty = st.number_input(f"Alt Qty (Optional)", min_value=0.0, value=0.0, step=1.0, key=f"a_qty_{item}")
                with c3:
                    alt_unit = st.text_input(f"Alt Unit (e.g. Rolls, Boxes)", key=f"a_unit_{item}")
                st.markdown('</div>', unsafe_allow_html=True)
                
                detail_str = f"{qty} {unit}"
                if alt_qty > 0 and alt_unit:
                    detail_str += f" (Alt: {alt_qty} {alt_unit})"
                    
                order_details_dict[item] = detail_str
        
        st.write("") 
        if st.button("🚀 Submit Order", type="primary"):
            if not customer_name:
                st.error("Please enter a customer name.")
            elif not selected_items:
                st.error("Please select at least one item.")
            else:
                # 1. CALCULATE IST TIME & DATE
                now_ist = datetime.now(IST)
                date_str = now_ist.strftime("%d.%m.%y") # e.g. 19.02.26
                full_time_str = now_ist.strftime("%d-%m-%Y %I:%M %p")
                
                # 2. CALCULATE TODAY'S ORDER NUMBER (#x)
                today_prefix = f"{date_str}..#"
                next_x = 1
                
                if not orders_df.empty and 'Order ID' in orders_df.columns:
                    # Find all orders that start with today's date prefix
                    today_orders = orders_df[orders_df['Order ID'].astype(str).str.startswith(today_prefix)]
                    if not today_orders.empty:
                        try:
                            # Extract the number after the # symbol
                            nums = today_orders['Order ID'].apply(lambda x: int(str(x).split('..#')[1]))
                            next_x = nums.max() + 1
                        except:
                            next_x = len(today_orders) + 1
                            
                order_id = f"{today_prefix}{next_x}"
                details_str = " | ".join([f"{k}: {v}" for k, v in order_details_dict.items()])
                
                try:
                    orders_sheet.append_row([order_id, full_time_str, customer_name, details_str, "Pending"])
                    st.success(f"✅ Order {order_id} placed successfully! Refreshing in 5 seconds...")
                    time.sleep(5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to save order: {e}")

    # --- TAB 2: PENDING ORDERS ---
    with order_tab2:
        st.subheader("⏳ Pending Orders")
        if not orders_df.empty and 'Status' in orders_df.columns:
            pending_df = orders_df[orders_df['Status'] == 'Pending']
            
            if pending_df.empty:
                st.info("No pending orders right now. Great job!")
            else:
                # We sort by the index to keep newest at the top
                pending_df = pending_df.iloc[::-1]
                
                for index, row in pending_df.iterrows():
                    table_html = generate_html_table(row['Order Details'])
                    
                    with st.container():
                        st.markdown(f"""
                        <div class="order-card">
                            <h4 style="margin-top:0; color:#0056b3;">Order {row['Order ID']}</h4>
                            <b>Date:</b> {row['Date']} (IST)<br>
                            <b>Customer:</b> <span style="font-size: 16px; font-weight:bold; color:#333;">{row['Customer Name']}</span> <br>
                            {table_html}
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
                completed_df = completed_df.iloc[::-1]
                
                for index, row in completed_df.iterrows():
                    table_html = generate_html_table(row['Order Details'])
                    
                    st.markdown(f"""
                    <div class="completed-card order-card">
                        <h4 style="margin-top:0; color:#28a745;">Order {row['Order ID']}</h4>
                        <b>Date:</b> {row['Date']} (IST)<br>
                        <b>Customer:</b> <span style="font-size: 16px; font-weight:bold; color:#333;">{row['Customer Name']}</span> <br>
                        {table_html}
                    </div>
                    """, unsafe_allow_html=True)
