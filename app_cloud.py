import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import time
from datetime import datetime, timedelta
import pytz
import uuid
import google.generativeai as genai
from fpdf import FPDF
import urllib.parse
import requests
import extra_streamlit_components as stx
import calendar

# --- CONFIGURATION ---
SHEET_NAME = "Tally Live Stock"
IST = pytz.timezone('Asia/Kolkata')

st.set_page_config(page_title="Manglam Tradelink Portal", layout="wide", page_icon="🏭")

# --- CUSTOM STYLE (PREMIUM SAAS UI) ---
st.markdown("""
    <style>
    /* 1. Hide Streamlit Branding & Adjust Spacing */
    [data-testid="stToolbar"] {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    .block-container {padding-top: 2rem !important; padding-bottom: 2rem !important;}
    
    /* 2. App Background & Global Font Tweaks */
    .stApp {background-color: #f8f9fc; color: #1e293b;}
    
    /* 3. Sleek Login Box */
    .login-box {
        max-width: 420px; margin: 40px auto; padding: 40px; 
        background: #ffffff; border-radius: 16px; 
        box-shadow: 0 10px 25px rgba(0,0,0,0.05); border: 1px solid #e2e8f0;
    }
    
    /* 4. Modern Order Cards with Hover Lift */
    .order-card { 
        padding: 20px; background: #ffffff; border-radius: 12px; 
        border-left: 6px solid #3b82f6; margin-bottom: 15px; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-top: 1px solid #f1f5f9;
        border-right: 1px solid #f1f5f9; border-bottom: 1px solid #f1f5f9;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    .order-card:hover { transform: translateY(-3px); box-shadow: 0 10px 15px rgba(0,0,0,0.05); }
    .completed-card { border-left-color: #10b981; }
    
    /* 5. Clean Item Banners & Inputs for Order Form */
    .item-banner { 
        background: linear-gradient(90deg, #f8fafc 0%, #f1f5f9 100%); 
        padding: 15px 20px; border-radius: 10px 10px 0px 0px; 
        border-left: 5px solid #6366f1; margin-top: 25px; 
        border: 1px solid #e2e8f0; border-bottom: none;
    }
    .item-inputs { 
        background: #ffffff; padding: 20px; border-radius: 0px 0px 10px 10px; 
        border: 1px solid #e2e8f0; border-top: none; margin-bottom: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
    }
    
    /* 6. Beautiful Tables */
    .order-table { 
        width: 100%; border-collapse: collapse; margin-top: 15px; 
        background-color: white; border-radius: 8px; overflow: hidden; 
        border: 1px solid #e2e8f0;
    }
    .order-table th { background-color: #f8fafc; padding: 12px 15px; text-align: left; font-size: 13px; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #e2e8f0;}
    .order-table td { padding: 12px 15px; border-bottom: 1px solid #f1f5f9; font-size: 14px; color: #334155;}
    
    /* 7. Vibrant AI Card */
    .ai-card { 
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%); 
        padding: 25px; border-radius: 16px; color: white; 
        margin-bottom: 25px; box-shadow: 0 10px 20px rgba(99, 102, 241, 0.2);
    }
    .ai-card h4 { color: white !important; margin-top: 0;}
    .ai-card p { color: #f8fafc !important; }
    
    /* 8. Dashboard Metrics Styling */
    [data-testid="stMetric"] {
        background-color: #ffffff; padding: 15px 20px; 
        border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); 
        border: 1px solid #e2e8f0;
    }
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
        
        try: audit_sheet = db.worksheet("Audit Logs")
        except: audit_sheet = None
        
        try: master_sheet = db.worksheet("Master Items")
        except: master_sheet = None

        try: tenants_sheet = db.worksheet("Tenants")
        except: tenants_sheet = None
        
        try: rent_tx_sheet = db.worksheet("Rent Transactions")
        except: rent_tx_sheet = None

        stock_sheet = db.sheet1

        return stock_sheet, db.worksheet("Orders"), db.worksheet("Users"), db.worksheet("Restock Times"), db.worksheet("Weekly Snapshots"), db.worksheet("15-Day Sales"), db.worksheet("Customers"), audit_sheet, master_sheet, tenants_sheet, rent_tx_sheet
    except Exception as e:
        return None, None, None, None, None, None, None, None, None, None, None

stock_sheet, orders_sheet, users_sheet, restock_sheet, history_sheet, sales_sheet, cust_sheet, audit_sheet, master_sheet, tenants_sheet, rent_tx_sheet = get_gspread_client()

# --- CONFIGURE GEMINI AI ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    ai_model = genai.GenerativeModel('gemini-2.5-flash')
except:
    ai_model = None

# --- COOKIE MANAGER & SESSION STATE ---
cookie_manager = stx.CookieManager(key="mt_cookie_manager")
time.sleep(0.5)

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = ""
    st.session_state.user_name = ""
    st.session_state.role = ""

if not st.session_state.logged_in:
    all_cookies = cookie_manager.get_all()
    c_auth = all_cookies.get("mt_auth")
    
    if c_auth:
        parts = str(c_auth).split("::")
        if len(parts) == 3:
            st.session_state.logged_in = True
            st.session_state.user_id = parts[0]
            st.session_state.user_name = parts[1]
            st.session_state.role = parts[2]
            st.rerun()

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
                        
                        expire_date = datetime.now() + timedelta(days=30)
                        auth_string = f"{st.session_state.user_id}::{st.session_state.user_name}::{st.session_state.role}"
                        cookie_manager.set("mt_auth", auth_string, expires_at=expire_date)
                        
                        st.success(f"Welcome back, {st.session_state.user_name}! Securing login...")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("❌ Invalid User ID or Password")
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop() 

# ==========================================
# MAIN APP & HELPER FUNCTIONS (3 MEMORY BANKS)
# ==========================================
@st.cache_data(ttl=60)
def fetch_stock_cache(_sheet): 
    try:
        if _sheet is None: return pd.DataFrame()
        data = _sheet.get_all_values()
        if not data: return pd.DataFrame()
        headers = [str(h).strip() for h in data[0]]
        # 🟢 THE FIX: If there are only headers and no data yet, keep the headers!
        if len(data) == 1: return pd.DataFrame(columns=headers)
        df = pd.DataFrame(data[1:], columns=headers).replace("", None).dropna(how='all').fillna("")
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=60)
def fetch_orders_cache(_sheet): 
    try:
        if _sheet is None: return pd.DataFrame()
        data = _sheet.get_all_values()
        if not data: return pd.DataFrame()
        headers = [str(h).strip() for h in data[0]]
        if len(data) == 1: return pd.DataFrame(columns=headers)
        df = pd.DataFrame(data[1:], columns=headers).replace("", None).dropna(how='all').fillna("")
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=60)
def fetch_rent_cache(_sheet): 
    try:
        if _sheet is None: return pd.DataFrame()
        data = _sheet.get_all_values()
        if not data: return pd.DataFrame()
        headers = [str(h).strip() for h in data[0]]
        if len(data) == 1: return pd.DataFrame(columns=headers)
        df = pd.DataFrame(data[1:], columns=headers).replace("", None).dropna(how='all').fillna("")
        return df
    except: return pd.DataFrame()

# 🟢 LOAD INVENTORY SAFELY
df = fetch_stock_cache(stock_sheet)

if not df.empty and 'Quantity' in df.columns:
    df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0)
    df['Unit'] = df['Unit'].fillna('units')
    df['Item'] = df['Item Name']
    if 'Group' not in df.columns: df['Group'] = 'Default'
    df['Display Qty'] = df['Quantity'].map('{:,.0f}'.format) + " " + df['Unit']

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

def create_order_pdf(row):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 20)
    pdf.cell(0, 10, "MANGLAM TRADELINK", ln=True, align="C")
    pdf.set_font("helvetica", "", 12)
    pdf.cell(0, 8, "NYC Brand - Official Order Receipt", ln=True, align="C")
    pdf.ln(10)
    
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(40, 8, "Order ID:", 0, 0)
    pdf.set_font("helvetica", "", 12)
    pdf.cell(0, 8, str(row.get('Order ID', '')), ln=True)
    
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(40, 8, "Date (IST):", 0, 0)
    pdf.set_font("helvetica", "", 12)
    pdf.cell(0, 8, str(row.get('Date', '')), ln=True)
    
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(40, 8, "Customer:", 0, 0)
    pdf.set_font("helvetica", "", 12)
    pdf.cell(0, 8, str(row.get('Customer Name', '')), ln=True)
    
    notes = str(row.get('Notes', '')).strip()
    if notes and notes != 'None':
        pdf.set_font("helvetica", "B", 12)
        pdf.cell(40, 8, "Notes:", 0, 0)
        pdf.set_font("helvetica", "", 12)
        pdf.multi_cell(0, 8, notes)
        
    pdf.ln(10)
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(0, 10, "Order Details & Quantities", ln=True)
    pdf.set_font("helvetica", "", 12)
    
    items = str(row.get('Order Details', '')).split(" | ")
    for item in items:
        clean_item = item.encode('latin-1', 'replace').decode('latin-1')
        pdf.cell(0, 8, f"- {clean_item}", ln=True)
        
    return bytes(pdf.output())

# ==========================================
# APP NAVIGATION MENU
# ==========================================
st.sidebar.title(f"🏢 NYC Brand")
st.sidebar.markdown(f"**User:** {st.session_state.user_name}")
st.sidebar.markdown(f"**Role:** {st.session_state.role}")
st.sidebar.divider()

pages = ["📦 Inventory Dashboard", "📝 Order Desk", "🔍 Stock Audit", "🤖 AI Restock Advisor", "🏢 Rent Tracker"]

if st.session_state.role == "Admin":
    pages.append("📊 Audit Report")
    pages.append("⚙️ Admin Dashboard")

page = st.sidebar.radio("Navigate", pages)

st.sidebar.divider()
if st.sidebar.button("🔄 Force Refresh Data"):
    st.cache_data.clear()
    st.rerun()
if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    cookie_manager.delete("mt_auth")
    cookie_manager.delete("mt_userid")
    st.rerun()

# --- PAGE 1: INVENTORY DASHBOARD ---
if page == "📦 Inventory Dashboard":
    st.title("📦 Live Physical Inventory")
    if not df.empty:
        col_search, col_filter = st.columns(2)
        with col_search: search_text = st.text_input("🔍 Search Item...", "")
        with col_filter:
            groups = ["All Groups"] + df['Group'].dropna().unique().tolist()
            selected_group = st.selectbox("📂 Filter Group:", groups)

        filtered_df = df.copy()
        if search_text: filtered_df = filtered_df[filtered_df['Item'].str.contains(search_text, case=False, na=False)]
        if selected_group != "All Groups": filtered_df = filtered_df[filtered_df['Group'] == selected_group]

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
                fig.update_layout(xaxis_tickangle=-45, height=500, plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)

        with tab2:
            sorted_df = filtered_df[['Group', 'Item', 'Quantity', 'Unit']].sort_values(["Group", "Quantity"], ascending=[True, False])
            st.dataframe(sorted_df, use_container_width=True, hide_index=True)

# --- PAGE 2: ORDER DESK ---
elif page == "📝 Order Desk":
    st.title("📝 Order Management")
    orders_df = fetch_orders_cache(orders_sheet)
    
    order_tab1, order_tab2, order_tab3 = st.tabs(["➕ Place New Order", "⏳ Pending Orders", "✅ Completed Orders"])
    
    with order_tab1:
        # 🟢 THE FIX: Initialize a Master Reset Key
        if 'form_reset' not in st.session_state:
            st.session_state.form_reset = 0
        r_key = st.session_state.form_reset
        
        try:
            cust_data = cust_sheet.get_all_records()
            customer_list = sorted(list(set([str(row['Customer Name']).strip() for row in cust_data if 'Customer Name' in row and str(row['Customer Name']).strip()])))
        except: customer_list = []
            
        st.subheader("Create a New Order")
        st.write("👤 **Customer Details**")
        
        # Notice how every input now has f"_{r_key}" attached to it!
        customer_dropdown = st.selectbox("Search Existing Customer:", customer_list, index=None, placeholder="Start typing to search...", key=f"order_cust_drop_{r_key}")
        
        if not customer_dropdown: 
            customer_name = st.text_input("Or manually type a New Customer Name:", placeholder="e.g. Sharma Traders", key=f"order_cust_text_{r_key}")
        else: 
            customer_name = customer_dropdown
            
        order_notes = st.text_input("📝 Order Notes (Optional)", placeholder="e.g. Dispatch via VRL Logistics, Urgent...", key=f"order_notes_{r_key}")
        
        st.divider()
        st.write("🛒 **Select Items to Add to Cart**")
        
        try:
            master_data = master_sheet.get_all_records()
            item_list = sorted([str(row['Item Name']).strip() for row in master_data if 'Item Name' in row])
        except:
            item_list = df['Item'].tolist() if not df.empty else []
            
        selected_items = st.multiselect("Search and choose items...", item_list, key=f"order_items_{r_key}")
        order_details_dict = {}
        
        if selected_items:
            for item in selected_items:
                item_data = df[df['Item'] == item]
                if not item_data.empty:
                    avail_qty = item_data['Quantity'].iloc[0]
                    unit = item_data['Unit'].iloc[0]
                    stock_color = "#4CAF50"
                else:
                    avail_qty = 0
                    unit = "units"
                    stock_color = "#dc3545"
                
                st.markdown(f'<div class="item-banner"><h4 style="margin:0; color: #333;">{item}</h4><span style="color: {stock_color}; font-weight: bold;">📦 Stock: {avail_qty:,.0f} {unit}</span></div>', unsafe_allow_html=True)
                st.markdown('<div class="item-inputs">', unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                with c1: qty = st.number_input(f"Order Qty ({unit})", min_value=1.0, value=1.0, step=1.0, key=f"p_{item}_{r_key}")
                with c2: alt_qty = st.number_input("Alt Qty", min_value=0.0, value=0.0, step=1.0, key=f"a_{item}_{r_key}")
                with c3: alt_unit = st.text_input("Alt Unit", key=f"u_{item}_{r_key}")
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
                    orders_sheet.append_row([order_id, now_ist.strftime("%d-%m-%Y %I:%M %p"), customer_name, details_str, "Pending", "", order_notes])
                    
                    # Telegram Processing
                    tg_success = False
                    try:
                        tg_token = st.secrets.get("TELEGRAM_BOT_TOKEN")
                        tg_chat_id = st.secrets.get("TELEGRAM_CHAT_ID")
                        if tg_token and tg_chat_id:
                            items_array = details_str.split(" | ")
                            table_text = "━━━━━━━━━━━━━━━━━━━━\n"
                            for i in items_array:
                                if ": " in i:
                                    name, q = i.split(": ", 1)
                                    table_text += f"▪️ {name} ➔ {q}\n"
                                else:
                                    table_text += f"▪️ {i}\n"
                            table_text += "━━━━━━━━━━━━━━━━━━━━\n"
                            
                            alert_text = "🚨 NEW ORDER ALERT 🚨\n\n"
                            alert_text += f"🆔 {order_id}\n👤 {customer_name}\n\n{table_text}"
                            if order_notes and str(order_notes).strip(): alert_text += f"\n📝 Notes: {order_notes}\n"
                            alert_text += f"\n✅ Placed By: {st.session_state.user_name}"
                            
                            encoded_text = urllib.parse.quote(alert_text)
                            res = requests.get(f"https://api.telegram.org/bot{tg_token}/sendMessage?chat_id={tg_chat_id}&text={encoded_text}")
                            
                            if res.status_code == 200:
                                tg_success = True
                            else:
                                st.error(f"⚠️ Telegram failed: {res.text}")
                        else:
                            st.error("⚠️ Telegram keys are missing from Streamlit Secrets.")
                    except Exception as tg_e:
                        st.error(f"⚠️ Telegram System Error: {tg_e}")
                    
                    if tg_success:
                        st.success(f"✅ Order {order_id} placed and alert sent to Warehouse!")
                    else:
                        st.success(f"✅ Order {order_id} placed successfully in Database!")

                    # 🟢 THE UNIFIED FIX: Advance the reset key AND clear the memory cache!
                    st.session_state.form_reset += 1
                    fetch_orders_cache.clear()
                            
                    time.sleep(1.5)
                    st.rerun()
                except Exception as e: 
                    st.error(f"Error saving order: {e}")
                    

    with order_tab2:
        if not orders_df.empty and 'Status' in orders_df.columns:
            pending_df = orders_df[orders_df['Status'] == 'Pending'].iloc[::-1]
            for idx, row in pending_df.iterrows():
                st.markdown(f'<div class="order-card"><h4 style="margin-top:0; color:#0056b3;">Order {row["Order ID"]}</h4><b>Customer:</b> {row["Customer Name"]}<br><b>Notes:</b> {row.get("Notes", "None")}<br>{generate_html_table(row["Order Details"])}</div>', unsafe_allow_html=True)
                
                c1, c2 = st.columns([1, 1])
                with c1:
                    if st.button(f"✅ Mark Complete", key=f"btn_{row['Order ID']}_{idx}"):
                        try:
                            cell = orders_sheet.find(row['Order ID'])
                            orders_sheet.update_cell(cell.row, 5, 'Completed')
                            orders_sheet.update_cell(cell.row, 6, st.session_state.user_name)
                            
                            try:
                                tg_token = st.secrets.get("TELEGRAM_BOT_TOKEN")
                                tg_chat_id = st.secrets.get("TELEGRAM_CHAT_ID")
                                if tg_token and tg_chat_id:
                                    comp_text = f"✅ *ORDER COMPLETED* ✅\n\n🆔 {row['Order ID']}\n👤 {row['Customer Name']}\n👷 Completed By: {st.session_state.user_name}"
                                    encoded_comp = urllib.parse.quote(comp_text)
                                    requests.get(f"https://api.telegram.org/bot{tg_token}/sendMessage?chat_id={tg_chat_id}&text={encoded_comp}")
                            except: pass
                            
                            st.success(f"Order Completed!")
                            time.sleep(1)
                            fetch_orders_cache.clear()
                            st.rerun()
                        except Exception as e: st.error(f"Error: {e}")
                with c2:
                    pdf_data = create_order_pdf(row)
                    st.download_button("📄 Share PDF", data=pdf_data, file_name=f"Order_{row['Order ID']}.pdf", mime="application/pdf", key=f"pdf_{row['Order ID']}_{idx}")

                with st.expander("✏️ Modify or Delete Order"):
                    mod_cust = st.text_input("Customer Name", str(row['Customer Name']), key=f"mcust_{row['Order ID']}_{idx}")
                    
                    current_items = {}
                    for chunk in str(row['Order Details']).split(" | "):
                        if ": " in chunk:
                            k, v = chunk.split(": ", 1)
                            current_items[k.strip()] = v.strip()
                            
                    all_items = df['Item'].dropna().unique().tolist() if not df.empty else []
                    for k in current_items.keys():
                        if k not in all_items: all_items.append(k)
                            
                    st.write("🛒 **Modify Items & Quantities**")
                    mod_selected_items = st.multiselect(
                        "Add or Remove Items (Exact Names):",
                        options=all_items,
                        default=list(current_items.keys()),
                        key=f"mitems_{row['Order ID']}_{idx}"
                    )
                    
                    new_order_dict = {}
                    for item in mod_selected_items:
                        default_qty = current_items.get(item, "1.0 units")
                        new_qty = st.text_input(f"Quantity/Details for [{item}]", value=default_qty, key=f"mqty_{row['Order ID']}_{idx}_{item}")
                        new_order_dict[item] = new_qty
                        
                    mod_notes = st.text_input("Notes", str(row.get('Notes', '')), key=f"mnot_{row['Order ID']}_{idx}")
                    
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        if st.button("💾 Save Changes", type="primary", key=f"msave_{row['Order ID']}_{idx}"):
                            reconstructed_details = " | ".join([f"{k}: {v}" for k, v in new_order_dict.items()])
                            if not reconstructed_details:
                                st.error("You must have at least one item in the order.")
                            else:
                                try:
                                    cell = orders_sheet.find(row['Order ID'])
                                    orders_sheet.update_cell(cell.row, 3, mod_cust)
                                    orders_sheet.update_cell(cell.row, 4, reconstructed_details)
                                    orders_sheet.update_cell(cell.row, 7, mod_notes)
                                    st.success("Order Updated!")
                                    time.sleep(1)
                                    fetch_orders_cache.clear()
                                    st.rerun()
                                except Exception as e: st.error(f"Failed to update: {e}")
                    with ec2:
                        if st.button("❌ Delete Order", key=f"mdel_{row['Order ID']}_{idx}"):
                            try:
                                cell = orders_sheet.find(row['Order ID'])
                                orders_sheet.delete_rows(cell.row)
                                st.warning("Order Deleted!")
                                time.sleep(1)
                                fetch_orders_cache.clear()
                                st.rerun()
                            except Exception as e: st.error(f"Failed to delete: {e}")

    with order_tab3:
        if not orders_df.empty and 'Status' in orders_df.columns:
            completed_df = orders_df[orders_df['Status'] == 'Completed'].copy()
            completed_df['Parsed Date'] = pd.to_datetime(completed_df['Date'], format="%d-%m-%Y %I:%M %p", errors='coerce').dt.date
            
            with st.expander("🔎 Advanced Filters & Search"):
                fc1, fc2, fc3, fc4 = st.columns(4)
                
                with fc1:
                    search_query = st.text_input("Search (Name, ID, Notes)", placeholder="e.g. Sharma...", key="search_comp")
                
                with fc2:
                    min_date = completed_df['Parsed Date'].dropna().min() if not completed_df['Parsed Date'].dropna().empty else datetime.today().date()
                    max_date = completed_df['Parsed Date'].dropna().max() if not completed_df['Parsed Date'].dropna().empty else datetime.today().date()
                    date_filter = st.date_input("Date Range", value=(), min_value=min_date, max_value=max_date, key="date_comp")
                
                with fc3:
                    emp_list = ["All Employees"] + sorted(completed_df['Completed By'].dropna().unique().tolist())
                    emp_filter = st.selectbox("Completed By", emp_list, key="emp_comp")
                    
                with fc4:
                    item_list = ["All Items"] + df['Item'].dropna().unique().tolist() if not df.empty else ["All Items"]
                    item_filter = st.selectbox("Contains Fabric/Item", item_list, key="item_comp")
                    
            filtered_df = completed_df.copy()
            
            if search_query:
                filtered_df = filtered_df[
                    filtered_df['Order ID'].astype(str).str.contains(search_query, case=False, na=False) |
                    filtered_df['Customer Name'].astype(str).str.contains(search_query, case=False, na=False) |
                    filtered_df['Notes'].astype(str).str.contains(search_query, case=False, na=False)
                ]
                
            if isinstance(date_filter, tuple) and len(date_filter) == 2:
                start_date, end_date = date_filter
                filtered_df = filtered_df[(filtered_df['Parsed Date'] >= start_date) & (filtered_df['Parsed Date'] <= end_date)]
                
            if emp_filter != "All Employees":
                filtered_df = filtered_df[filtered_df['Completed By'] == emp_filter]
                
            if item_filter != "All Items":
                filtered_df = filtered_df[filtered_df['Order Details'].astype(str).str.contains(item_filter, case=False, na=False)]

            filtered_df = filtered_df.iloc[::-1]
            st.markdown(f"<p style='color: #64748b; font-size: 14px;'>Showing <b>{len(filtered_df)}</b> completed orders matching your criteria.</p>", unsafe_allow_html=True)

            for idx, row in filtered_df.iterrows():
                cb = row.get('Completed By', 'Unknown')
                st.markdown(f'<div class="completed-card order-card"><h4 style="margin-top:0; color:#10b981;">Order {row["Order ID"]}</h4><b>Customer:</b> {row["Customer Name"]}<br><b>Notes:</b> {row.get("Notes", "None")}<br>{generate_html_table(row["Order Details"])}<hr><span style="color: #6c757d;">✅ Completed by: <b>{cb}</b> on {row.get("Date", "")}</span></div>', unsafe_allow_html=True)
                
                c1, c2 = st.columns([1, 1])
                with c1:
                    pdf_data = create_order_pdf(row)
                    st.download_button("📄 Download Receipt", data=pdf_data, file_name=f"Receipt_{row['Order ID']}.pdf", mime="application/pdf", key=f"pdf_comp_{row['Order ID']}_{idx}")
                with c2:
                    if st.session_state.role == "Admin":
                        if st.button("🗑️ Delete Record", key=f"del_comp_{row['Order ID']}_{idx}"):
                            try:
                                cell = orders_sheet.find(row['Order ID'])
                                orders_sheet.delete_rows(cell.row)
                                st.warning("Record Deleted permanently!")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e: st.error(f"Failed to delete: {e}")

# --- PAGE 3: STOCK AUDIT (EMPLOYEE VIEW) ---
elif page == "🔍 Stock Audit":
    st.title("🔍 Physical Stock Audit")
    
    with st.expander("👀 View Current System Quantities (Live Tally Stock)"):
        st.dataframe(df[['Group', 'Item', 'Quantity', 'Unit']].sort_values(["Group", "Quantity"], ascending=[True, False]), use_container_width=True, hide_index=True)
    
    if not audit_sheet:
        st.error("Audit Logs database not found. Please ask Admin to create the 'Audit Logs' sheet.")
    else:
        try:
            audit_data = audit_sheet.get_all_records()
            audit_df = pd.DataFrame(audit_data)
            if not audit_df.empty and 'Status' in audit_df.columns:
                active_audit = audit_df[audit_df['Status'] == 'Active']
            else:
                active_audit = pd.DataFrame(columns=['Timestamp', 'Item Name', 'Location', 'Quantity Found', 'Employee Name', 'Status'])
        except:
            active_audit = pd.DataFrame(columns=['Timestamp', 'Item Name', 'Location', 'Quantity Found', 'Employee Name', 'Status'])

        all_items = df['Item'].dropna().unique().tolist()
        audited_items = active_audit['Item Name'].dropna().unique().tolist() if not active_audit.empty else []
        remaining_items = [i for i in all_items if i not in audited_items]
        
        st.metric("📊 Audit Progress", f"{len(audited_items)} / {len(all_items)} Items Audited")
        st.progress(len(audited_items) / len(all_items) if len(all_items) > 0 else 0.0)
        
        st.divider()
        st.write("Count scattered batches in the warehouse. Your entries will be summed automatically.")

        audit_item = st.selectbox("Search & Select Item to Count:", all_items, index=None, placeholder="Type item name...")
        
        if audit_item:
            item_audits = active_audit[active_audit['Item Name'] == audit_item]
            found_so_far = pd.to_numeric(item_audits['Quantity Found'], errors='coerce').sum() if not item_audits.empty else 0
            
            st.markdown("### 📊 Live Item Progress")
            if st.session_state.role == "Admin":
                system_qty = df[df['Item'] == audit_item]['Quantity'].iloc[0] if not df.empty else 0
                variance = found_so_far - system_qty
                
                c1, c2, c3 = st.columns(3)
                c1.metric("System Expected", f"{system_qty:,.0f}")
                c2.metric("Found So Far", f"{found_so_far:,.0f}")
                c3.metric("Variance", f"{variance:,.0f}", delta_color="inverse")
            else:
                st.metric("📦 Found So Far (Your Counts)", f"{found_so_far:,.0f}")
            
            st.divider()
            
            st.subheader("➕ Log a Found Batch")
            with st.form("audit_form", clear_on_submit=True):
                loc = st.text_input("Location / Rack Details (Optional)", placeholder="e.g., Aisle 3, Top Shelf")
                qty = st.number_input("Quantity Found in this specific location", min_value=0.0, step=1.0)
                submit_batch = st.form_submit_button("💾 Save Batch", type="primary")
                
                if submit_batch:
                    if qty < 0:
                        st.error("Quantity cannot be negative.")
                    else:
                        timestamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                        try:
                            audit_sheet.append_row([timestamp, audit_item, loc, qty, st.session_state.user_name, "Active"])
                            st.success(f"Successfully logged {qty} for {audit_item}!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to log audit: {e}")
                            
            if not item_audits.empty:
                st.markdown("**Recent entries for this item:**")
                st.dataframe(item_audits[['Location', 'Quantity Found', 'Employee Name', 'Timestamp']].iloc[::-1], hide_index=True)

        st.divider()
        st.subheader("📋 Remaining Items to Count")
        if remaining_items:
            rem_df = df[df['Item'].isin(remaining_items)][['Group', 'Item']].sort_values(["Group", "Item"])
            st.dataframe(rem_df, use_container_width=True, hide_index=True)
        else:
            st.success("🎉 Incredible job! All inventory items have been physically audited.")

# --- PAGE 4: AUDIT REPORT (ADMIN ONLY) ---
elif page == "📊 Audit Report":
    st.title("📊 Physical Audit Variance Report")
    st.write("Compare physical counts submitted by employees against live Tally stock.")
    
    if not audit_sheet:
        st.error("Audit Logs database not found.")
    else:
        try:
            audit_data = audit_sheet.get_all_records()
            audit_df = pd.DataFrame(audit_data)
        except:
            audit_df = pd.DataFrame()
            
        if not audit_df.empty and 'Status' in audit_df.columns:
            active_audit = audit_df[audit_df['Status'] == 'Active']
            
            if active_audit.empty:
                st.info("No active audits running.")
            else:
                active_audit['Quantity Found'] = pd.to_numeric(active_audit['Quantity Found'], errors='coerce')
                summary_df = active_audit.groupby('Item Name')['Quantity Found'].sum().reset_index()
                
                report_data = []
                for _, row in summary_df.iterrows():
                    item = row['Item Name']
                    physical_qty = row['Quantity Found']
                    system_qty = df[df['Item'] == item]['Quantity'].iloc[0] if not df[df['Item'] == item].empty else 0
                    variance = physical_qty - system_qty
                    report_data.append({
                        "Item": item,
                        "System Expected": system_qty,
                        "Physical Count": physical_qty,
                        "Variance": variance
                    })
                
                report_df = pd.DataFrame(report_data)
                st.dataframe(
                    report_df.style.map(lambda x: 'color: red;' if x < 0 else 'color: green;' if x > 0 else '', subset=['Variance']),
                    use_container_width=True, hide_index=True
                )
                
                st.divider()
                st.subheader("Archive Current Audit")
                st.warning("Archiving the audit board resets all items back to 'Pending' for the next full warehouse count.")
                
                if st.button("Archive & Reset Audit Board", type="primary"):
                    try:
                        cell_list = audit_sheet.findall("Active")
                        for cell in cell_list:
                            if cell.col == 6:
                                audit_sheet.update_cell(cell.row, 6, "Closed")
                        st.success("Audit Archived Successfully! The board is now clear.")
                        time.sleep(2)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to archive: {e}")
        else:
            st.info("No audit logs found.")

# --- PAGE 5: AI RESTOCK ADVISOR ---
elif page == "🤖 AI Restock Advisor":
    st.title("🤖 Supply Chain Intelligence")
    st.markdown('<div class="ai-card"><h4>🧠 Gemini AI Predictive Analysis</h4><p>Click below to have Gemini analyze your live inventory against the <b>last 15 days of outward sales</b> and your lead times to generate a highly prioritized reordering report.</p></div>', unsafe_allow_html=True)
    
    if not ai_model:
        st.error("Gemini API Key missing or invalid in Secrets.")
    else:
        if st.button("✨ Generate Smart Restock Report", type="primary"):
            with st.spinner("Gemini is analyzing burn rates, lead times, and current stock..."):
                try:
                    live_stock = df.to_csv(index=False) if not df.empty else "No live stock data."
                    try: restock_times = pd.DataFrame(restock_sheet.get_all_records()).to_csv(index=False)
                    except: restock_times = "No restock lead times configured."
                    try: recent_sales = pd.DataFrame(sales_sheet.get_all_records()).to_csv(index=False)
                    except: recent_sales = "No recent sales data available."
                    
                    prompt = f"""
                    You are an expert AI Supply Chain Manager for Manglam Tradelink (Brand: Nyc), manufacturing bags with fabrics like Twill, 1000D PU, 1000D PVC, etc.
                    
                    CRITICAL INSTRUCTION: You MUST give the HIGHEST PRIORITY to the "RECENT 15-DAY SALES (OUTWARD MOVEMENT)" data. 
                    If an item is selling fast in the last 15 days, it needs to be reordered immediately to meet current demand velocity. Calculate the daily burn rate (15-Day Sales / 15) and multiply it by the Lead Time to determine if current stock is dangerously low.
                    
                    Analyze this data and write an executive advisory report grouped by urgency:
                    1. 🔴 URGENT REORDER (Stock will likely run out before lead time finishes based on recent 15-day sales).
                    2. 🟡 MONITOR CLOSELY (Selling steadily, reorder soon).
                    3. 🟢 HEALTHY STOCK (Current stock easily covers recent velocity + lead time).
                    
                    CURRENT INVENTORY DATA:
                    {live_stock}
                    
                    RECENT 15-DAY SALES (OUTWARD MOVEMENT):
                    {recent_sales}
                    
                    CONFIGURED LEAD TIMES (Days to Restock):
                    {restock_times}
                    """
                    response = ai_model.generate_content(prompt)
                    st.markdown("### 📊 Predictive Restock Report")
                    st.write(response.text)
                except Exception as e:
                    st.error(f"AI Generation Failed: {e}")

# --- PAGE 6: ADMIN DASHBOARD ---
elif page == "⚙️ Admin Dashboard":
    st.title("⚙️ User Management")
    with st.form("add_user_form"):
        new_name, new_id, new_pass, new_role = st.text_input("Full Name"), st.text_input("User ID"), st.text_input("Password", type="password"), st.selectbox("Role", ["Employee", "Admin"])
        if st.form_submit_button("Create User") and new_name and new_id and new_pass:
            users_sheet.append_row([new_id, new_pass, new_role, new_name])
            st.success("User created!")
    
    try: st.dataframe(pd.DataFrame(users_sheet.get_all_records())[['User ID', 'Name', 'Role']], use_container_width=True)
    except: pass

# --- PAGE 7: RENT TRACKER ---
elif page == "🏢 Rent Tracker":
    st.title("🏢 Property & Rent Tracker")
    
    if tenants_sheet is None or rent_tx_sheet is None:
        st.error("⚠️ Database Error: 'Tenants' or 'Rent Transactions' sheets not found in Google Sheets.")
    else:
        df_tenants = fetch_rent_cache(tenants_sheet)
        df_tx = fetch_rent_cache(rent_tx_sheet)

        if 'Name' not in df_tenants.columns:
            st.error("⚠️ Critical Database Error: The 'Name' column is missing.")
            st.warning(f"🕵️ Debugger: Here are the exact headers Python is seeing right now: {df_tenants.columns.tolist()}")
            st.info("💡 If you see completely random text or blank spaces above, Google Sheets has saved empty ghost rows. Please delete Rows 2 through 1000 in your spreadsheet, click 'Force Refresh Data', and try again.")
            st.stop()

        balances = {}
        if not df_tenants.empty and not df_tx.empty and 'Amount' in df_tx.columns and 'Tenant Name' in df_tx.columns:
            for t_name in df_tenants['Name'].dropna().unique():
                t_tx = df_tx[df_tx['Tenant Name'] == t_name]
                charges = pd.to_numeric(t_tx[t_tx['Type'] == 'Charge']['Amount'], errors='coerce').sum()
                payments = pd.to_numeric(t_tx[t_tx['Type'] == 'Payment']['Amount'], errors='coerce').sum()
                balances[t_name] = charges - payments
        elif not df_tenants.empty and 'Name' in df_tenants.columns:
            for t_name in df_tenants['Name'].dropna().unique(): 
                balances[t_name] = 0

        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Balances", "💸 Collect Payment", "⚡ Log Bills", "📜 History", "⚙️ Manage Tenants"])

        with tab1:
            st.subheader("Current Pending Balances")
            if not df_tenants.empty:
                for idx, row in df_tenants.iterrows():
                    t_name = row['Name']
                    bal = balances.get(t_name, 0)
                    status_color = "#dc3545" if bal > 0 else "#10b981"
                    status_text = f"DUE: ₹{bal:,.2f}" if bal > 0 else "CLEARED"
                    
                    try: sec_dep = float(row.get('Security Deposit', 0.0))
                    except (ValueError, TypeError): sec_dep = 0.0
                    
                    st.markdown(f"""
                    <div class="order-card">
                        <h4 style="margin:0; color:#333;">{t_name} <span style="float:right; color:{status_color};">{status_text}</span></h4>
                        <p style="margin:5px 0 0 0; color:#64748b;">
                            📍 {row.get('Location', 'N/A')} | 🏠 Rent: ₹{row.get('Rent Amount', 0)} | ⚡ Elec: {row.get('Electricity Type', 'N/A')} (Paid by {row.get('Elec Paid By', 'N/A')})<br>
                            <span style="color: #0284c7; font-weight: 500;">🛡️ Security Deposit Held: ₹{sec_dep:,.2f}</span>
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No tenants found. Add one in the 'Manage Tenants' tab.")

        with tab2:
            st.subheader("Record a Received Payment")
            if not df_tenants.empty:
                with st.form("payment_form", clear_on_submit=True):
                    p_tenant = st.selectbox("Select Tenant", df_tenants['Name'].tolist())
                    p_amt = st.number_input("Payment Amount Received (₹)", min_value=1.0, step=100.0)
                    p_notes = st.text_input("Notes (e.g. Cash, UPI Reference)")
                    
                    if st.form_submit_button("💾 Save Payment", type="primary"):
                        timestamp = datetime.now(IST).strftime("%d-%m-%Y %I:%M %p")
                        rent_tx_sheet.append_row([timestamp, p_tenant, "Payment", "Payment Received", float(p_amt), "", p_notes, st.session_state.user_name])
                        st.success(f"Payment of ₹{p_amt} recorded for {p_tenant}!")
                        time.sleep(1)
                        st.rerun()

        with tab3:
            st.subheader("Generate Monthly Charges")
            if not df_tenants.empty:
                bill_tenant = st.selectbox("Select Tenant to Bill", df_tenants['Name'].tolist(), key="bill_t")
                t_data = df_tenants[df_tenants['Name'] == bill_tenant].iloc[0]
                
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("##### 🏠 Rent Charge")
                    try: base_rent = float(t_data.get('Rent Amount', 0.0))
                    except (ValueError, TypeError): base_rent = 0.0
                    charge_rent = st.checkbox(f"Apply Base Rent (₹{base_rent})", value=True)
                
                with c2:
                    st.markdown("##### ⚡ Electricity Charge")
                    e_type = str(t_data.get('Electricity Type', 'None'))
                    try: e_rate = float(t_data.get('Elec Rate', 0.0))
                    except (ValueError, TypeError): e_rate = 0.0
                    
                    units = 0.0
                    new_meter = 0.0
                    
                    if str(t_data.get('Elec Paid By', '')) == 'Company/Landlord':
                        st.info("Electricity is covered by the Landlord/Company.")
                        charge_elec = False
                    elif e_type == 'Fixed':
                        charge_elec = st.checkbox(f"Apply Fixed Electricity (₹{e_rate})", value=True)
                    elif e_type == 'Variable':
                        try: prev_meter = float(t_data.get('Meter Reading', 0.0))
                        except (ValueError, TypeError): prev_meter = 0.0
                        
                        st.info(f"Last Recorded Meter: **{prev_meter}**")
                        new_meter = st.number_input(f"Enter Current Meter Reading", min_value=prev_meter, step=1.0, value=prev_meter)
                        units = new_meter - prev_meter
                        st.write(f"**Calculated Usage:** {units} units (Rate: ₹{e_rate})")
                        charge_elec = st.checkbox("Apply Variable Electricity", value=True)
                    else:
                        st.write("No electricity tracking configured.")
                        charge_elec = False

                bill_notes = st.text_input("Billing Month / Notes (e.g., 'March 2026 Rent')", key="bill_n")

                if st.button("📝 Post Charges to Ledger", type="primary"):
                    timestamp = datetime.now(IST).strftime("%d-%m-%Y %I:%M %p")
                    try:
                        if charge_rent:
                            rent_tx_sheet.append_row([timestamp, bill_tenant, "Charge", "Rent", base_rent, "", bill_notes, st.session_state.user_name])
                        
                        if charge_elec:
                            e_amt = e_rate if e_type == 'Fixed' else (e_rate * units)
                            if e_amt > 0:
                                rent_tx_sheet.append_row([timestamp, bill_tenant, "Charge", "Electricity", float(e_amt), float(units), bill_notes, st.session_state.user_name])
                                if e_type == 'Variable':
                                    t_cell = tenants_sheet.find(str(t_data['Tenant ID']))
                                    tenants_sheet.update_cell(t_cell.row, 8, float(new_meter))
                                    
                        st.success("Charges successfully posted to the tenant's ledger!")
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e: st.error(f"Error posting charges: {e}")

        with tab4:
            st.subheader("Ledger History")
            if not df_tenants.empty and not df_tx.empty:
                hist_tenant = st.selectbox("View History For:", ["All Tenants"] + df_tenants['Name'].tolist())
                
                hist_df = df_tx.copy()
                if hist_tenant != "All Tenants" and 'Tenant Name' in hist_df.columns:
                    hist_df = hist_df[hist_df['Tenant Name'] == hist_tenant]
                
                hist_df = hist_df.iloc[::-1]
                
                # 🟢 THE FIX: Safely check if the 'Type' column exists before trying to color-code it!
                if 'Type' in hist_df.columns:
                    st.dataframe(hist_df.style.map(lambda x: 'color: #dc3545; font-weight:bold;' if x == 'Charge' else 'color: #10b981; font-weight:bold;' if x == 'Payment' else '', subset=['Type']), use_container_width=True, hide_index=True)
                else:
                    st.dataframe(hist_df, use_container_width=True, hide_index=True)
            else:
                st.info("No transaction history found yet. Post a bill or log a payment to see it here!")

        with tab5:
            with st.expander("➕ Add New Tenant", expanded=False):
                with st.form("add_tenant_form", clear_on_submit=True):
                    t_id = f"T-{uuid.uuid4().hex[:6].upper()}"
                    nt_name = st.text_input("Tenant/Company Name")
                    nt_loc = st.text_input("Location / Unit Number")
                    
                    c1, c2 = st.columns(2)
                    with c1: nt_rent = st.number_input("Monthly Base Rent (₹)", min_value=0.0, step=500.0)
                    with c2: nt_security = st.number_input("Security Deposit Received (₹)", min_value=0.0, step=500.0)
                    
                    st.write("⚡ **Electricity Configuration**")
                    nt_etype = st.selectbox("Electricity Billing Type", ["Fixed", "Variable", "None"])
                    nt_erate = st.number_input("Fixed Amount OR Rate Per Unit (₹)", min_value=0.0, step=1.0)
                    nt_epaid = st.selectbox("Electricity Paid By", ["Tenant", "Company/Landlord"])
                    
                    nt_meter = 0.0
                    if nt_etype == "Variable":
                        nt_meter = st.number_input("Initial Meter Reading (Base Units)", min_value=0.0, step=1.0)
                        
                    st.divider()
                    apply_prorata = st.checkbox("Automatically charge Pro-Rata rent for the remaining days of this month?", value=True)
                    
                    if st.form_submit_button("Create Tenant Profile", type="primary"):
                        if nt_name:
                            tenants_sheet.append_row([t_id, nt_name, nt_loc, float(nt_rent), nt_etype, float(nt_erate), nt_epaid, float(nt_meter), float(nt_security)])
                            
                            if apply_prorata and nt_rent > 0:
                                now = datetime.now(IST)
                                days_in_month = calendar.monthrange(now.year, now.month)[1]
                                days_active = days_in_month - now.day + 1
                                pro_rata_rent = round((float(nt_rent) / days_in_month) * days_active, 2)
                                
                                timestamp = now.strftime("%d-%m-%Y %I:%M %p")
                                rent_tx_sheet.append_row([
                                    timestamp, nt_name, "Charge", "Rent (Pro-Rata)", float(pro_rata_rent), "",
                                    f"Pro-rata rent for {days_active} days in {now.strftime('%b %Y')}",
                                    st.session_state.user_name
                                ])
                                st.success(f"Tenant added! First pro-rata rent of ₹{pro_rata_rent} automatically charged.")
                            else:
                                st.success("Tenant added without pro-rata billing. Rent will start on the next billing cycle.")
                                
                            time.sleep(2)
                            st.rerun()
                        else: st.error("Name is required.")
            
            st.markdown("### Existing Tenants")
            if not df_tenants.empty:
                for idx, row in df_tenants.iterrows():
                    with st.expander(f"⚙️ {row['Name']} ({row['Location']})"):
                        if st.session_state.role == "Admin":
                            if st.button("🗑️ Delete Tenant", key=f"del_t_{idx}"):
                                cell = tenants_sheet.find(row['Tenant ID'])
                                tenants_sheet.delete_rows(cell.row)
                                st.warning("Tenant deleted.")
                                time.sleep(1)
                                st.rerun()
                        else:
                            st.info("Only Admins can delete tenants. Contact Admin for removal.")






