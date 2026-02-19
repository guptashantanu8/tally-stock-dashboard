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
import google.generativeai as genai

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
    .ai-card { background: linear-gradient(135deg, #f6d365 0%, #fda085 100%); padding: 20px; border-radius: 10px; color: #333; margin-bottom: 20px;}
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
        db = client.open(SHEET_NAME)
        # Fetching all required sheets safely
        return db.worksheet("Orders"), db.worksheet("Users"), db.worksheet("Restock Times"), db.worksheet("Weekly Snapshots")
    except Exception as e:
        return None, None, None, None

orders_sheet, users_sheet, restock_sheet, history_sheet = get_gspread_client()

# --- CONFIGURE GEMINI AI ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    ai_model = genai.GenerativeModel('gemini-1.5-flash')
except:
    ai_model = None

# --- SESSION STATE ---
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
            if not users_data:
                st.error("Database Error: The 'Users' sheet is empty.")
            else:
                df_users = pd.DataFrame(users_data)
                df_users.columns = df_users.columns.astype(str).str.strip()
                if 'User ID' not in df_users.columns or 'Password' not in df_users.columns:
                    st.error("Missing User ID or Password headers.")
                else:
                    user_match = df_users[
                        (df_users['User ID'].astype(str).str.strip() == str(login_id).strip()) & 
                        (df_users['Password'].astype(str).str.strip() == str(login_pass).strip())
                    ]
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
    st.stop() 

# ==========================================
# MAIN APP
# ==========================================
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

pages = ["📦 Inventory Dashboard", "📝 Order Desk", "🤖 AI Restock Advisor"]
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
            st.dataframe(filtered_df[['Group', 'Item', 'Quantity', 'Unit']].sort_values("Quantity", ascending=False), use_container_width=True, hide_index=True)

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
        customer_name = st.text_input("👤 Customer Name", placeholder="e.g. Sharma Traders")
        item_list = df['Item'].tolist() if not df.empty else []
        selected_items = st.multiselect("Search and choose items...", item_list)
        order_details_dict = {}
        
        if selected_items:
            for item in selected_items:
                item_data = df[df['Item'] == item]
                avail_qty = item_data['Quantity'].iloc[0] if not item_data.empty else 0
                unit = item_data['Unit'].iloc[0] if not item_data.empty else "units"
                
                st.markdown(f'<div class="item-banner"><h4 style="margin:0; color: #333;">{item}</h4><span style="color: #4CAF50; font-weight: bold;">📦 Stock: {avail_qty:,.0f} {unit}</span></div>', unsafe_allow_html=True)
                st.markdown('<div class="item-inputs">', unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                with c1: qty = st.number_input(f"Order Qty ({unit})", min_value=1.0, value=1.0, step=1.0, key=f"p_{item}")
                with c2: alt_qty = st.number_input("Alt Qty", min_value=0.0, value=0.0, step=1.0, key=f"a_{item}")
                with c3: alt_unit = st.text_input("Alt Unit", key=f"u_{item}")
                st.markdown('</div>', unsafe_allow_html=True)
                
                detail_str = f"{qty} {unit}" + (f" (Alt: {alt_qty} {alt_unit})" if alt_qty > 0 and alt_unit else "")
                order_details_dict[item] = detail_str
        
        if st.button("🚀 Submit Order", type="primary"):
            if not customer_name or not selected_items:
                st.error("Please fill all details.")
            else:
                now_ist = datetime.now(IST)
                today_prefix = f"{now_ist.strftime('%d.%m.%y')}..#"
                next_x = 1
                if not orders_df.empty and 'Order ID' in orders_df.columns:
                    today_orders = orders_df[orders_df['Order ID'].astype(str).str.startswith(today_prefix)]
                    if not today_orders.empty: next_x = len(today_orders) + 1
                
                order_id = f"{today_prefix}{next_x}"
                details_str = " | ".join([f"{k}: {v}" for k, v in order_details_dict.items()])
                try:
                    orders_sheet.append_row([order_id, now_ist.strftime("%d-%m-%Y %I:%M %p"), customer_name, details_str, "Pending", ""])
                    st.success(f"✅ Order {order_id} placed! Refreshing...")
                    time.sleep(3)
                    st.rerun()
                except Exception as e: st.error(f"Error: {e}")

    with order_tab2:
        if not orders_df.empty and 'Status' in orders_df.columns:
            pending_df = orders_df[orders_df['Status'] == 'Pending'].iloc[::-1]
            for _, row in pending_df.iterrows():
                st.markdown(f'<div class="order-card"><h4 style="margin-top:0; color:#0056b3;">Order {row["Order ID"]}</h4><b>Customer:</b> {row["Customer Name"]}<br>{generate_html_table(row["Order Details"])}</div>', unsafe_allow_html=True)
                if st.button(f"✅ Mark Complete", key=f"btn_{row['Order ID']}"):
                    cell = orders_sheet.find(row['Order ID'])
                    orders_sheet.update_cell(cell.row, 5, 'Completed')
                    orders_sheet.update_cell(cell.row, 6, st.session_state.user_name)
                    st.rerun()

    with order_tab3:
        if not orders_df.empty and 'Status' in orders_df.columns:
            completed_df = orders_df[orders_df['Status'] == 'Completed'].iloc[::-1]
            for _, row in completed_df.iterrows():
                cb = row.get('Completed By', 'Unknown')
                st.markdown(f'<div class="completed-card order-card"><h4 style="margin-top:0; color:#28a745;">Order {row["Order ID"]}</h4><b>Customer:</b> {row["Customer Name"]}<br>{generate_html_table(row["Order Details"])}<hr><span style="color: #6c757d;">✅ Completed by: <b>{cb}</b></span></div>', unsafe_allow_html=True)

# --- PAGE 3: AI RESTOCK ADVISOR ---
elif page == "🤖 AI Restock Advisor":
    st.title("🤖 Supply Chain Intelligence")
    st.markdown('<div class="ai-card"><h4>🧠 Gemini AI Analysis</h4><p>Click below to have Google Gemini analyze your live inventory, historical burn rate, and lead times to generate a predictive purchasing report.</p></div>', unsafe_allow_html=True)
    
    if not ai_model:
        st.error("Gemini API Key missing or invalid in Secrets.")
    else:
        if st.button("✨ Generate Smart Restock Report", type="primary"):
            with st.spinner("Gemini is analyzing millions of data points..."):
                try:
                    # Gather Data for AI
                    live_stock = df.to_csv(index=False) if not df.empty else "No live stock data."
                    
                    try:
                        restock_times = pd.DataFrame(restock_sheet.get_all_records()).to_csv(index=False)
                    except: restock_times = "No restock lead times configured."
                    
                    # Construct Prompt
                    prompt = f"""
                    You are an expert AI Supply Chain Manager for a business named Manglam Tradelink (Brand: Nyc) located in New Delhi, manufacturing bags and using PVC/PU coated fabrics.
                    
                    Analyze this data and write an executive advisory report. 
                    Identify items that are running critically low based on their current stock and lead time. Group your recommendations by urgency (Immediate Order, Order Soon, Healthy). Be concise, use bullet points, and highlight specific item names.
                    
                    CURRENT INVENTORY DATA:
                    {live_stock}
                    
                    CONFIGURED LEAD TIMES (Days to Restock):
                    {restock_times}
                    """
                    
                    response = ai_model.generate_content(prompt)
                    st.markdown("### 📊 AI Advisory Report")
                    st.write(response.text)
                except Exception as e:
                    st.error(f"AI Generation Failed: {e}")

# --- PAGE 4: ADMIN DASHBOARD ---
elif page == "⚙️ Admin Dashboard":
    st.title("⚙️ User Management")
    with st.form("add_user_form"):
        new_name, new_id, new_pass, new_role = st.text_input("Full Name"), st.text_input("User ID"), st.text_input("Password", type="password"), st.selectbox("Role", ["Employee", "Admin"])
        if st.form_submit_button("Create User") and new_name and new_id and new_pass:
            users_sheet.append_row([new_id, new_pass, new_role, new_name])
            st.success("User created!")
    
    try: st.dataframe(pd.DataFrame(users_sheet.get_all_records())[['User ID', 'Name', 'Role']], use_container_width=True)
    except: pass
