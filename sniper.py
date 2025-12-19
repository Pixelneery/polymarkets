import streamlit as st
import requests
import pandas as pd
import re
from urllib.parse import urlparse

# --- CONFIGURATION ---
POLY_URL = "https://gamma-api.polymarket.com/events"
st.set_page_config(page_title="PolySource Scout", layout="wide", page_icon="🔍")

# --- CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #c9d1d9; }
    div[data-testid="stMetricValue"] { color: #00ff00; }
    </style>
""", unsafe_allow_html=True)

# --- SESSION STATE INITIALIZATION ---
if 'market_data' not in st.session_state:
    st.session_state['market_data'] = pd.DataFrame()

# --- LOGIC ---
def extract_source(description):
    if not description: return "Unknown"
    urls = re.findall(r'(https?://[^\s\)]+)', description)
    if urls:
        domain = urlparse(urls[0]).netloc
        return domain.replace('www.', '')
    return "No Link / General"

def fetch_data(pages):
    all_data = []
    bar = st.progress(0, text="Scanning API...")
    
    for page in range(pages):
        try:
            params = {"closed": "false", "limit": 50, "offset": page*50, "order": "volume", "ascending": "false"}
            r = requests.get(POLY_URL, params=params)
            if not r.ok: break
            events = r.json()
            if not events: break
            
            for e in events:
                tags = e.get('tags', [])
                cat = tags[0]['label'] if tags else "Uncategorized"
                src = extract_source(e.get('description', ''))
                markets = e.get('markets', [])
                if markets:
                    all_data.append({
                        "Category": cat,
                        "Source": src,
                        "Event": e.get('title'),
                        "Volume": float(markets[0].get('volume', 0)),
                        "Slug": e.get('slug'),
                        "Desc": e.get('description', '')
                    })
        except: break
        bar.progress((page + 1) / pages)
    
    bar.empty()
    return pd.DataFrame(all_data)

# --- SIDEBAR CONTROLS ---
st.sidebar.title("🔍 Config")
scan_depth = st.sidebar.slider("Scan Depth", 1, 10, 3)

if st.sidebar.button("🚀 START NEW SCAN", type="primary"):
    with st.spinner("Fetching fresh data..."):
        df = fetch_data(scan_depth)
        st.session_state['market_data'] = df # Save to memory

st.sidebar.divider()

# --- DYNAMIC FILTERS (Only show if data exists) ---
df = st.session_state['market_data']

if not df.empty:
    st.sidebar.subheader("Filter Results")
    
    # 1. Category Dropdown
    # Get unique categories and sort them
    unique_cats = sorted(df['Category'].unique().tolist())
    selected_cats = st.sidebar.multiselect(
        "Select Categories", 
        unique_cats,
        default=unique_cats[:3] if len(unique_cats) > 3 else unique_cats # Select first 3 by default
    )
    
    # 2. Source Dropdown
    unique_sources = sorted(df['Source'].unique().tolist())
    selected_sources = st.sidebar.multiselect(
        "Select Sources", 
        unique_sources,
        default=[] # Default empty means "Show All" in our logic below
    )
    
    # --- FILTER LOGIC ---
    # Apply Category Filter
    if selected_cats:
        df = df[df['Category'].isin(selected_cats)]
        
    # Apply Source Filter (If empty, we assume user wants ALL sources)
    if selected_sources:
        df = df[df['Source'].isin(selected_sources)]

# --- MAIN UI ---
st.title("Polymarket Source Scout")

if df.empty:
    st.info("👈 Click 'START NEW SCAN' in the sidebar to begin.")
else:
    # Statistics based on current filters
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Markets Found", len(df))
    with c2: st.metric("Avg Volume", f"${df['Volume'].mean():,.0f}")
    with c3: 
        top_src = df['Source'].mode()[0] if not df.empty else "-"
        st.metric("Top Source", top_src)

    st.divider()
    
    # Interactive Table
    st.dataframe(
        df[['Category', 'Source', 'Event', 'Volume']],
        column_config={
            "Volume": st.column_config.NumberColumn(format="$%d"),
            "Source": st.column_config.TextColumn(width="medium"),
        },
        use_container_width=True,
        height=500
    )
    
    # Direct Links Section
    st.subheader("Deep Dive")
    for i, row in df.iterrows():
        with st.expander(f"[{row['Category']}] {row['Event']}"):
            st.write(f"**Source:** {row['Source']}")
            st.write(f"**Volume:** ${row['Volume']:,.0f}")
            st.caption(row['Desc'][:300] + "...")
            st.markdown(f"[Go to Market](https://polymarket.com/event/{row['Slug']})")