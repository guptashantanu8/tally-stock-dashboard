import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURATION ---
# PASTE YOUR CSV LINK HERE:
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSGCN0vX5T-HTyvx1Bkbm8Jm8QlQrZRgYj_0_E2kKX7UKQvE12oVQ0s-QZqkct7Ev6c0sp3Bqx82JQR/pub?output=csv"

st.set_page_config(page_title="Dragon Fly AI", layout="wide", page_icon="🐉")

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
        if 'Value (₹)' in df.columns:
            df['Value'] = pd.to_numeric(df['Value (₹)'], errors='coerce').fillna(0)
            df['Item'] = df['Item Name']
            df['Group'] = df['Group'] # We now pull the Group column!
        return df
    except:
        return pd.DataFrame()

df = load_data()

# --- HEADER ---
c1, c2 = st.columns([3, 1])
with c1:
    st.title("🐉 Dragon Fly Intelligence")
with c2:
    if st.button("🔄 Force Refresh"):
        st.cache_data.clear()
        st.rerun()

if not df.empty:
    total_val = df['Value'].sum()
    top_group = df.groupby('Group')['Value'].sum().idxmax()
    
    # METRICS
    m1, m2, m3 = st.columns(3)
    m1.metric("💰 Net Worth", f"₹ {total_val:,.0f}")
    m2.metric("📂 Top Stock Group", top_group)
    m3.metric("📦 Total Unique Items", len(df))

    st.divider()

    tab1, tab2 = st.tabs(["📊 Group Heatmap", "📋 Detailed Inventory"])

    with tab1:
        st.subheader("Inventory by Group (Click a box to expand!)")
        
        # THE MAGIC HAPPENS HERE: path=['Group', 'Item'] nests them together
        fig = px.treemap(df, path=['Group', 'Item'], values='Value',
                         color='Value', color_continuous_scale='Viridis',
                         hover_data=['Value'])
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
            filtered_df[['Group', 'Item', 'Value']].sort_values(["Group", "Value"], ascending=[True, False]),
            column_config={
                "Value": st.column_config.ProgressColumn("Stock Value", format="₹%d", min_value=0, max_value=df['Value'].max())
            },
            use_container_width=True, hide_index=True
        )
else:
    st.warning("Waiting for data sync...")
