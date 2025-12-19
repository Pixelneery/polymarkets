import streamlit as st
import requests
import pandas as pd
import re
from urllib.parse import urlparse

# --- CONFIGURATION ---
POLY_URL = "https://gamma-api.polymarket.com/events"
st.set_page_config(page_title="PolySource Scout", layout="wide", page_icon="🔍")

# --- CSS FOR CLEAN LOOK ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #c9d1d9; }
    .source-tag { 
        background-color: #238636; 
        color: white; 
        padding: 2px 8px; 
        border-radius: 10px; 
        font-size: 0.8em;
    }
    .category-tag {
        border: 1px solid #30363d;
        color: #58a6ff;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.8em;
    }
    </style>
""", unsafe_allow_html=True)

# --- LOGIC: EXTRACT DOMAIN FROM DESCRIPTION ---
def extract_source(description):
    """
    Scans the market description to find the first Link.
    Usually the first link is the Resolution Source.
    """
    if not description:
        return "Unknown"
    
    # Regex to find http/https links
    urls = re.findall(r'(https?://[^\s\)]+)', description)
    
    if urls:
        # Get the domain (e.g., 'www.boxofficemojo.com')
        domain = urlparse(urls[0]).netloc
        return domain.replace('www.', '')
    
    return "No Link / General Knowledge"

# --- FETCH FUNCTION ---
@st.cache_data(ttl=600)
def fetch_source_markets(pages=4):
    all_data = []
    bar = st.progress(0, text="Scanning Resolution Sources...")
    
    for page in range(pages):
        params = {
            "closed": "false", 
            "limit": 50, 
            "offset": page*50, 
            "order": "volume", # Get high volume/popular ones first
            "ascending": "false"
        }
        
        try:
            r = requests.get(POLY_URL, params=params)
            if not r.ok: break
            events = r.json()
            if not events: break
            
            for e in events:
                # 1. Get Category (First Tag)
                tags = e.get('tags', [])
                category = tags[0]['label'] if tags else "Uncategorized"
                
                # 2. Extract Source Domain
                desc = e.get('description', '')
                source_domain = extract_source(desc)
                
                # 3. Market Info
                # Check markets inside event
                markets = e.get('markets', [])
                if markets:
                    m = markets[0] # Take the main market
                    all_data.append({
                        "Event": e.get('title'),
                        "Category": category,
                        "Source": source_domain,
                        "Volume": m.get('volume', 0),
                        "Slug": e.get('slug'),
                        "Description": desc
                    })
                    
        except Exception as err:
            st.error(f"Error: {err}")
            break
            
        bar.progress((page + 1) / pages)
        
    bar.empty()
    return pd.DataFrame(all_data)

# --- SIDEBAR ---
st.sidebar.title("🔍 Source Scout")
scan_depth = st.sidebar.slider("Scan Depth (Pages)", 1, 10, 3)
st.sidebar.divider()

# Filter by Category
target_category = st.sidebar.text_input("Filter Category (e.g. Economy, Pop)", "")
# Filter by Source
target_source = st.sidebar.text_input("Filter Source (e.g. twitter, bls.gov)", "")

# --- MAIN UI ---
st.title("Polymarket Resolution Sources")
st.caption("Scanning events to see WHO decides the winner.")

if st.button("SCAN SOURCES"):
    df = fetch_source_markets(scan_depth)
    
    if not df.empty:
        # --- FILTERING ---
        if target_category:
            df = df[df['Category'].str.contains(target_category, case=False, na=False)]
        if target_source:
            df = df[df['Source'].str.contains(target_source, case=False, na=False)]
            
        # --- STATISTICS ---
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Total Markets", len(df))
        with c2:
            top_cat = df['Category'].mode()[0] if not df.empty else "N/A"
            st.metric("Top Category", top_cat)
        with c3:
            top_source = df['Source'].mode()[0] if not df.empty else "N/A"
            st.metric("Most Common Source", top_source)
            
        st.divider()

        # --- DISPLAY AS INTERACTIVE TABLE ---
        # Convert volume to numeric for sorting
        df['Volume'] = pd.to_numeric(df['Volume'])
        
        # Configure the Dataframe display
        st.dataframe(
            df[['Category', 'Source', 'Event', 'Volume']],
            column_config={
                "Category": st.column_config.TextColumn("Category", help="Market Type"),
                "Source": st.column_config.TextColumn("Resolution Source", width="medium"),
                "Event": st.column_config.TextColumn("Event Name", width="large"),
                "Volume": st.column_config.NumberColumn("Volume", format="$%d"),
            },
            use_container_width=True,
            hide_index=True,
            height=600
        )
        
        # --- RAW LIST VIEW (For clicking) ---
        st.subheader("Direct Links")
        for i, row in df.iterrows():
            with st.expander(f"{row['Category']} | {row['Source']} | {row['Event']}"):
                st.write(f"**Resolution Source:** {row['Source']}")
                st.markdown(f"[Go to Market](https://polymarket.com/event/{row['Slug']})")
                st.info(f"**Full Context:** {row['Description'][:300]}...")

    else:
        st.warning("No data found.")