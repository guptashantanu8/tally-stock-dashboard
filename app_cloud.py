import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import time
from datetime import datetime
import pytz
import uuid

# --- CONFIGURATION ---
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSGCN0vX5T-HTyvx1Bkbm8Jm8QlQrZRgYj_0_E2kKX7UKQvE12oVQ0s-QZqkct7Ev6c0sp3Bqx82JQR/pub?output=csv" # Put your CSV link here!
SHEET_NAME = "Tally Live Stock"
IST = pytz.timezone('Asia/Kolkata')

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
    .login-box { max-width: 400px; margin: 0 auto; padding: 30px; border: 1px solid #ddd; border-radius: 10px; background-color: #f8f9fa; box-shadow: 0 4px 8px rgba(0,0,0,0.1);}
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
        # Return both sheets now!
        return client.open(SHEET_NAME).worksheet("Orders"), client.open(SHEET_NAME).worksheet("Users")
    except Exception as e:
        st.error(f"Could not connect to Google Sheets. Error: {e}")
        return None, None

orders_sheet, users_sheet = get_gspread_client()

# --- SESSION STATE INITIALIZATION ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = ""
    st.session_state.user_name = ""
    st.session_state.role = ""

# ==========================================
# LOGIN SCREEN
# ==========================================
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center; color: #333; margin-top: 50px;'>🏢 Manglam Tradelink Portal</h1>", unsafe_allow_html=True)
    
    st.markdown('<div class="login-box">', unsafe_allow_html=True)
    st.subheader("Secure Login")
    login_id = st.text_input("User ID")
    login_pass = st.text_input("Password", type="password")
    
    if st.button("Login", type="primary", use_container_width=True):
        if users_sheet:
            users_data = users_sheet.get_all_records()
            df_users = pd.DataFrame(users_data)
            
            # Check credentials
            user_match = df_users[(df_users['User ID'] == login_id) & (df_users['Password'].astype(str) == str(login_pass))]
            
            if not user_match.empty:
                st.session_state.logged_in = True
                st.session_state.user_id = user_match.iloc[0]['User ID']
                st.session_state.user_name = user_match.iloc[0]['Name']
                st.session_state.role = user_match.iloc[0]['Role']
                st.success(f"Welcome back, {st.session_state.user_name}!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Invalid User ID or Password")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop() # HALTS THE APP HERE IF NOT LOGGED IN

# ==========================================
# MAIN APP (Only runs if logged in)
# ==========================================

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

def generate_html_table(details_str):
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
st.sidebar.title(f"🏢 Nyc Brand")
st.sidebar.markdown(f"**User:** {st.session_state.user_name}")
st.sidebar.markdown(f"**Role:** {st.session_state.role}")
st.sidebar.divider()

# Only show Admin Dashboard if the user is an Admin
pages = ["📦 Inventory Dashboard", "📝 Order Desk"]
if st.session_state.role == "Admin":
    pages.append("⚙️ Admin Dashboard")

page = st.sidebar.radio("Navigate", pages)

st.sidebar.divider()
if st.sidebar.button("🔄 Force Refresh Data"):
    st.cache_data.clear()
    st.rerun()
if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.rerun()

# --- PAGE 1: INVENTORY DASHBOARD ---
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

# --- PAGE 2: ORDER DESK ---
elif page == "📝 Order Desk":
    st.title("📝 Order Management")
    
    try:
        all_orders = orders_sheet.get_all_records()
        orders_df = pd.DataFrame(all_orders)
    except:
        orders_df = pd.DataFrame()
        
    order_tab1, order_tab2, order_tab3 = st.tabs(["➕ Place New Order", "⏳ Pending Orders", "✅ Completed Orders"])
    
    with order_tab1:
        st.subheader("Create a New Order")
        customer_name = st.text_input("👤 Customer Name", placeholder="e.g. Sharma Traders")
        st.write("🛒 Select Items to Add to Cart")
        item_list = df['Item'].tolist() if not df.empty else []
        selected_items = st.multiselect("Search and choose items...", item_list)
        order_details_dict = {}
        
        if selected_items:
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
                    alt_unit = st.text_input(f"Alt Unit", key=f"a_unit_{item}")
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
                now_ist = datetime.now(IST)
                date_str = now_ist.strftime("%d.%m.%y")
                full_time_str = now_ist.strftime("%d-%m-%Y %I:%M %p")
                today_prefix = f"{date_str}..#"
                next_x = 1
                
                if not orders_df.empty and 'Order ID' in orders_df.columns:
                    today_orders = orders_df[orders_df['Order ID'].astype(str).str.startswith(today_prefix)]
                    if not today_orders.empty:
                        try:
                            nums = today_orders['Order ID'].apply(lambda x: int(str(x).split('..#')[1]))
                            next_x = nums.max() + 1
                        except:
                            next_x = len(today_orders) + 1
                            
                order_id = f"{today_prefix}{next_x}"
                details_str = " | ".join([f"{k}: {v}" for k, v in order_details_dict.items()])
                
                try:
                    # Added empty string for the 'Completed By' column (Column F)
                    orders_sheet.append_row([order_id, full_time_str, customer_name, details_str, "Pending", ""])
                    st.success(f"✅ Order {order_id} placed successfully! Refreshing...")
                    time.sleep(3)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to save order: {e}")

    with order_tab2:
        st.subheader("⏳ Pending Orders")
        if not orders_df.empty and 'Status' in orders_df.columns:
            pending_df = orders_df[orders_df['Status'] == 'Pending']
            if pending_df.empty:
                st.info("No pending orders right now. Great job!")
            else:
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
                        
                        if st.button(f"✅ Mark {row['Order ID']} Complete", key=f"btn_{row['Order ID']}"):
                            try:
                                cell = orders_sheet.find(row['Order ID'])
                                # Update Status to Completed
                                orders_sheet.update_cell(cell.row, 5, 'Completed')
                                # RECORD WHO COMPLETED IT IN COLUMN 6 (F)
                                orders_sheet.update_cell(cell.row, 6, st.session_state.user_name)
                                
                                st.success(f"Marked completed by {st.session_state.user_name}! Refreshing...")
                                time.sleep(2)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error updating: {e}")
                        st.write("")
        else:
            st.info("No orders found.")

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
                    # Safely handle old orders that might not have a 'Completed By' value
                    completed_by = row.get('Completed By', 'Unknown')
                    if not completed_by: completed_by = "Unknown"
                    
                    st.markdown(f"""
                    <div class="completed-card order-card">
                        <h4 style="margin-top:0; color:#28a745;">Order {row['Order ID']}</h4>
                        <b>Date:</b> {row['Date']} (IST)<br>
                        <b>Customer:</b> <span style="font-size: 16px; font-weight:bold; color:#333;">{row['Customer Name']}</span> <br>
                        {table_html}
                        <hr style="margin: 10px 0px;">
                        <span style="color: #6c757d; font-size: 14px;">✅ Completed by: <b>{completed_by}</b></span>
                    </div>
                    """, unsafe_allow_html=True)

# --- PAGE 3: ADMIN DASHBOARD (Hidden from regular employees) ---
elif page == "⚙️ Admin Dashboard":
    st.title("⚙️ User Management")
    st.write("Create and manage employee access.")
    
    with st.form("add_user_form"):
        st.subheader("Add New Employee")
        new_name = st.text_input("Full Name (e.g. Rahul Kumar)")
        new_id = st.text_input("User ID (e.g. rahul123)")
        new_pass = st.text_input("Password", type="password")
        new_role = st.selectbox("Role", ["Employee", "Admin"])
        
        if st.form_submit_button("Create User"):
            if new_name and new_id and new_pass:
                try:
                    users_sheet.append_row([new_id, new_pass, new_role, new_name])
                    st.success(f"User '{new_name}' created successfully!")
                except Exception as e:
                    st.error(f"Error creating user: {e}")
            else:
                st.error("Please fill out all fields.")
                
    st.divider()
    st.subheader("Current Users Directory")
    try:
        current_users = pd.DataFrame(users_sheet.get_all_records())
        # Hide passwords from display!
        display_users = current_users[['User ID', 'Name', 'Role']]
        st.dataframe(display_users, use_container_width=True, hide_index=True)
    except:
        st.info("Loading user directory...")
