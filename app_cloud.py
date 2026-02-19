import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURATION ---
# PASTE YOUR CSV LINK HERE:
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSGCN0vX5T-HTyvx1Bkbm8Jm8QlQrZRgYj_0_E2kKX7UKQvE12oVQ0s-QZqkct7Ev6c0sp3Bqx82JQR/pub?output=csv"

st.set_page_config(page_title="Dragon Fly Inventory", layout="wide", page_icon="🐉")

# --- LOAD DATA ---
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

# --- HEADER ---
c1, c2 = st.columns([3, 1])
with c1:
    st.title("🐉 Dragon Fly Physical Inventory")
with c2:
    if st.button("🔄 Force Refresh"):
        st.cache_data.clear()
        st.rerun()

if not df.empty:
    # --- GLOBAL SEARCH & FILTER ---
    st.markdown("### 🔍 Search & Filter")
    col_search, col_filter = st.columns(2)
    
    with col_search:
        search_text = st.text_input("Search for an Item by name...", "")
    with col_filter:
        groups = ["All Groups"] + df['Group'].dropna().unique().tolist()
        selected_group = st.selectbox("Filter by Stock Group:", groups)

    # Apply the filters
    filtered_df = df.copy()
    if search_text:
        filtered_df = filtered_df[filtered_df['Item'].str.contains(search_text, case=False, na=False)]
    if selected_group != "All Groups":
        filtered_df = filtered_df[filtered_df['Group'] == selected_group]

    # Recalculate metrics based on what is currently filtered
    total_qty = filtered_df['Quantity'].sum()
    top_group = filtered_df.groupby('Group')['Quantity'].sum().idxmax() if not filtered_df.empty else "N/A"
    
    # METRICS
    m1, m2, m3 = st.columns(3)
    m1.metric("📦 Volume (Filtered)", f"{total_qty:,.0f} units")
    m2.metric("📂 Top Group (Filtered)", top_group)
    m3.metric("📋 Items Found", len(filtered_df))

    st.divider()

    # --- TABS
