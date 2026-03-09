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
    .block-container {padding-top: 3rem !important; padding-bottom: 2rem !important;}
    
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
        import json
        creds_raw = st.secrets["GOOGLE_CREDENTIALS"]
        
        # 🟢 THE BULLETPROOF LOADER: strict=False forces Python to ignore line breaks!
        if isinstance(creds_raw, str):
            try:
                creds_dict = json.loads(creds_raw, strict=False)
            except Exception:
                # If it still fails, forcefully fix the literal newlines
                clean_raw = creds_raw.replace('\n', '\\n').replace('\r', '')
                creds_dict = json.loads(clean_raw, strict=False)
        else:
            creds_dict = dict(creds_raw)
            
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        db = client.open("Tally Live Stock")
        
        def safe_open(name):
            try: return db.worksheet(name)
            except: return None

        return (
            db.sheet1, # 🟢 THIS FIXES THE DASHBOARD: It automatically grabs your first tab!
            safe_open("Orders"),
            safe_open("Users"),
            safe_open("Restock Times"),
            safe_open("Weekly Snapshots"),
            safe_open("15-Day Sales"),
            safe_open("Customers"),
            safe_open("Audit Logs"),
            safe_open("Master Items"),
            safe_open("Tenants"),
            safe_open("Rent Transactions")
        )
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets: {e}")
        return [None]*11

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
# 🌐 EARLY LANGUAGE INIT (so Login page can also be translated)
# ==========================================
saved_lang = cookie_manager.get("mt_lang")
if "app_lang" not in st.session_state:
    st.session_state.app_lang = saved_lang if saved_lang in ["English", "Hindi"] else "English"

# Login page translation (small dict used before full LANG is loaded)
_login_t = {
    "English": {"title": "🏢 Manglam Tradelink Portal", "secure": "Secure Login", "uid": "User ID", "pwd": "Password", "btn": "Login", "welcome": "Welcome back, {name}! Securing login...", "invalid": "❌ Invalid User ID or Password", "empty": "Database Error: The 'Users' sheet is empty.", "headers": "Missing User ID or Password headers."},
    "Hindi": {"title": "🏢 मंगलम ट्रेडलिंक पोर्टल", "secure": "सुरक्षित लॉगिन", "uid": "यूज़र आईडी", "pwd": "पासवर्ड", "btn": "लॉगिन", "welcome": "फिर से स्वागत है, {name}! लॉगिन सुरक्षित हो रहा है...", "invalid": "❌ गलत यूज़र आईडी या पासवर्ड", "empty": "डेटाबेस त्रुटि: 'Users' शीट खाली है।", "headers": "User ID या Password हेडर गायब है।"},
}
_lt = _login_t[st.session_state.app_lang]

# ==========================================
# LOGIN SCREEN
# ==========================================
if not st.session_state.logged_in:
    # Language toggle on login page too
    _, login_lang_col = st.columns([7, 3])
    with login_lang_col:
        is_hindi_login = st.session_state.app_lang == "Hindi"
        new_lang_login = "Hindi" if st.toggle("हिंदी / Eng", value=is_hindi_login, key="login_lang") else "English"
        if new_lang_login != st.session_state.app_lang:
            st.session_state.app_lang = new_lang_login
            cookie_manager.set("mt_lang", new_lang_login)
            st.rerun()

    st.markdown(f"<h1 style='text-align: center; color: #333; margin-top: 50px;'>{_lt['title']}</h1>", unsafe_allow_html=True)
    st.markdown('<div class="login-box">', unsafe_allow_html=True)
    st.subheader(_lt["secure"])
    login_id = st.text_input(_lt["uid"])
    login_pass = st.text_input(_lt["pwd"], type="password")
    
    if st.button(_lt["btn"], type="primary", use_container_width=True):
        if users_sheet:
            users_data = users_sheet.get_all_records()
            if not users_data:
                st.error(_lt["empty"])
            else:
                df_users = pd.DataFrame(users_data)
                df_users.columns = df_users.columns.astype(str).str.strip()
                if 'User ID' not in df_users.columns or 'Password' not in df_users.columns:
                    st.error(_lt["headers"])
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
                        
                        st.success(_lt["welcome"].format(name=st.session_state.user_name))
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(_lt["invalid"])
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
def fetch_rent_cache(_sheet, sheet_name): # 🟢 THE FIX: Added sheet_name so Streamlit doesn't mix them up!
    try:
        if _sheet is None: return pd.DataFrame()
        data = _sheet.get_all_values()
        if not data: return pd.DataFrame()
        headers = [str(h).strip() for h in data[0]]
        if len(data) == 1: return pd.DataFrame(columns=headers)
        df = pd.DataFrame(data[1:], columns=headers).replace("", None).dropna(how='all').fillna("")
        return df
    except: return pd.DataFrame()
    

# 🟢 HINDI DATA MAP — Reads the "Hindi Map" sheet for data translation
@st.cache_data(ttl=300)
def fetch_hindi_map(_client_open_func):
    """Load the English→Hindi translation map from the 'Hindi Map' sheet tab."""
    try:
        hindi_sheet = _client_open_func("Hindi Map")
        if hindi_sheet is None: return {}
        data = hindi_sheet.get_all_records()
        return {str(row.get("English","")).strip(): str(row.get("Hindi","")).strip() 
                for row in data if row.get("English") and row.get("Hindi")}
    except:
        return {}

# Try to load the Hindi Map (safe — returns empty dict if sheet doesn't exist yet)
_hindi_map = {}
try:
    def _safe_open_hindi(name):
        """Helper to open a worksheet by name for the Hindi Map."""
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        import json
        creds_raw = st.secrets["GOOGLE_CREDENTIALS"]
        if isinstance(creds_raw, str):
            try: creds_dict = json.loads(creds_raw, strict=False)
            except: creds_dict = json.loads(creds_raw.replace('\n', '\\n').replace('\r', ''), strict=False)
        else: creds_dict = dict(creds_raw)
        from oauth2client.service_account import ServiceAccountCredentials
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        db = client.open("Tally Live Stock")
        try: return db.worksheet(name)
        except: return None
    _hindi_map = fetch_hindi_map(_safe_open_hindi)
except:
    _hindi_map = {}

def hindi(text):
    """Translate data value to Hindi if Hindi mode is ON and translation exists."""
    if st.session_state.get("app_lang") != "Hindi":
        return text
    if not text or not isinstance(text, str):
        return text
    return _hindi_map.get(text.strip(), text)

def hindi_df_columns(dataframe, col_names):
    """Apply hindi() to specific columns of a DataFrame for display."""
    if st.session_state.get("app_lang") != "Hindi" or not _hindi_map:
        return dataframe
    display_df = dataframe.copy()
    for col in col_names:
        if col in display_df.columns:
            display_df[col] = display_df[col].astype(str).apply(lambda x: _hindi_map.get(x.strip(), x))
    return display_df


# 🟢 LOAD INVENTORY SAFELY
df = fetch_stock_cache(stock_sheet)

# 🟢 THE FIX: Global Safety Net to prevent KeyErrors across all pages
if not df.empty and 'Quantity' in df.columns and 'Item Name' in df.columns:
    df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0)
    if 'Unit' not in df.columns: df['Unit'] = 'units'
    df['Unit'] = df['Unit'].fillna('units')
    df['Item'] = df['Item Name']
    if 'Group' not in df.columns: df['Group'] = 'Default'
    df['Display Qty'] = df['Quantity'].map('{:,.0f}'.format) + " " + df['Unit']
else:
    # If the sheet is empty or syncing, load a blank template so the app doesn't crash
    df = pd.DataFrame(columns=['Group', 'Item', 'Quantity', 'Unit', 'Display Qty'])

def generate_html_table(details_str):
    items = details_str.split(" | ")
    html = "<table class='order-table'><tr><th>Stock Item</th><th>Quantity Ordered</th></tr>"
    for item in items:
        if ": " in item:
            name, qty = item.split(": ", 1)
            html += f"<tr><td><b>{hindi(name)}</b></td><td>{qty}</td></tr>"
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
# 🌐 LANGUAGE DICTIONARY (full version for main app)
# ==========================================

# 2. Complete Hindi Dictionary for the ENTIRE UI
LANG = {
    "English": {
        # --- Navigation & Header ---
        "brand": "🏢 NYC Brand",
        "inv": "📦 Inventory Dashboard",
        "ord": "📝 Order Desk",
        "aud": "🔍 Stock Audit",
        "ai": "🤖 AI Restock Advisor",
        "rent": "🏢 Rent Tracker",
        "rep": "📊 Audit Report",
        "admin": "⚙️ Admin Dashboard",
        "menu": "🧭 Menu",
        "refresh": "🔄 Refresh",
        "logout": "🚪 Logout",

        # --- Login Page ---
        "portal_title": "🏢 Manglam Tradelink Portal",
        "secure_login": "Secure Login",
        "user_id": "User ID",
        "password": "Password",
        "login_btn": "Login",
        "welcome_back": "Welcome back, {name}! Securing login...",
        "invalid_creds": "❌ Invalid User ID or Password",
        "db_error_empty": "Database Error: The 'Users' sheet is empty.",
        "missing_headers": "Missing User ID or Password headers.",
        "sheets_error": "Failed to connect to Google Sheets: {err}",

        # --- Inventory Dashboard ---
        "search_item": "🔍 Search Item...",
        "filter_group": "📂 Filter Group:",
        "all_groups": "All Groups",
        "volume_filtered": "📦 Volume (Filtered)",
        "items_found": "📋 Items Found",
        "bar_chart": "📊 Bar Chart",
        "stock_list": "📋 Stock List",

        # --- Order Desk ---
        "place_order": "➕ Place New Order",
        "pending_orders": "⏳ Pending Orders",
        "completed_orders": "✅ Completed Orders",
        "create_order": "Create a New Order",
        "customer_details": "👤 **Customer Details**",
        "search_customer": "Search Existing Customer:",
        "search_customer_ph": "Start typing to search...",
        "new_customer_name": "Or manually type a New Customer Name:",
        "new_customer_ph": "e.g. Sharma Traders",
        "order_notes_label": "📝 Order Notes (Optional)",
        "order_notes_ph": "e.g. Dispatch via VRL Logistics, Urgent...",
        "select_items_cart": "🛒 **Select Items to Add to Cart**",
        "search_choose_items": "Search and choose items...",
        "stock_label": "📦 Stock:",
        "order_qty": "Order Qty",
        "alt_qty": "Alt Qty",
        "alt_unit": "Alt Unit",
        "submit_order": "🚀 Submit Order",
        "fill_all_details": "Please fill all details.",
        "order_placed_tg": "✅ Order {oid} placed and alert sent to Warehouse!",
        "order_placed_db": "✅ Order {oid} placed successfully in Database!",
        "tg_failed": "⚠️ Telegram failed: {err}",
        "tg_keys_missing": "⚠️ Telegram keys are missing from Streamlit Secrets.",
        "tg_system_error": "⚠️ Telegram System Error: {err}",
        "error_saving_order": "Error saving order: {err}",
        "mark_complete": "✅ Mark Complete",
        "share_pdf": "📄 Share PDF",
        "modify_delete": "✏️ Modify or Delete Order",
        "customer_name_label": "Customer Name",
        "modify_items": "🛒 **Modify Items & Quantities**",
        "add_remove_items": "Add or Remove Items (Exact Names):",
        "qty_details_for": "Quantity/Details for [{item}]",
        "notes_label": "Notes",
        "save_changes": "💾 Save Changes",
        "delete_order": "❌ Delete Order",
        "order_updated": "Order Updated!",
        "failed_update": "Failed to update: {err}",
        "order_deleted": "Order Deleted!",
        "failed_delete": "Failed to delete: {err}",
        "order_completed": "Order Completed!",
        "adv_filters": "🔎 Advanced Filters & Search",
        "search_name_id": "Search (Name, ID, Notes)",
        "search_eg": "e.g. Sharma...",
        "date_range": "Date Range",
        "completed_by": "Completed By",
        "all_employees": "All Employees",
        "contains_fabric": "Contains Fabric/Item",
        "all_items_filter": "All Items",
        "showing_completed": "Showing <b>{count}</b> completed orders matching your criteria.",
        "download_receipt": "📄 Download Receipt",
        "delete_record": "🗑️ Delete Record",
        "record_deleted": "Record Deleted permanently!",

        # --- Stock Audit ---
        "view_system_qty": "👀 View Current System Quantities (Live Tally Stock)",
        "stock_syncing": "⚠️ Live stock data is currently syncing or missing.",
        "audit_db_missing": "Audit Logs database not found. Please ask Admin to create the 'Audit Logs' sheet.",
        "audit_progress": "📊 Audit Progress",
        "items_audited": "{done} / {total} Items Audited",
        "count_batches": "Count scattered batches in the warehouse. Your entries will be summed automatically.",
        "search_select_item": "Search & Select Item to Count:",
        "type_item_name": "Type item name...",
        "live_item_progress": "### 📊 Live Item Progress",
        "system_expected": "System Expected",
        "found_so_far": "Found So Far",
        "variance": "Variance",
        "found_so_far_yours": "📦 Found So Far (Your Counts)",
        "log_batch": "➕ Log a Found Batch",
        "location_rack": "Location / Rack Details (Optional)",
        "location_rack_ph": "e.g., Aisle 3, Top Shelf",
        "qty_found_here": "Quantity Found in this specific location",
        "save_batch": "💾 Save Batch",
        "qty_negative": "Quantity cannot be negative.",
        "logged_success": "Successfully logged {qty} for {item}!",
        "failed_log_audit": "Failed to log audit: {err}",
        "recent_entries": "**Recent entries for this item:**",
        "remaining_items": "📋 Remaining Items to Count",
        "all_audited": "🎉 Incredible job! All inventory items have been physically audited.",

        # --- AI Restock Advisor (was also Audit Report page routing) ---
        "compare_counts": "Compare physical counts submitted by employees against live Tally stock.",
        "audit_db_not_found": "Audit Logs database not found.",
        "no_active_audits": "No active audits running.",
        "archive_audit": "Archive Current Audit",
        "archive_warning": "Archiving the audit board resets all items back to 'Pending' for the next full warehouse count.",
        "archive_btn": "Archive & Reset Audit Board",
        "archive_success": "Audit Archived Successfully! The board is now clear.",
        "failed_archive": "Failed to archive: {err}",
        "no_audit_logs": "No audit logs found.",

        # --- AI Restock Advisor (actual page) ---
        "supply_chain_title": "🤖 Supply Chain Intelligence",
        "ai_card_title": "🧠 Gemini AI Predictive Analysis",
        "ai_card_desc": "Click below to have Gemini analyze your live inventory against the <b>last 15 days of outward sales</b> and your lead times to generate a highly prioritized reordering report.",
        "ai_key_missing": "Gemini API Key missing or invalid in Secrets.",
        "generate_report": "✨ Generate Smart Restock Report",
        "ai_spinner": "Gemini is analyzing burn rates, lead times, and current stock...",
        "restock_report_title": "### 📊 Predictive Restock Report",
        "ai_failed": "AI Generation Failed: {err}",

        # --- Admin Dashboard ---
        "user_mgmt": "⚙️ User Management",
        "full_name": "Full Name",
        "create_user_btn": "Create User",
        "user_created": "User created!",
        "role_label": "Role",

        # --- Rent Tracker ---
        "rent_db_error": "⚠️ Database Error: Sheets not found in Google Sheets.",
        "tab_balances": "📊 Balances & Dashboard",
        "tab_collect": "💸 Collect Payment",
        "tab_bills": "⚡ Log Bills",
        "tab_history": "📜 History",
        "tab_manage": "⚙️ Manage Tenants",
        "action_required": "🚨 **ACTION REQUIRED TODAY:** Generate Monthly Bills for: **{names}**",
        "active_tenants": "🟢 Active Tenants",
        "no_active_tenants": "No active tenants right now.",
        "due_label": "DUE: ₹{amt}",
        "advance_label": "ADVANCE: ₹{amt}",
        "cleared_label": "CLEARED",
        "pending_dues_label": "PENDING DUES: ₹{amt}",
        "refund_due_label": "REFUND DUE: ₹{amt}",
        "settled_label": "SETTLED",
        "first_of_month": "1st of Month",
        "date_of_month": "Date {day} of Month",
        "view_vacated": "🚪 View Vacated Tenants",
        "no_tenants_found": "No tenants found. Add one in the 'Manage Tenants' tab.",
        "record_payment": "Record a Received Payment",
        "select_tenant": "Select Tenant",
        "payment_amount": "Payment Amount Received (₹)",
        "payment_notes": "Notes (e.g. Cash, UPI Reference, Final Settlement)",
        "save_payment": "💾 Save Payment",
        "payment_recorded": "Payment of ₹{amt} recorded for {tenant}!",
        "generate_charges": "Generate Monthly Charges",
        "select_tenant_bill": "Select Tenant to Bill",
        "rent_charge": "##### 🏠 Rent Charge",
        "apply_base_rent": "Apply Base Rent (₹{amt})",
        "elec_charge": "##### ⚡ Electricity Charge",
        "elec_covered": "Electricity is covered by the Landlord/Company.",
        "enter_meter_bill": "💡 Enter the exact meter bill amount you paid for them.",
        "lump_sum_elec": "Lump Sum Electricity Bill (₹)",
        "passthrough_bill": "Pass-through Bill to Tenant Ledger",
        "last_meter": "Last Recorded Meter: **{val}**",
        "current_meter": "Enter Current Meter Reading",
        "calc_usage": "**Calculated Usage:** {units} units (Rate: ₹{rate})",
        "apply_var_elec": "Apply Variable Electricity",
        "no_elec_tracking": "No electricity tracking configured.",
        "billing_month": "Billing Month / Notes (e.g., 'March 2026 Rent')",
        "post_charges": "📝 Post Charges to Ledger",
        "charges_posted": "Charges successfully posted to the tenant's ledger!",
        "error_posting": "Error posting charges: {err}",
        "no_active_to_bill": "No active tenants to bill.",
        "ledger_history": "Ledger History",
        "view_history_for": "View History For:",
        "all_tenants_hist": "All Tenants",
        "no_tx_history": "No transaction history available yet.",
        "add_tenant": "➕ Add New Tenant",
        "tenant_name": "Tenant/Company Name",
        "location_unit": "Location / Unit Number",
        "monthly_rent": "Monthly Base Rent (₹)",
        "security_deposit": "Security Deposit Received (₹)",
        "elec_config": "⚡ **Electricity Configuration**",
        "elec_billing_type": "Electricity Billing Type",
        "rate_per_unit": "Rate Per Unit (₹) - Only if Variable",
        "elec_paid_by": "Electricity Paid By",
        "initial_meter": "Initial Meter Reading (Base Units)",
        "billing_cycle": "📅 **Billing Cycle & Move-In**",
        "date_keys_given": "Date Keys Given (Billing Start)",
        "billing_logic": "Billing Logic",
        "pro_rata_option": "Pro-Rata (Bill on 1st of every month)",
        "fixed_cycle_option": "Fixed Cycle (Bill on Anniversary Date)",
        "create_tenant": "Create Tenant Profile",
        "name_required": "Name is required.",
        "tenant_added_prorata": "Tenant added! First pro-rata rent of ₹{amt} automatically charged.",
        "tenant_added_fixed": "Tenant added! Billing set to exactly the {day} of every month.",
        "edit_vacate": "### ⚙️ Edit / Vacate Existing Tenants",
        "modify_details": "**Modify Details or Process Move-Out**",
        "location_label": "Location",
        "monthly_rent_edit": "Monthly Rent (Increase/Decrease)",
        "elec_type": "Elec Type",
        "per_unit_rate": "Per Unit Rate (If Variable)",
        "security_held": "Security Deposit Held",
        "pro_rata_q": "Pro Rata Billing?",
        "tenant_status": "Tenant Status",
        "save_all": "💾 Save All Changes",
        "tenant_updated": "Tenant profile for {name} updated!",
        "error_updating": "Error updating tenant: {err}",
    },
    "Hindi": {
        # --- नेविगेशन और हेडर ---
        "brand": "🏢 NYC ब्रांड",
        "inv": "📦 स्टॉक डैशबोर्ड",
        "ord": "📝 ऑर्डर डेस्क",
        "aud": "🔍 स्टॉक ऑडिट",
        "ai": "🤖 AI रीस्टॉक सलाह",
        "rent": "🏢 किराया ट्रैकर",
        "rep": "📊 ऑडिट रिपोर्ट",
        "admin": "⚙️ एडमिन डैशबोर्ड",
        "menu": "🧭 मेनू",
        "refresh": "🔄 रिफ्रेश करें",
        "logout": "🚪 लॉगआउट",

        # --- लॉगिन पेज ---
        "portal_title": "🏢 मंगलम ट्रेडलिंक पोर्टल",
        "secure_login": "सुरक्षित लॉगिन",
        "user_id": "यूज़र आईडी",
        "password": "पासवर्ड",
        "login_btn": "लॉगिन",
        "welcome_back": "फिर से स्वागत है, {name}! लॉगिन सुरक्षित हो रहा है...",
        "invalid_creds": "❌ गलत यूज़र आईडी या पासवर्ड",
        "db_error_empty": "डेटाबेस त्रुटि: 'Users' शीट खाली है।",
        "missing_headers": "User ID या Password हेडर गायब है।",
        "sheets_error": "Google Sheets से कनेक्ट नहीं हो पाया: {err}",

        # --- इन्वेंटरी डैशबोर्ड ---
        "search_item": "🔍 आइटम खोजें...",
        "filter_group": "📂 ग्रुप फ़िल्टर:",
        "all_groups": "सभी ग्रुप",
        "volume_filtered": "📦 मात्रा (फ़िल्टर्ड)",
        "items_found": "📋 आइटम मिले",
        "bar_chart": "📊 बार चार्ट",
        "stock_list": "📋 स्टॉक सूची",

        # --- ऑर्डर डेस्क ---
        "place_order": "➕ नया ऑर्डर दें",
        "pending_orders": "⏳ पेंडिंग ऑर्डर",
        "completed_orders": "✅ पूर्ण ऑर्डर",
        "create_order": "नया ऑर्डर बनाएं",
        "customer_details": "👤 **ग्राहक विवरण**",
        "search_customer": "मौजूदा ग्राहक खोजें:",
        "search_customer_ph": "खोजने के लिए टाइप करें...",
        "new_customer_name": "या नया ग्राहक नाम टाइप करें:",
        "new_customer_ph": "जैसे: शर्मा ट्रेडर्स",
        "order_notes_label": "📝 ऑर्डर नोट्स (वैकल्पिक)",
        "order_notes_ph": "जैसे: VRL लॉजिस्टिक्स से भेजें, अर्जेंट...",
        "select_items_cart": "🛒 **कार्ट में आइटम चुनें**",
        "search_choose_items": "आइटम खोजें और चुनें...",
        "stock_label": "📦 स्टॉक:",
        "order_qty": "ऑर्डर मात्रा",
        "alt_qty": "वैकल्पिक मात्रा",
        "alt_unit": "वैकल्पिक यूनिट",
        "submit_order": "🚀 ऑर्डर सबमिट करें",
        "fill_all_details": "कृपया सभी विवरण भरें।",
        "order_placed_tg": "✅ ऑर्डर {oid} दर्ज हुआ और वेयरहाउस को अलर्ट भेजा गया!",
        "order_placed_db": "✅ ऑर्डर {oid} सफलतापूर्वक डेटाबेस में दर्ज हुआ!",
        "tg_failed": "⚠️ टेलीग्राम विफल: {err}",
        "tg_keys_missing": "⚠️ Streamlit Secrets में टेलीग्राम कुंजियाँ गायब हैं।",
        "tg_system_error": "⚠️ टेलीग्राम सिस्टम त्रुटि: {err}",
        "error_saving_order": "ऑर्डर सेव करने में त्रुटि: {err}",
        "mark_complete": "✅ पूर्ण करें",
        "share_pdf": "📄 PDF शेयर करें",
        "modify_delete": "✏️ ऑर्डर संशोधित / हटाएं",
        "customer_name_label": "ग्राहक का नाम",
        "modify_items": "🛒 **आइटम और मात्रा बदलें**",
        "add_remove_items": "आइटम जोड़ें या हटाएं (सही नाम):",
        "qty_details_for": "[{item}] के लिए मात्रा/विवरण",
        "notes_label": "नोट्स",
        "save_changes": "💾 बदलाव सहेजें",
        "delete_order": "❌ ऑर्डर हटाएं",
        "order_updated": "ऑर्डर अपडेट हो गया!",
        "failed_update": "अपडेट विफल: {err}",
        "order_deleted": "ऑर्डर हटा दिया गया!",
        "failed_delete": "हटाना विफल: {err}",
        "order_completed": "ऑर्डर पूरा हो गया!",
        "adv_filters": "🔎 एडवांस फ़िल्टर और खोज",
        "search_name_id": "खोजें (नाम, आईडी, नोट्स)",
        "search_eg": "जैसे: शर्मा...",
        "date_range": "तारीख सीमा",
        "completed_by": "पूर्ण किया",
        "all_employees": "सभी कर्मचारी",
        "contains_fabric": "कपड़ा/आइटम शामिल",
        "all_items_filter": "सभी आइटम",
        "showing_completed": "आपकी शर्तों से मेल खाते <b>{count}</b> पूर्ण ऑर्डर दिख रहे हैं।",
        "download_receipt": "📄 रसीद डाउनलोड करें",
        "delete_record": "🗑️ रिकॉर्ड हटाएं",
        "record_deleted": "रिकॉर्ड स्थायी रूप से हटा दिया गया!",

        # --- स्टॉक ऑडिट ---
        "view_system_qty": "👀 वर्तमान सिस्टम मात्रा देखें (लाइव टैली स्टॉक)",
        "stock_syncing": "⚠️ लाइव स्टॉक डेटा अभी सिंक हो रहा है या गायब है।",
        "audit_db_missing": "ऑडिट लॉग डेटाबेस नहीं मिला। कृपया एडमिन से 'Audit Logs' शीट बनाने को कहें।",
        "audit_progress": "📊 ऑडिट प्रगति",
        "items_audited": "{done} / {total} आइटम गिने गए",
        "count_batches": "गोदाम में बिखरे बैचों की गिनती करें। आपकी एंट्री स्वचालित रूप से जोड़ी जाएंगी।",
        "search_select_item": "गिनने के लिए आइटम खोजें और चुनें:",
        "type_item_name": "आइटम का नाम टाइप करें...",
        "live_item_progress": "### 📊 लाइव आइटम प्रगति",
        "system_expected": "सिस्टम अनुमान",
        "found_so_far": "अब तक मिला",
        "variance": "अंतर",
        "found_so_far_yours": "📦 अब तक मिला (आपकी गिनती)",
        "log_batch": "➕ मिला हुआ बैच दर्ज करें",
        "location_rack": "स्थान / रैक विवरण (वैकल्पिक)",
        "location_rack_ph": "जैसे: गलियारा 3, ऊपरी शेल्फ",
        "qty_found_here": "इस विशिष्ट स्थान पर मिली मात्रा",
        "save_batch": "💾 बैच सहेजें",
        "qty_negative": "मात्रा नकारात्मक नहीं हो सकती।",
        "logged_success": "{item} के लिए {qty} सफलतापूर्वक दर्ज हुआ!",
        "failed_log_audit": "ऑडिट दर्ज करने में विफल: {err}",
        "recent_entries": "**इस आइटम की हाल की एंट्री:**",
        "remaining_items": "📋 गिनने के लिए शेष आइटम",
        "all_audited": "🎉 शानदार काम! सभी इन्वेंटरी आइटम की भौतिक ऑडिट हो गई।",

        # --- AI रीस्टॉक सलाह (ऑडिट रिपोर्ट पेज) ---
        "compare_counts": "कर्मचारियों द्वारा सबमिट की गई भौतिक गिनती की लाइव टैली स्टॉक से तुलना करें।",
        "audit_db_not_found": "ऑडिट लॉग डेटाबेस नहीं मिला।",
        "no_active_audits": "कोई सक्रिय ऑडिट नहीं चल रहा।",
        "archive_audit": "वर्तमान ऑडिट संग्रहित करें",
        "archive_warning": "ऑडिट बोर्ड को संग्रहित करने से सभी आइटम अगली पूर्ण गोदाम गिनती के लिए 'पेंडिंग' पर रीसेट हो जाएंगे।",
        "archive_btn": "ऑडिट संग्रहित करें और रीसेट करें",
        "archive_success": "ऑडिट सफलतापूर्वक संग्रहित हो गया! बोर्ड अब साफ है।",
        "failed_archive": "संग्रहित करने में विफल: {err}",
        "no_audit_logs": "कोई ऑडिट लॉग नहीं मिला।",

        # --- AI रीस्टॉक सलाह (वास्तविक पेज) ---
        "supply_chain_title": "🤖 सप्लाई चेन इंटेलिजेंस",
        "ai_card_title": "🧠 Gemini AI भविष्यवाणी विश्लेषण",
        "ai_card_desc": "नीचे क्लिक करें ताकि Gemini आपकी लाइव इन्वेंटरी का <b>पिछले 15 दिनों की बिक्री</b> और लीड टाइम के साथ विश्लेषण करे और एक प्राथमिकता वाली री-ऑर्डरिंग रिपोर्ट बनाए।",
        "ai_key_missing": "Gemini API Key Secrets में गायब या अमान्य है।",
        "generate_report": "✨ स्मार्ट रीस्टॉक रिपोर्ट बनाएं",
        "ai_spinner": "Gemini बर्न रेट, लीड टाइम और मौजूदा स्टॉक का विश्लेषण कर रहा है...",
        "restock_report_title": "### 📊 भविष्यवाणी रीस्टॉक रिपोर्ट",
        "ai_failed": "AI जनरेशन विफल: {err}",

        # --- एडमिन डैशबोर्ड ---
        "user_mgmt": "⚙️ उपयोगकर्ता प्रबंधन",
        "full_name": "पूरा नाम",
        "create_user_btn": "उपयोगकर्ता बनाएं",
        "user_created": "उपयोगकर्ता बन गया!",
        "role_label": "भूमिका",

        # --- किराया ट्रैकर ---
        "rent_db_error": "⚠️ डेटाबेस त्रुटि: Google Sheets में शीट नहीं मिली।",
        "tab_balances": "📊 बैलेंस और डैशबोर्ड",
        "tab_collect": "💸 भुगतान लें",
        "tab_bills": "⚡ बिल दर्ज करें",
        "tab_history": "📜 इतिहास",
        "tab_manage": "⚙️ किरायेदार प्रबंधन",
        "action_required": "🚨 **आज कार्रवाई आवश्यक:** इनके लिए मासिक बिल बनाएं: **{names}**",
        "active_tenants": "🟢 सक्रिय किरायेदार",
        "no_active_tenants": "अभी कोई सक्रिय किरायेदार नहीं।",
        "due_label": "बकाया: ₹{amt}",
        "advance_label": "अग्रिम: ₹{amt}",
        "cleared_label": "चुकता",
        "pending_dues_label": "बकाया राशि: ₹{amt}",
        "refund_due_label": "वापसी बकाया: ₹{amt}",
        "settled_label": "निपटान हो गया",
        "first_of_month": "महीने की 1 तारीख",
        "date_of_month": "महीने की {day} तारीख",
        "view_vacated": "🚪 खाली किए गए किरायेदार देखें",
        "no_tenants_found": "कोई किरायेदार नहीं मिला। 'किरायेदार प्रबंधन' टैब में जोड़ें।",
        "record_payment": "प्राप्त भुगतान दर्ज करें",
        "select_tenant": "किरायेदार चुनें",
        "payment_amount": "भुगतान राशि प्राप्त (₹)",
        "payment_notes": "नोट्स (जैसे: नकद, UPI संदर्भ, अंतिम निपटान)",
        "save_payment": "💾 भुगतान सहेजें",
        "payment_recorded": "₹{amt} का भुगतान {tenant} के लिए दर्ज हो गया!",
        "generate_charges": "मासिक शुल्क बनाएं",
        "select_tenant_bill": "बिल के लिए किरायेदार चुनें",
        "rent_charge": "##### 🏠 किराया शुल्क",
        "apply_base_rent": "मूल किराया लगाएं (₹{amt})",
        "elec_charge": "##### ⚡ बिजली शुल्क",
        "elec_covered": "बिजली मकान मालिक/कंपनी द्वारा वहन की जाती है।",
        "enter_meter_bill": "💡 उनके लिए भुगतान की गई सटीक मीटर बिल राशि दर्ज करें।",
        "lump_sum_elec": "एकमुश्त बिजली बिल (₹)",
        "passthrough_bill": "किरायेदार खाते में बिल पास करें",
        "last_meter": "अंतिम दर्ज मीटर: **{val}**",
        "current_meter": "वर्तमान मीटर रीडिंग दर्ज करें",
        "calc_usage": "**गणना किया गया उपयोग:** {units} यूनिट (दर: ₹{rate})",
        "apply_var_elec": "वेरिएबल बिजली लगाएं",
        "no_elec_tracking": "बिजली ट्रैकिंग कॉन्फ़िगर नहीं है।",
        "billing_month": "बिलिंग माह / नोट्स (जैसे: 'मार्च 2026 किराया')",
        "post_charges": "📝 शुल्क खाते में दर्ज करें",
        "charges_posted": "शुल्क सफलतापूर्वक किरायेदार के खाते में दर्ज हो गए!",
        "error_posting": "शुल्क दर्ज करने में त्रुटि: {err}",
        "no_active_to_bill": "बिल के लिए कोई सक्रिय किरायेदार नहीं।",
        "ledger_history": "खाता इतिहास",
        "view_history_for": "किसका इतिहास देखें:",
        "all_tenants_hist": "सभी किरायेदार",
        "no_tx_history": "अभी तक कोई लेन-देन इतिहास उपलब्ध नहीं।",
        "add_tenant": "➕ नया किरायेदार जोड़ें",
        "tenant_name": "किरायेदार/कंपनी का नाम",
        "location_unit": "स्थान / यूनिट नंबर",
        "monthly_rent": "मासिक मूल किराया (₹)",
        "security_deposit": "सुरक्षा जमा प्राप्त (₹)",
        "elec_config": "⚡ **बिजली कॉन्फ़िगरेशन**",
        "elec_billing_type": "बिजली बिलिंग प्रकार",
        "rate_per_unit": "प्रति यूनिट दर (₹) - केवल वेरिएबल के लिए",
        "elec_paid_by": "बिजली का भुगतान कौन करता है",
        "initial_meter": "प्रारंभिक मीटर रीडिंग (बेस यूनिट)",
        "billing_cycle": "📅 **बिलिंग चक्र और प्रवेश**",
        "date_keys_given": "चाबी देने की तारीख (बिलिंग शुरू)",
        "billing_logic": "बिलिंग तर्क",
        "pro_rata_option": "प्रो-राटा (हर महीने की 1 तारीख को बिल)",
        "fixed_cycle_option": "फिक्स्ड साइकल (वर्षगांठ तारीख पर बिल)",
        "create_tenant": "किरायेदार प्रोफ़ाइल बनाएं",
        "name_required": "नाम आवश्यक है।",
        "tenant_added_prorata": "किरायेदार जोड़ा गया! ₹{amt} का पहला प्रो-राटा किराया स्वचालित रूप से चार्ज हुआ।",
        "tenant_added_fixed": "किरायेदार जोड़ा गया! बिलिंग हर महीने की {day} तारीख पर सेट है।",
        "edit_vacate": "### ⚙️ मौजूदा किरायेदार संपादित / खाली करें",
        "modify_details": "**विवरण बदलें या बाहर जाने की प्रक्रिया करें**",
        "location_label": "स्थान",
        "monthly_rent_edit": "मासिक किराया (बढ़ाएं/घटाएं)",
        "elec_type": "बिजली प्रकार",
        "per_unit_rate": "प्रति यूनिट दर (वेरिएबल के लिए)",
        "security_held": "सुरक्षा जमा रखी गई",
        "pro_rata_q": "प्रो-राटा बिलिंग?",
        "tenant_status": "किरायेदार स्थिति",
        "save_all": "💾 सभी बदलाव सहेजें",
        "tenant_updated": "{name} की किरायेदार प्रोफ़ाइल अपडेट हो गई!",
        "error_updating": "किरायेदार अपडेट करने में त्रुटि: {err}",
    }
}

# Shortcut variable to make writing code faster (moved here so Login page can use it too)
t = LANG[st.session_state.app_lang]


# ==========================================
# MOBILE-FRIENDLY TOP NAVIGATION
# ==========================================
# Language Toggle Switch (Sits right above the header)
lang_col1, lang_col2 = st.columns([7, 3])
with lang_col2:
    # If toggle is ON, it's Hindi. If OFF, it's English.
    is_hindi = st.session_state.app_lang == "Hindi"
    new_lang_toggle = st.toggle("हिंदी / Eng", value=is_hindi)
    new_lang = "Hindi" if new_lang_toggle else "English"
    
    # If the user flips the switch, save to cookie and reload the app
    if new_lang != st.session_state.app_lang:
        st.session_state.app_lang = new_lang
        cookie_manager.set("mt_lang", new_lang)
        st.rerun()

# Build the page list using our Dictionary (t)
pages = [t["inv"], t["ord"], t["aud"], t["ai"], t["rent"]]

if st.session_state.role == "Admin":
    pages.append(t["rep"])
    pages.append(t["admin"])

# Sleek Top Header Box
st.markdown(f"""
    <div style="display:flex; justify-content:space-between; align-items:center; background:#ffffff; padding:15px; border-radius:12px; border:1px solid #e2e8f0; margin-bottom:15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02);">
        <div style="font-size:18px; font-weight:bold; color:#1e293b;">{t["brand"]}</div>
        <div style="font-size:14px; color:#64748b;">👤 {st.session_state.user_name}</div>
    </div>
""", unsafe_allow_html=True)

# Navigation Dropdown & Action Buttons Row
nav_col, btn1_col, btn2_col = st.columns([5, 3, 2])
with nav_col:
    page = st.selectbox(t["menu"], pages, label_visibility="collapsed")
with btn1_col:
    if st.button(t["refresh"], use_container_width=True):
        st.cache_data.clear()
        st.rerun()
with btn2_col:
    if st.button(t["logout"], use_container_width=True):
        st.session_state.logged_in = False
        cookie_manager.delete("mt_auth")
        cookie_manager.delete("mt_userid")
        st.rerun()

st.divider()

# --- PAGE 1: INVENTORY DASHBOARD ---
if page == t["inv"]:
    st.header(t["inv"])
    if not df.empty:
        col_search, col_filter = st.columns(2)
        with col_search: search_text = st.text_input(t["search_item"], "")
        with col_filter:
            groups = [t["all_groups"]] + df['Group'].dropna().unique().tolist()
            selected_group = st.selectbox(t["filter_group"], groups)

        filtered_df = df.copy()
        if search_text: filtered_df = filtered_df[filtered_df['Item'].str.contains(search_text, case=False, na=False)]
        if selected_group != t["all_groups"]: filtered_df = filtered_df[filtered_df['Group'] == selected_group]

        total_qty = filtered_df['Quantity'].sum()
        m1, m2 = st.columns(2)
        m1.metric(t["volume_filtered"], f"{total_qty:,.0f}")
        m2.metric(t["items_found"], len(filtered_df))

        st.divider()
        tab1, tab2 = st.tabs([t["bar_chart"], t["stock_list"]])

        with tab1:
            if not filtered_df.empty:
                chart_df = filtered_df.sort_values('Quantity', ascending=False)
                display_chart = hindi_df_columns(chart_df, ['Item', 'Group'])
                fig = px.bar(display_chart, x='Item', y='Quantity', color='Group', hover_data=['Display Qty'])
                fig.update_layout(xaxis_tickangle=-45, height=500, plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)

        with tab2:
            sorted_df = filtered_df[['Group', 'Item', 'Quantity', 'Unit']].sort_values(["Group", "Quantity"], ascending=[True, False])
            st.dataframe(hindi_df_columns(sorted_df, ['Group', 'Item']), use_container_width=True, hide_index=True)

# --- PAGE 2: ORDER DESK ---
elif page == t["ord"]:
    st.header(t["ord"])
    orders_df = fetch_orders_cache(orders_sheet)
    
    order_tab1, order_tab2, order_tab3 = st.tabs([t["place_order"], t["pending_orders"], t["completed_orders"]])
    
    with order_tab1:
        # 🟢 THE FIX: Initialize a Master Reset Key
        if 'form_reset' not in st.session_state:
            st.session_state.form_reset = 0
        r_key = st.session_state.form_reset
        
        try:
            cust_data = cust_sheet.get_all_records()
            customer_list = sorted(list(set([str(row['Customer Name']).strip() for row in cust_data if 'Customer Name' in row and str(row['Customer Name']).strip()])))
            if st.session_state.get('app_lang') == 'Hindi':
                customer_list = [hindi(c) for c in customer_list]
        except: customer_list = []
            
        st.subheader(t["create_order"])
        st.write(t["customer_details"])
        
        # Notice how every input now has f"_{r_key}" attached to it!
        customer_dropdown = st.selectbox(t["search_customer"], customer_list, index=None, placeholder=t["search_customer_ph"], key=f"order_cust_drop_{r_key}")
        
        if not customer_dropdown: 
            customer_name = st.text_input(t["new_customer_name"], placeholder=t["new_customer_ph"], key=f"order_cust_text_{r_key}")
        else: 
            customer_name = customer_dropdown
            
        order_notes = st.text_input(t["order_notes_label"], placeholder=t["order_notes_ph"], key=f"order_notes_{r_key}")
        
        st.divider()
        st.write(t["select_items_cart"])
        
        try:
            master_data = master_sheet.get_all_records()
            item_list = sorted([str(row['Item Name']).strip() for row in master_data if 'Item Name' in row])
        except:
            item_list = df['Item'].tolist() if not df.empty else []
        
        # 🟢 Cart-based item adding
        if 'order_cart' not in st.session_state:
            st.session_state.order_cart = {}
        
        # --- ADD ITEM SECTION ---
        st.markdown(f"##### {t.get('add_item_title', '➕ Add Item to Cart')}")
        
        # Filter out items already in cart
        available_items = [i for i in item_list if i not in st.session_state.order_cart]
        display_available = [hindi(i) for i in available_items] if st.session_state.get('app_lang') == 'Hindi' else available_items
        display_to_real_item = dict(zip(display_available, available_items))
        
        pick_display = st.selectbox(
            t.get("pick_item", "🔍 Search & Pick an Item"),
            display_available, index=None,
            placeholder=t.get("pick_item_ph", "Type to search..."),
            key=f"pick_item_{r_key}"
        )
        pick_item = display_to_real_item.get(pick_display) if pick_display else None
        
        if pick_item:
            item_data = df[df['Item'] == pick_item]
            if not item_data.empty:
                avail_qty = item_data['Quantity'].iloc[0]
                unit = item_data['Unit'].iloc[0]
                stock_color = "#4CAF50" if avail_qty > 0 else "#dc3545"
            else:
                avail_qty = 0
                unit = "units"
                stock_color = "#dc3545"
            
            st.markdown(f'<div class="item-banner"><h4 style="margin:0; color: #333;">{hindi(pick_item)}</h4><span style="color: {stock_color}; font-weight: bold;">{t["stock_label"]} {avail_qty:,.0f} {unit}</span></div>', unsafe_allow_html=True)
            st.markdown('<div class="item-inputs">', unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            with c1: qty = st.number_input(f"{t['order_qty']} ({unit})", min_value=1.0, value=1.0, step=1.0, key=f"p_add_{r_key}")
            with c2: alt_qty = st.number_input(t["alt_qty"], min_value=0.0, value=0.0, step=1.0, key=f"a_add_{r_key}")
            with c3: alt_unit = st.text_input(t["alt_unit"], key=f"u_add_{r_key}")
            st.markdown('</div>', unsafe_allow_html=True)
            
            if st.button(t.get("add_to_cart", "➕ Add to Cart"), type="primary", key=f"add_btn_{r_key}"):
                detail_str = f"{qty} {unit}" + (f" (Alt: {alt_qty} {alt_unit})" if alt_qty > 0 and alt_unit else "")
                st.session_state.order_cart[pick_item] = detail_str
                st.rerun()
        
        # --- CART SUMMARY ---
        if st.session_state.order_cart:
            st.divider()
            st.markdown(f"##### 🛒 {t.get('cart_title', 'Your Cart')} ({len(st.session_state.order_cart)} {t.get('cart_items', 'items')})")
            
            for cart_item, cart_detail in list(st.session_state.order_cart.items()):
                ic1, ic2, ic3 = st.columns([5, 4, 1])
                with ic1:
                    st.markdown(f"**{hindi(cart_item)}**")
                with ic2:
                    st.caption(cart_detail)
                with ic3:
                    if st.button("❌", key=f"rm_{cart_item}_{r_key}", help=t.get("remove_item", "Remove")):
                        del st.session_state.order_cart[cart_item]
                        st.rerun()
            
            if st.button(t.get("clear_cart", "🗑️ Clear Cart"), key=f"clear_cart_{r_key}"):
                st.session_state.order_cart = {}
                st.rerun()
        
        order_details_dict = st.session_state.order_cart
        
        if st.button(t["submit_order"], type="primary"):
            if not customer_name or not order_details_dict:
                st.error(t["fill_all_details"])
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
                            table_text_hi = "━━━━━━━━━━━━━━━━━━━━\n"
                            for i in items_array:
                                if ": " in i:
                                    name, q = i.split(": ", 1)
                                    table_text += f"▪️ {name} ➔ {q}\n"
                                    table_text_hi += f"▪️ {hindi(name)} ➔ {q}\n"
                                else:
                                    table_text += f"▪️ {i}\n"
                                    table_text_hi += f"▪️ {hindi(i)}\n"
                            table_text += "━━━━━━━━━━━━━━━━━━━━\n"
                            table_text_hi += "━━━━━━━━━━━━━━━━━━━━\n"
                            
                            alert_text = "🚨 NEW ORDER ALERT 🚨\n\n"
                            alert_text += f"🆔 {order_id}\n👤 {customer_name}\n\n{table_text}"
                            if order_notes and str(order_notes).strip(): alert_text += f"\n📝 Notes: {order_notes}\n"
                            alert_text += f"\n✅ Placed By: {st.session_state.user_name}"
                            
                            # Hindi translation section
                            alert_text += "\n\n── हिंदी अनुवाद ──\n"
                            alert_text += f"🚨 नया ऑर्डर 🚨\n"
                            alert_text += f"🆔 {order_id}\n👤 {hindi(customer_name)}\n\n{table_text_hi}"
                            if order_notes and str(order_notes).strip(): alert_text += f"📝 नोट: {hindi(str(order_notes))}\n"
                            alert_text += f"✅ द्वारा: {st.session_state.user_name}"
                            
                            encoded_text = urllib.parse.quote(alert_text)
                            res = requests.get(f"https://api.telegram.org/bot{tg_token}/sendMessage?chat_id={tg_chat_id}&text={encoded_text}")
                            
                            if res.status_code == 200:
                                tg_success = True
                            else:
                                st.error(t["tg_failed"].format(err=res.text))
                        else:
                            st.error(t["tg_keys_missing"])
                    except Exception as tg_e:
                        st.error(t["tg_system_error"].format(err=tg_e))
                    
                    if tg_success:
                        st.success(t["order_placed_tg"].format(oid=order_id))
                    else:
                        st.success(t["order_placed_db"].format(oid=order_id))

                    # 🟢 THE UNIFIED FIX: Advance the reset key AND clear the memory cache!
                    st.session_state.form_reset += 1
                    fetch_orders_cache.clear()
                            
                    time.sleep(1.5)
                    st.rerun()
                except Exception as e: 
                    st.error(t["error_saving_order"].format(err=e))
                    

    with order_tab2:
        if not orders_df.empty and 'Status' in orders_df.columns:
            pending_df = orders_df[orders_df['Status'] == 'Pending'].iloc[::-1]
            for idx, row in pending_df.iterrows():
                st.markdown(f'<div class="order-card"><h4 style="margin-top:0; color:#0056b3;">Order {row["Order ID"]}</h4><b>Customer:</b> {hindi(str(row["Customer Name"]))}<br><b>Notes:</b> {hindi(str(row.get("Notes", "None")))}<br>{generate_html_table(row["Order Details"])}</div>', unsafe_allow_html=True)
                
                c1, c2 = st.columns([1, 1])
                with c1:
                    if st.button(t["mark_complete"], key=f"btn_{row['Order ID']}_{idx}"):
                        try:
                            cell = orders_sheet.find(row['Order ID'])
                            orders_sheet.update_cell(cell.row, 5, 'Completed')
                            orders_sheet.update_cell(cell.row, 6, st.session_state.user_name)
                            
                            try:
                                tg_token = st.secrets.get("TELEGRAM_BOT_TOKEN")
                                tg_chat_id = st.secrets.get("TELEGRAM_CHAT_ID")
                                if tg_token and tg_chat_id:
                                    comp_text = f"✅ *ORDER COMPLETED* ✅\n\n🆔 {row['Order ID']}\n👤 {row['Customer Name']}\n👷 Completed By: {st.session_state.user_name}"
                                    comp_text += f"\n\n── हिंदी ──\n✅ *ऑर्डर पूरा* ✅\n\n🆔 {row['Order ID']}\n👤 {hindi(str(row['Customer Name']))}\n👷 पूरा किया: {st.session_state.user_name}"
                                    encoded_comp = urllib.parse.quote(comp_text)
                                    requests.get(f"https://api.telegram.org/bot{tg_token}/sendMessage?chat_id={tg_chat_id}&text={encoded_comp}")
                            except: pass
                            
                            st.success(t["order_completed"])
                            time.sleep(1)
                            fetch_orders_cache.clear()
                            st.rerun()
                        except Exception as e: st.error(f"Error: {e}")
                with c2:
                    pdf_data = create_order_pdf(row)
                    st.download_button(t["share_pdf"], data=pdf_data, file_name=f"Order_{row['Order ID']}.pdf", mime="application/pdf", key=f"pdf_{row['Order ID']}_{idx}")

                with st.expander(t["modify_delete"]):
                    mod_cust = st.text_input(t["customer_name_label"], str(row['Customer Name']), key=f"mcust_{row['Order ID']}_{idx}")
                    
                    current_items = {}
                    for chunk in str(row['Order Details']).split(" | "):
                        if ": " in chunk:
                            k, v = chunk.split(": ", 1)
                            current_items[k.strip()] = v.strip()
                            
                    all_items = df['Item'].dropna().unique().tolist() if not df.empty else []
                    for k in current_items.keys():
                        if k not in all_items: all_items.append(k)
                            
                    st.write(t["modify_items"])
                    mod_selected_items = st.multiselect(
                        t["add_remove_items"],
                        options=all_items,
                        default=list(current_items.keys()),
                        key=f"mitems_{row['Order ID']}_{idx}"
                    )
                    
                    new_order_dict = {}
                    for item in mod_selected_items:
                        default_qty = current_items.get(item, "1.0 units")
                        new_qty = st.text_input(t["qty_details_for"].format(item=item), value=default_qty, key=f"mqty_{row['Order ID']}_{idx}_{item}")
                        new_order_dict[item] = new_qty
                        
                    mod_notes = st.text_input(t["notes_label"], str(row.get('Notes', '')), key=f"mnot_{row['Order ID']}_{idx}")
                    
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        if st.button(t["save_changes"], type="primary", key=f"msave_{row['Order ID']}_{idx}"):
                            reconstructed_details = " | ".join([f"{k}: {v}" for k, v in new_order_dict.items()])
                            if not reconstructed_details:
                                st.error("You must have at least one item in the order.")
                            else:
                                try:
                                    cell = orders_sheet.find(row['Order ID'])
                                    orders_sheet.update_cell(cell.row, 3, mod_cust)
                                    orders_sheet.update_cell(cell.row, 4, reconstructed_details)
                                    orders_sheet.update_cell(cell.row, 7, mod_notes)
                                    st.success(t["order_updated"])
                                    time.sleep(1)
                                    fetch_orders_cache.clear()
                                    st.rerun()
                                except Exception as e: st.error(t["failed_update"].format(err=e))
                    with ec2:
                        if st.button(t["delete_order"], key=f"mdel_{row['Order ID']}_{idx}"):
                            try:
                                cell = orders_sheet.find(row['Order ID'])
                                orders_sheet.delete_rows(cell.row)
                                st.warning(t["order_deleted"])
                                time.sleep(1)
                                fetch_orders_cache.clear()
                                st.rerun()
                            except Exception as e: st.error(t["failed_delete"].format(err=e))

    with order_tab3:
        if not orders_df.empty and 'Status' in orders_df.columns:
            completed_df = orders_df[orders_df['Status'] == 'Completed'].copy()
            completed_df['Parsed Date'] = pd.to_datetime(completed_df['Date'], format="%d-%m-%Y %I:%M %p", errors='coerce').dt.date
            
            with st.expander(t["adv_filters"]):
                fc1, fc2, fc3, fc4 = st.columns(4)
                
                with fc1:
                    search_query = st.text_input(t["search_name_id"], placeholder=t["search_eg"], key="search_comp")
                
                with fc2:
                    min_date = completed_df['Parsed Date'].dropna().min() if not completed_df['Parsed Date'].dropna().empty else datetime.today().date()
                    max_date = completed_df['Parsed Date'].dropna().max() if not completed_df['Parsed Date'].dropna().empty else datetime.today().date()
                    date_filter = st.date_input(t["date_range"], value=(), min_value=min_date, max_value=max_date, key="date_comp")
                
                with fc3:
                    emp_list = [t["all_employees"]] + sorted(completed_df['Completed By'].dropna().unique().tolist())
                    emp_filter = st.selectbox(t["completed_by"], emp_list, key="emp_comp")
                    
                with fc4:
                    item_list = [t["all_items_filter"]] + df['Item'].dropna().unique().tolist() if not df.empty else [t["all_items_filter"]]
                    item_filter = st.selectbox(t["contains_fabric"], item_list, key="item_comp")
                    
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
                
            if emp_filter != t["all_employees"]:
                filtered_df = filtered_df[filtered_df['Completed By'] == emp_filter]
                
            if item_filter != t["all_items_filter"]:
                filtered_df = filtered_df[filtered_df['Order Details'].astype(str).str.contains(item_filter, case=False, na=False)]

            filtered_df = filtered_df.iloc[::-1]
            st.markdown(f"<p style='color: #64748b; font-size: 14px;'>{t['showing_completed'].format(count=len(filtered_df))}</p>", unsafe_allow_html=True)

            for idx, row in filtered_df.iterrows():
                cb = row.get('Completed By', 'Unknown')
                st.markdown(f'<div class="completed-card order-card"><h4 style="margin-top:0; color:#10b981;">Order {row["Order ID"]}</h4><b>Customer:</b> {hindi(str(row["Customer Name"]))}<br><b>Notes:</b> {hindi(str(row.get("Notes", "None")))}<br>{generate_html_table(row["Order Details"])}<hr><span style="color: #6c757d;">✅ Completed by: <b>{cb}</b> on {row.get("Date", "")}</span></div>', unsafe_allow_html=True)
                
                c1, c2 = st.columns([1, 1])
                with c1:
                    pdf_data = create_order_pdf(row)
                    st.download_button(t["download_receipt"], data=pdf_data, file_name=f"Receipt_{row['Order ID']}.pdf", mime="application/pdf", key=f"pdf_comp_{row['Order ID']}_{idx}")
                with c2:
                    if st.session_state.role == "Admin":
                        if st.button(t["delete_record"], key=f"del_comp_{row['Order ID']}_{idx}"):
                            try:
                                cell = orders_sheet.find(row['Order ID'])
                                orders_sheet.delete_rows(cell.row)
                                st.warning(t["record_deleted"])
                                time.sleep(1)
                                st.rerun()
                            except Exception as e: st.error(t["failed_delete"].format(err=e))

# --- PAGE 3: STOCK AUDIT (EMPLOYEE VIEW) ---
elif page == t["aud"]:
    st.header(t["aud"])
    
    with st.expander(t["view_system_qty"]):
        if not df.empty and all(c in df.columns for c in ['Group', 'Item', 'Quantity', 'Unit']):
            st.dataframe(hindi_df_columns(df[['Group', 'Item', 'Quantity', 'Unit']].sort_values(["Group", "Quantity"], ascending=[True, False]), ['Group', 'Item']), use_container_width=True, hide_index=True)
        else:
            st.warning(t["stock_syncing"])
    
    if not audit_sheet:
        st.error(t["audit_db_missing"])
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
        
        st.metric(t["audit_progress"], t["items_audited"].format(done=len(audited_items), total=len(all_items)))
        st.progress(len(audited_items) / len(all_items) if len(all_items) > 0 else 0.0)
        
        st.divider()
        st.write(t["count_batches"])

        display_items = [hindi(i) for i in all_items] if st.session_state.get('app_lang') == 'Hindi' else all_items
        display_to_real = dict(zip(display_items, all_items))
        audit_item_display = st.selectbox(t["search_select_item"], display_items, index=None, placeholder=t["type_item_name"])
        audit_item = display_to_real.get(audit_item_display) if audit_item_display else None
        
        if audit_item:
            item_audits = active_audit[active_audit['Item Name'] == audit_item]
            found_so_far = pd.to_numeric(item_audits['Quantity Found'], errors='coerce').sum() if not item_audits.empty else 0
            
            st.markdown(t["live_item_progress"])
            if st.session_state.role == "Admin":
                system_qty = df[df['Item'] == audit_item]['Quantity'].iloc[0] if not df.empty else 0
                variance = found_so_far - system_qty
                
                c1, c2, c3 = st.columns(3)
                c1.metric(t["system_expected"], f"{system_qty:,.0f}")
                c2.metric(t["found_so_far"], f"{found_so_far:,.0f}")
                c3.metric(t["variance"], f"{variance:,.0f}", delta_color="inverse")
            else:
                st.metric(t["found_so_far_yours"], f"{found_so_far:,.0f}")
            
            st.divider()
            
            st.subheader(t["log_batch"])
            with st.form("audit_form", clear_on_submit=True):
                loc = st.text_input(t["location_rack"], placeholder=t["location_rack_ph"])
                qty = st.number_input(t["qty_found_here"], min_value=0.0, step=1.0)
                submit_batch = st.form_submit_button(t["save_batch"], type="primary")
                
                if submit_batch:
                    if qty < 0:
                        st.error(t["qty_negative"])
                    else:
                        timestamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
                        try:
                            audit_sheet.append_row([timestamp, audit_item, loc, qty, st.session_state.user_name, "Active"])
                            st.success(t["logged_success"].format(qty=qty, item=audit_item))
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(t["failed_log_audit"].format(err=e))
                            
            if not item_audits.empty:
                st.markdown(t["recent_entries"])
                st.dataframe(item_audits[['Location', 'Quantity Found', 'Employee Name', 'Timestamp']].iloc[::-1], hide_index=True)

        st.divider()
        st.subheader(t["remaining_items"])
        if remaining_items:
            rem_df = df[df['Item'].isin(remaining_items)][['Group', 'Item']].sort_values(["Group", "Item"])
            st.dataframe(hindi_df_columns(rem_df, ['Group', 'Item']), use_container_width=True, hide_index=True)
        else:
            st.success(t["all_audited"])

# --- PAGE 4: AUDIT REPORT (ADMIN ONLY) ---
elif page == t["rep"]:
    st.header(t["rep"])
    st.write(t["compare_counts"])
    
    if not audit_sheet:
        st.error(t["audit_db_not_found"])
    else:
        try:
            audit_data = audit_sheet.get_all_records()
            audit_df = pd.DataFrame(audit_data)
        except:
            audit_df = pd.DataFrame()
            
        if not audit_df.empty and 'Status' in audit_df.columns:
            active_audit = audit_df[audit_df['Status'] == 'Active']
            
            if active_audit.empty:
                st.info(t["no_active_audits"])
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
                st.subheader(t["archive_audit"])
                st.warning(t["archive_warning"])
                
                if st.button(t["archive_btn"], type="primary"):
                    try:
                        cell_list = audit_sheet.findall("Active")
                        for cell in cell_list:
                            if cell.col == 6:
                                audit_sheet.update_cell(cell.row, 6, "Closed")
                        st.success(t["archive_success"])
                        time.sleep(2)
                        st.rerun()
                    except Exception as e:
                        st.error(t["failed_archive"].format(err=e))
        else:
            st.info(t["no_audit_logs"])

# --- PAGE 5: AI RESTOCK ADVISOR ---
elif page == t["ai"]:
    st.title(t["supply_chain_title"])
    st.markdown(f'<div class="ai-card"><h4>{t["ai_card_title"]}</h4><p>{t["ai_card_desc"]}</p></div>', unsafe_allow_html=True)
    
    if not ai_model:
        st.error(t["ai_key_missing"])
    else:
        if st.button(t["generate_report"], type="primary"):
            with st.spinner(t["ai_spinner"]):
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
                    st.markdown(t["restock_report_title"])
                    st.write(response.text)
                except Exception as e:
                    st.error(t["ai_failed"].format(err=e))

# --- PAGE 6: ADMIN DASHBOARD ---
elif page == t["admin"]:
    st.title(t["user_mgmt"])
    with st.form("add_user_form"):
        new_name, new_id, new_pass, new_role = st.text_input(t["full_name"]), st.text_input(t["user_id"]), st.text_input(t["password"], type="password"), st.selectbox(t["role_label"], ["Employee", "Admin"])
        if st.form_submit_button(t["create_user_btn"]) and new_name and new_id and new_pass:
            users_sheet.append_row([new_id, new_pass, new_role, new_name])
            st.success(t["user_created"])
    
    try: st.dataframe(pd.DataFrame(users_sheet.get_all_records())[['User ID', 'Name', 'Role']], use_container_width=True)
    except: pass

# --- PAGE 7: RENT TRACKER ---
elif page == t["rent"]:
    st.header(t["rent"])
    
    if tenants_sheet is None or rent_tx_sheet is None:
        st.error(t["rent_db_error"])
    else:
        # 1. Fetch data safely using the new named caches
        df_tenants_raw = fetch_rent_cache(tenants_sheet, "Tenants")
        df_tx_raw = fetch_rent_cache(rent_tx_sheet, "Rent Transactions")

        df_tenants = df_tenants_raw.copy()
        df_tx = df_tx_raw.copy()

        # 2. Clean Headers (Remove invisible spaces)
        if not df_tenants.empty: df_tenants.columns = df_tenants.columns.str.strip()
        if not df_tx.empty: df_tx.columns = df_tx.columns.str.strip()

        # 3. SAFETY NET: Auto-fill missing new columns so old data doesn't crash the app
        if not df_tenants.empty:
            if 'Billing Start Date' not in df_tenants.columns: df_tenants['Billing Start Date'] = datetime.now(IST).strftime('%Y-%m-%d')
            if 'Pro Rata' not in df_tenants.columns: df_tenants['Pro Rata'] = 'Yes'
            if 'Status' not in df_tenants.columns: df_tenants['Status'] = 'Active'

        # 4. BULLETPROOF MATH CALCULATION
        balances = {}
        if not df_tenants.empty and not df_tx.empty and 'Amount' in df_tx.columns and 'Tenant Name' in df_tx.columns:
            calc_tx = df_tx.copy()
            calc_tx['Tenant Name'] = calc_tx['Tenant Name'].astype(str).str.strip()
            calc_tx['Type'] = calc_tx['Type'].astype(str).str.strip()
            
            calc_tx['Safe Amount'] = calc_tx['Amount'].astype(str).str.replace(r'[^\d.]', '', regex=True)
            calc_tx['Safe Amount'] = pd.to_numeric(calc_tx['Safe Amount'], errors='coerce').fillna(0.0)
            
            clean_tenants = df_tenants['Name'].astype(str).str.strip().dropna().unique()
            
            for t_name in clean_tenants:
                t_tx = calc_tx[calc_tx['Tenant Name'] == t_name]
                charges = t_tx[t_tx['Type'].str.contains('Charge', case=False, na=False)]['Safe Amount'].sum()
                payments = t_tx[t_tx['Type'].str.contains('Payment', case=False, na=False)]['Safe Amount'].sum()
                balances[t_name] = charges - payments
                
        elif not df_tenants.empty and 'Name' in df_tenants.columns:
            for t_name in df_tenants['Name'].astype(str).str.strip().dropna().unique(): 
                balances[t_name] = 0.0

        tab1, tab2, tab3, tab4, tab5 = st.tabs([t["tab_balances"], t["tab_collect"], t["tab_bills"], t["tab_history"], t["tab_manage"]])

        # TAB 1: DASHBOARD & BALANCES
        # TAB 1: DASHBOARD & BALANCES
        with tab1:
            if not df_tenants.empty:
                active_tenants = df_tenants[df_tenants['Status'] == 'Active']
                vacated_tenants = df_tenants[df_tenants['Status'] == 'Vacated']
                today = datetime.now(IST).date()
                
                # SMART BILLING REMINDER SYSTEM
                reminders = []
                for idx, row in active_tenants.iterrows():
                    pr_status = str(row.get('Pro Rata', 'Yes')).strip()
                    sd_str = str(row.get('Billing Start Date', str(today)))
                    try: sd_date = datetime.strptime(sd_str, "%Y-%m-%d").date()
                    except: sd_date = today
                    
                    due_day = 1 if pr_status == 'Yes' else sd_date.day
                    if today.day == due_day:
                        reminders.append(str(row['Name']).strip())
                
                if reminders:
                    st.error(t["action_required"].format(names=', '.join(reminders)))
                
                st.subheader(t["active_tenants"])
                if active_tenants.empty: st.info(t["no_active_tenants"])
                
                for idx, row in active_tenants.iterrows():
                    t_name = str(row['Name']).strip()
                    bal = balances.get(t_name, 0.0)
                    
                    # 🟢 THE NEW ADVANCE LOGIC
                    if bal > 0:
                        status_color = "#dc3545" # Red
                        status_text = t["due_label"].format(amt=f"{bal:,.2f}")
                    elif bal < 0:
                        status_color = "#0284c7" # Blue
                        status_text = t["advance_label"].format(amt=f"{abs(bal):,.2f}")
                    else:
                        status_color = "#10b981" # Green
                        status_text = t["cleared_label"]
                    
                    try: sec_dep = float(row.get('Security Deposit', 0.0))
                    except (ValueError, TypeError): sec_dep = 0.0
                    
                    pr_txt = t["first_of_month"] if str(row.get('Pro Rata', 'Yes')).strip() == 'Yes' else t["date_of_month"].format(day=datetime.strptime(str(row.get('Billing Start Date', str(today))), '%Y-%m-%d').day)
                    
                    st.markdown(f"""
                    <div class="order-card">
                        <h4 style="margin:0; color:#333;">{t_name} <span style="float:right; color:{status_color};">{status_text}</span></h4>
                        <p style="margin:5px 0 0 0; color:#64748b;">
                            📍 {row.get('Location', 'N/A')} | 🏠 Rent: ₹{row.get('Rent Amount', 0)} | ⚡ Elec: {row.get('Electricity Type', 'N/A')}<br>
                            <span style="color: #0284c7; font-weight: 500;">🛡️ Security: ₹{sec_dep:,.2f}</span> | 📅 Cycle: {pr_txt}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                
                if not vacated_tenants.empty:
                    with st.expander(t["view_vacated"]):
                        for idx, row in vacated_tenants.iterrows():
                            t_name = str(row['Name']).strip()
                            bal = balances.get(t_name, 0.0)
                            
                            # 🟢 ADVANCE LOGIC FOR VACATED TENANTS (Refunds)
                            if bal > 0:
                                color = "#dc3545"
                                txt = t["pending_dues_label"].format(amt=f"{bal:,.2f}")
                            elif bal < 0:
                                color = "#0284c7"
                                txt = t["refund_due_label"].format(amt=f"{abs(bal):,.2f}")
                            else:
                                color = "#6c757d"
                                txt = t["settled_label"]
                                
                            st.markdown(f"**{t_name}** | {row.get('Location', '')} | <span style='color:{color}'>{txt}</span>", unsafe_allow_html=True)
            else:
                st.info(t["no_tenants_found"])

        # TAB 2: COLLECT PAYMENT
        with tab2:
            st.subheader(t["record_payment"])
            if not df_tenants.empty:
                with st.form("payment_form", clear_on_submit=True):
                    clean_tenant_names = df_tenants['Name'].astype(str).str.strip().tolist()
                    p_tenant = st.selectbox(t["select_tenant"], clean_tenant_names)
                    p_amt = st.number_input(t["payment_amount"], min_value=1.0, step=100.0)
                    p_notes = st.text_input(t["payment_notes"])
                    
                    if st.form_submit_button(t["save_payment"], type="primary"):
                        timestamp = datetime.now(IST).strftime("%d-%m-%Y %I:%M %p")
                        rent_tx_sheet.append_row([timestamp, p_tenant, "Payment", "Rent", float(p_amt), "", p_notes, st.session_state.user_name])
                        st.success(t["payment_recorded"].format(amt=p_amt, tenant=p_tenant))
                        fetch_rent_cache.clear()
                        time.sleep(1)
                        st.rerun()

        # TAB 3: LOG BILLS (RENT & ELECTRICITY)
        with tab3:
            st.subheader(t["generate_charges"])
            if not df_tenants.empty:
                active_only = df_tenants[df_tenants['Status'] == 'Active'].copy()
                if not active_only.empty:
                    active_only['Name'] = active_only['Name'].astype(str).str.strip()
                    bill_tenant = st.selectbox(t["select_tenant_bill"], active_only['Name'].tolist(), key="bill_t")
                    t_data = active_only[active_only['Name'] == bill_tenant].iloc[0]
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(t["rent_charge"])
                        try: base_rent = float(t_data.get('Rent Amount', 0.0))
                        except (ValueError, TypeError): base_rent = 0.0
                        charge_rent = st.checkbox(t["apply_base_rent"].format(amt=base_rent), value=True)
                    
                    with c2:
                        st.markdown(t["elec_charge"])
                        e_type = str(t_data.get('Electricity Type', 'None')).strip()
                        try: e_rate = float(t_data.get('Elec Rate', 0.0))
                        except (ValueError, TypeError): e_rate = 0.0
                        
                        units = 0.0
                        new_meter = 0.0
                        e_amt_final = 0.0
                        
                        if str(t_data.get('Elec Paid By', '')).strip() == 'Company/Landlord' and e_type not in ['Fixed', 'Direct Bill (Lump Sum)']:
                            st.info(t["elec_covered"])
                            charge_elec = False
                            
                        elif e_type in ['Fixed', 'Direct Bill (Lump Sum)']:
                            st.info(t["enter_meter_bill"])
                            e_amt_input = st.number_input(t["lump_sum_elec"], min_value=0.0, step=100.0, value=0.0)
                            charge_elec = st.checkbox(t["passthrough_bill"], value=True)
                            e_amt_final = e_amt_input
                            
                        elif e_type in ['Variable', 'Variable (Meter)']:
                            try: prev_meter = float(t_data.get('Meter Reading', 0.0))
                            except (ValueError, TypeError): prev_meter = 0.0
                            
                            st.info(t["last_meter"].format(val=prev_meter))
                            new_meter = st.number_input(t["current_meter"], min_value=prev_meter, step=1.0, value=prev_meter)
                            units = new_meter - prev_meter
                            st.write(t["calc_usage"].format(units=units, rate=e_rate))
                            charge_elec = st.checkbox(t["apply_var_elec"], value=True)
                            e_amt_final = e_rate * units
                        else:
                            st.write(t["no_elec_tracking"])
                            charge_elec = False

                    bill_notes = st.text_input(t["billing_month"], key="bill_n")

                    if st.button(t["post_charges"], type="primary"):
                        timestamp = datetime.now(IST).strftime("%d-%m-%Y %I:%M %p")
                        try:
                            if charge_rent:
                                rent_tx_sheet.append_row([timestamp, bill_tenant, "Charge", "Rent", base_rent, "", bill_notes, st.session_state.user_name])
                            
                            if charge_elec and e_amt_final > 0:
                                rent_tx_sheet.append_row([timestamp, bill_tenant, "Charge", "Electricity", float(e_amt_final), float(units) if units > 0 else "", bill_notes, st.session_state.user_name])
                                if e_type in ['Variable', 'Variable (Meter)']:
                                    t_cell = tenants_sheet.find(str(t_data['Tenant ID']))
                                    tenants_sheet.update_cell(t_cell.row, 8, float(new_meter))
                                        
                            st.success(t["charges_posted"])
                            fetch_rent_cache.clear()
                            time.sleep(1.5)
                            st.rerun()
                        except Exception as e: st.error(t["error_posting"].format(err=e))
                else:
                    st.info(t["no_active_to_bill"])

        # TAB 4: TRANSACTION HISTORY
        with tab4:
            st.subheader(t["ledger_history"])
            if not df_tenants.empty and not df_tx.empty and 'Tenant Name' in df_tx.columns:
                clean_tenant_list = df_tenants['Name'].astype(str).str.strip().tolist()
                hist_tenant = st.selectbox(t["view_history_for"], [t["all_tenants_hist"]] + clean_tenant_list)
                
                hist_df = df_tx.copy()
                hist_df['Tenant Name'] = hist_df['Tenant Name'].astype(str).str.strip()
                
                if hist_tenant != t["all_tenants_hist"]:
                    hist_df = hist_df[hist_df['Tenant Name'] == hist_tenant]
                
                hist_df = hist_df.dropna(how='all')
                hist_df = hist_df.iloc[::-1]
                
                if 'Type' in hist_df.columns:
                    hist_df['Type'] = hist_df['Type'].astype(str).str.strip()
                    st.dataframe(hist_df.style.map(lambda x: 'color: #dc3545; font-weight:bold;' if x == 'Charge' else 'color: #10b981; font-weight:bold;' if x == 'Payment' else '', subset=['Type']), use_container_width=True, hide_index=True)
                else:
                    st.dataframe(hist_df, use_container_width=True, hide_index=True)
            else:
                st.info(t["no_tx_history"])

        # TAB 5: MANAGE TENANTS (Add/Edit)
        with tab5:
            with st.expander(t["add_tenant"], expanded=False):
                with st.form("add_tenant_form", clear_on_submit=True):
                    t_id = f"T-{uuid.uuid4().hex[:6].upper()}"
                    nt_name = st.text_input(t["tenant_name"])
                    nt_loc = st.text_input(t["location_unit"])
                    
                    c1, c2 = st.columns(2)
                    with c1: nt_rent = st.number_input(t["monthly_rent"], min_value=0.0, step=500.0)
                    with c2: nt_security = st.number_input(t["security_deposit"], min_value=0.0, step=500.0)
                    
                    st.write(t["elec_config"])
                    nt_etype = st.selectbox(t["elec_billing_type"], ["Direct Bill (Lump Sum)", "Variable (Meter)", "None"])
                    nt_erate = st.number_input(t["rate_per_unit"], min_value=0.0, step=1.0)
                    nt_epaid = st.selectbox(t["elec_paid_by"], ["Tenant", "Company/Landlord"])
                    
                    nt_meter = 0.0
                    if nt_etype == "Variable (Meter)":
                        nt_meter = st.number_input(t["initial_meter"], min_value=0.0, step=1.0)
                        
                    st.divider()
                    st.write(t["billing_cycle"])
                    k1, k2 = st.columns(2)
                    with k1: start_date = st.date_input(t["date_keys_given"])
                    with k2: apply_prorata = st.selectbox(t["billing_logic"], [t["pro_rata_option"], t["fixed_cycle_option"]])
                    pr_val = "Yes" if t["pro_rata_option"] in apply_prorata else "No"
                    
                    if st.form_submit_button(t["create_tenant"], type="primary"):
                        if nt_name:
                            tenants_sheet.append_row([t_id, nt_name, nt_loc, float(nt_rent), nt_etype, float(nt_erate), nt_epaid, float(nt_meter), float(nt_security), str(start_date), pr_val, "Active"])
                            
                            if pr_val == "Yes" and nt_rent > 0:
                                now = datetime.now(IST)
                                days_in_month = calendar.monthrange(now.year, now.month)[1]
                                days_active = days_in_month - start_date.day + 1
                                pro_rata_rent = round((float(nt_rent) / days_in_month) * days_active, 2)
                                
                                timestamp = now.strftime("%d-%m-%Y %I:%M %p")
                                rent_tx_sheet.append_row([
                                    timestamp, nt_name, "Charge", "Rent (Pro-Rata)", float(pro_rata_rent), "",
                                    f"Pro-rata rent for {days_active} days in {now.strftime('%b %Y')}", st.session_state.user_name
                                ])
                                st.success(t["tenant_added_prorata"].format(amt=pro_rata_rent))
                            else:
                                st.success(t["tenant_added_fixed"].format(day=start_date.day))
                                
                            fetch_rent_cache.clear()
                            time.sleep(2)
                            st.rerun()
                        else: st.error(t["name_required"])
            
            st.markdown(t["edit_vacate"])
            if not df_tenants.empty:
                for idx, row in df_tenants.iterrows():
                    curr_status = str(row.get('Status', 'Active')).strip()
                    icon = "🟢" if curr_status == 'Active' else "🚪"
                    with st.expander(f"{icon} {row['Name']} ({row.get('Location', '')})"):
                        with st.form(f"edit_form_{idx}"):
                            st.write(t["modify_details"])
                            
                            c1, c2 = st.columns(2)
                            with c1: e_loc = st.text_input(t["location_label"], str(row.get('Location', '')))
                            with c2: e_rent = st.number_input(t["monthly_rent_edit"], value=float(row.get('Rent Amount', 0.0)), step=500.0)
                            
                            e1, e2 = st.columns(2)
                            old_etype = str(row.get('Electricity Type', 'None')).strip()
                            etype_idx = 0 if old_etype in ['Fixed', 'Direct Bill (Lump Sum)'] else 1 if old_etype in ['Variable', 'Variable (Meter)'] else 2
                            
                            with e1: e_etype_new = st.selectbox(t["elec_type"], ["Direct Bill (Lump Sum)", "Variable (Meter)", "None"], index=etype_idx)
                            with e2: e_rate = st.number_input(t["per_unit_rate"], value=float(row.get('Elec Rate', 0.0)), step=1.0)
                            
                            s1, s2, s3 = st.columns(3)
                            with s1: e_sec = st.number_input(t["security_held"], value=float(row.get('Security Deposit', 0.0)), step=500.0)
                            with s2: e_prorata = st.selectbox(t["pro_rata_q"], ["Yes", "No"], index=0 if str(row.get('Pro Rata', 'Yes')).strip() == 'Yes' else 1)
                            with s3: e_status = st.selectbox(t["tenant_status"], ["Active", "Vacated"], index=0 if curr_status == 'Active' else 1)
                            
                            if st.form_submit_button(t["save_all"], type="primary"):
                                try:
                                    cell = tenants_sheet.find(str(row['Tenant ID']))
                                    tenants_sheet.update_cell(cell.row, 3, e_loc)
                                    tenants_sheet.update_cell(cell.row, 4, float(e_rent))
                                    tenants_sheet.update_cell(cell.row, 5, e_etype_new)
                                    tenants_sheet.update_cell(cell.row, 6, float(e_rate))
                                    tenants_sheet.update_cell(cell.row, 9, float(e_sec))
                                    tenants_sheet.update_cell(cell.row, 11, e_prorata)
                                    tenants_sheet.update_cell(cell.row, 12, e_status)
                                    
                                    st.success(t["tenant_updated"].format(name=row['Name']))
                                    fetch_rent_cache.clear()
                                    time.sleep(1)
                                    st.rerun()
                                except Exception as e:
                                    st.error(t["error_updating"].format(err=e))























