import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURATION ---
# PASTE YOUR CSV LINK HERE:
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSGCN0vX5T-HTyvx1Bkbm8Jm8QlQrZRgYj_0_E2kKX7UKQvE12oVQ0s-QZqkct7Ev6c0sp3Bqx82JQR/pub?output=csv"

st.set_page_config(page_title="Dragon Fly Inventory", layout="wide", page_icon="🐉")

# --- CUSTOM STYLE ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: white; }
    </style>
    """, unsafe_allow_html=True)

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
            # Create a clean display string like "1500 pcs"
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
    total_qty = df['Quantity'].sum()
    top_group = df.groupby('Group')['Quantity'].sum().idxmax()
    
    # METRICS
    m1, m2, m3 = st.columns(3)
    m1.metric("📦 Total Physical Volume", f"{total_qty:,.0f} units")
    m2.metric("📂 Largest Stock Group", top_group)
    m3.metric("📋 Total Unique Items", len(df))

    st.divider()

    tab1, tab2 = st.tabs(["📊 Volume Heatmap", "📋 Detailed Stock List"])

    with tab1:
        st.subheader("Inventory Volume by Group (Click to expand)")
        
        # Treemap now uses Quantity for size, and shows the Unit when you hover
        fig = px.treemap(df, path=['Group', 'Item'], values='Quantity',
                         color='Quantity', color_continuous_scale='Blues',
                         hover_data=['Display Qty'])
        
        # Customize hover label to look clean
        fig.update_traces(hovertemplate='<b>%{label}</b><br>Stock: %{customdata[0]}<extra></extra>')
        fig.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=600)
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        # Group Filter
        groups = ["All Groups"] + df['Group'].unique().tolist()
        selected_group = st.selectbox("Filter by Stock Group:", groups)
        
        filtered_df = df.copy()
        if selected_group != "All Groups":
            filtered_df = filtered_df[filtered_df['Group'] == selected_group]

        st.dataframe(
            filtered_df[['Group', 'Item', 'Quantity', 'Unit']].sort_values(["Group", "Quantity"], ascending=[True, False]),
            column_config={
                "Quantity": st.column_config.NumberColumn("Physical Quantity", format="%d")
            },
            use_container_width=True, hide_index=True
        )
else:
    st.warning("Waiting for data sync...")
