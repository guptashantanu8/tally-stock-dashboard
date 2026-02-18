import streamlit as st
import pandas as pd
import time

# --- CONFIGURATION ---
# PASTE YOUR "PUBLISH TO WEB" CSV LINK HERE:
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSGCN0vX5T-HTyvx1Bkbm8Jm8QlQrZRgYj_0_E2kKX7UKQvE12oVQ0s-QZqkct7Ev6c0sp3Bqx82JQR/pub?output=csv"

st.set_page_config(page_title="Dragon Fly Stock", layout="wide", page_icon="🐉")

# --- CUSTOM DESIGN ---
st.markdown("""
    <style>
    .big-stat { font-size: 30px !important; font-weight: bold; color: #4CAF50; }
    .card { background-color: #1E1E1E; padding: 20px; border-radius: 10px; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- LOAD DATA FUNCTION ---
@st.cache_data(ttl=60) # Cache data for 60 seconds to prevent spamming Google
def load_data():
    try:
        # Read directly from the cloud
        df = pd.read_csv(SHEET_CSV_URL)
        
        # Clean up column names (remove extra spaces)
        df.columns = df.columns.str.strip()
        
        # Ensure Value is a number
        # (The CSV might read it as text if there are commas)
        if 'Value (₹)' in df.columns:
            df['Value'] = pd.to_numeric(df['Value (₹)'], errors='coerce').fillna(0)
            df['Item'] = df['Item Name']
        
        return df
    except Exception as e:
        st.error(f"Could not load data. Check your CSV Link. Error: {e}")
        return pd.DataFrame()

# --- MAIN APP ---
st.title("🐉 Dragon Fly Stock Dashboard")

# Refresh Button
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# Load Data
df = load_data()

if not df.empty:
    # Get the "Last Updated" time from the first row header or data
    # (Our sync script puts timestamp in the header, but pandas might shift it. 
    # For now, we just show the live data)
    
    # METRICS
    total_val = df['Value'].sum()
    top_item = df.loc[df['Value'].idxmax()]
    
    # Create 3 Columns for metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Total Stock Value", f"₹ {total_val:,.0f}")
    c2.metric("🏆 Most Valuable Item", top_item['Item'])
    c3.metric("📦 Unique Items", len(df))
    
    st.divider()
    
    # SEARCH BAR
    search = st.text_input("🔍 Search for an Item...", "")
    
    if search:
        # Filter data
        df = df[df['Item'].str.contains(search, case=False, na=False)]
    
    # CHARTS & TABLE
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📊 Top Assets")
        # Show top 15 items by value
        top_chart = df.sort_values("Value", ascending=False).head(15)
        st.bar_chart(top_chart.set_index("Item")['Value'], color="#4CAF50")
        
    with col2:
        st.subheader("📋 Stock List")
        # Show the table with a cool progress bar
        st.dataframe(
            df[['Item', 'Value']].sort_values("Value", ascending=False),
            column_config={
                "Value": st.column_config.ProgressColumn(
                    "Value (₹)",
                    format="₹%d",
                    min_value=0,
                    max_value=total_val/2 # Adjust scale for visibility
                )
            },
            hide_index=True,
            use_container_width=True
        )

else:
    st.warning("Data is empty. Make sure your Sync Script is running!")