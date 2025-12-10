import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone
import json
import time

# --- CONFIGURATION ---
POLY_URL = "https://gamma-api.polymarket.com/events"
TAGS_URL = "https://gamma-api.polymarket.com/tags"

# --- LOCAL/CLOUD API KEY HANDLING ---
# Try to get key from secrets (Cloud), else use a placeholder or input (Local)
OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]

st.set_page_config(page_title="PolySniper Pro", layout="wide", page_icon="🎯")

# --- SESSION STATE SETUP (Fix for Button Bug) ---
if 'audits' not in st.session_state:
    st.session_state['audits'] = {} # Stores audit results: {slug: {verdict:..., risk:...}}

# --- MODELS ---
MODEL_FALLBACK_LIST = [
    "qwen/qwen3-coder:free",
    "google/gemini-2.0-flash-exp:free",
    "kwaipilot/kat-coder-pro:free",
    "deepseek/deepseek-r1-0528:free",
    "deepseek/deepseek-chat-v3-0324:free",
    "deepseek/deepseek-r1:free",
    "tngtech/deepseek-r1t2-chimera:free",
    "tngtech/deepseek-r1t-chimera:free",
    "microsoft/mai-ds-r1:free",
    "deepseek/deepseek-chat-v3.1:free",
    "openai/gpt-oss-20b:free",
    "mistralai/mistral-small-3.2-24b-instruct:free",
    "mistralai/mistral-nemo:free",
    "google/gemma-3-27b-it:free",
    "z-ai/glm-4.5-air:free",
    "deepseek/deepseek-r1-0528-qwen3-8b:free",
    "alibaba/tongyi-deepresearch-30b-a3b:free",
    "meituan/longcat-flash-chat:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "nvidia/nemotron-nano-9b-v2:free",
    "meta-llama/llama-3.3-8b-instruct:free",
    "meta-llama/llama-4-maverick:free",
    "meta-llama/llama-4-scout:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "agentica-org/deepcoder-14b-preview:free",
    "qwen/qwen3-4b:free",
    "qwen/qwen3-30b-a3b:free",
    "qwen/qwen3-14b:free",
    "qwen/qwen3-235b-a22b:free",
    "moonshotai/kimi-k2:free",
    "mistralai/mistral-small-24b-instruct-2501:free",
    "mistralai/mistral-7b-instruct:free",
    "qwen/qwen-2.5-coder-32b-instruct:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "google/gemma-3-4b-it:free",
    "google/gemma-3-12b-it:free",
    "qwen/qwen2.5-vl-32b-instruct:free",
    "google/gemma-3n-e2b-it:free",
    "google/gemma-3n-e4b-it:free",
    "deepseek/deepseek-r1-distill-llama-70b:free"
]

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .stButton>button { border: 1px solid #30363d; background-color: #21262d; color: #58a6ff; }
    .stButton>button:hover { border-color: #58a6ff; color: #ffffff; }
    .risk-badge { padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .risk-safe { background-color: #238636; color: white; }
    .risk-high { background-color: #da3633; color: white; }
    </style>
""", unsafe_allow_html=True)

# --- FUNCTIONS ---

@st.cache_data(ttl=3600)
def fetch_tags():
    """Fetches all available tags from Polymarket for the dropdown."""
    try:
        r = requests.get(TAGS_URL)
        if r.status_code == 200:
            tags = r.json()
            # Return a dictionary {Name: ID}
            return {t['label']: t['id'] for t in tags if 'label' in t}
    except:
        pass
    return {}

def analyze_risk_llm(question, event_title, slug):
    """The AI Auditor Logic"""
    current_time = datetime.now().isoformat()
    
    system_prompt = f"""You are Synapse, a ruthless trade auditor.
    Current time: {current_time}.
    
    Audit this Polymarket event for "Manipulation Risk" and "Ambiguity".
    Event: {event_title}
    Market: {question}
    
    Output ONLY a JSON object:
    {{
        "risk_score": (Integer 1-10, 10=EXTREME RISK),
        "verdict": "SAFE" or "RISKY",
        "reasoning": "One sharp sentence explaining why."
    }}
    """
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://polysniper.streamlit.app",
    }

    for model in MODEL_FALLBACK_LIST:
        try:
            payload = {
                "model": model,
                "messages": [{"role": "system", "content": system_prompt}]
            }
            r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=15)
            
            if r.status_code == 200:
                content = r.json()['choices'][0]['message']['content']
                # Clean JSON
                if "```json" in content: content = content.split("```json")[1].split("```")[0]
                elif "```" in content: content = content.split("```")[1].split("```")[0]
                
                result = json.loads(content)
                # Store in Session State immediately
                st.session_state['audits'][slug] = result
                return result
        except:
            continue
            
    return {"risk_score": 0, "verdict": "ERROR", "reasoning": "AI unavailable."}

@st.cache_data(ttl=120)
def fetch_markets_advanced(pages=3, tag_id=None):
    """Fetches markets with optional Tag Filtering."""
    all_items = []
    
    for page in range(pages):
        offset = page * 50
        params = {
            "closed": "false",
            "limit": 50,
            "offset": offset,
            "order": "id",
            "ascending": "false"
        }
        if tag_id:
            params["tag_id"] = tag_id
            
        try:
            r = requests.get(POLY_URL, params=params)
            if not r.ok: break
            data = r.json()
            if not data: break
            
            for event in data:
                markets = event.get('markets', [])
                for m in markets:
                    # Calculate Spread/Price Sum
                    prices = json.loads(m.get('outcomePrices', '[]')) if isinstance(m.get('outcomePrices'), str) else m.get('outcomePrices', [])
                    # Simple check for Yes/No spread (assuming 2 outcomes)
                    price_sum = 0
                    try:
                        price_sum = sum([float(p) for p in prices]) if prices else 0
                    except: price_sum = 0
                    
                    all_items.append({
                        "Event": event.get('title'),
                        "Question": m.get('question'),
                        "Slug": event.get('slug'),
                        "Volume": float(m.get('volume', 0)),
                        "Liquidity": float(m.get('liquidity', 0)), # Gamma API sometimes has this
                        "EndDate": m.get('endDate'),
                        "PriceSum": price_sum, # 1.0 is perfect, >1.0 is fee, <1.0 is arb
                        "Outcomes": m.get('outcomes')
                    })
        except Exception as e:
            st.error(f"API Error: {e}")
            break
    
    return pd.DataFrame(all_items)

# --- SIDEBAR CONFIG ---
st.sidebar.title("🎯 Sniper Config")

# Tag Filter
tag_map = fetch_tags()
selected_tag_label = st.sidebar.selectbox("Filter by Category", ["All Markets"] + list(tag_map.keys()))
selected_tag_id = tag_map.get(selected_tag_label) if selected_tag_label != "All Markets" else None

days_left_max = st.sidebar.slider("Ends within (Days)", 0.5, 30.0, 5.0)
min_volume = st.sidebar.number_input("Min Volume ($)", 5000, 10000000, 10000)
scan_depth = st.sidebar.slider("Scan Depth (Pages)", 1, 10, 3)

# --- MAIN UI ---
st.title("PolySniper Pro ⚡")
st.caption(f"Targeting: {selected_tag_label} | Vol > ${min_volume:,.0f} | < {days_left_max} Days")

if st.button("RUN DEEP SCAN"):
    with st.spinner("Scanning Order Books..."):
        df = fetch_markets_advanced(scan_depth, selected_tag_id)
        
        if not df.empty:
            # Date Math
            df['EndDate'] = pd.to_datetime(df['EndDate']).dt.tz_convert(None)
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            df['DaysLeft'] = (df['EndDate'] - now).dt.total_seconds() / 86400
            
            # Filtering
            mask = (df['DaysLeft'] > 0) & (df['DaysLeft'] <= days_left_max) & (df['Volume'] >= min_volume)
            filtered = df[mask].copy()
            
            # Action Density (Vol / Time)
            filtered['ActionDensity'] = filtered['Volume'] / filtered['DaysLeft'].clip(lower=0.1)
            filtered = filtered.sort_values(by='ActionDensity', ascending=False)
            
            st.session_state['last_results'] = filtered # Save results so they stay after buttons click
        else:
            st.warning("No markets found.")

# --- RENDER RESULTS (From Session State) ---
if 'last_results' in st.session_state:
    results = st.session_state['last_results']
    st.success(f"Displaying {len(results)} Opportunities")
    
    for i, row in results.iterrows():
        slug = row['Slug']
        
        with st.container():
            c1, c2, c3 = st.columns([3, 1, 1])
            
            with c1:
                st.subheader(row['Question'])
                st.caption(f"Event: {row['Event']}")
                st.markdown(f"[Trade on Polymarket](https://polymarket.com/event/{slug})", unsafe_allow_html=True)
                
                # SPREAD WARNING
                if row['PriceSum'] > 1.02:
                    st.warning(f"⚠️ High Spread/Fees (Sum: {row['PriceSum']:.2f})")
                elif row['PriceSum'] < 0.98 and row['PriceSum'] > 0:
                    st.info(f"💎 Arbitrage Chance? (Sum: {row['PriceSum']:.2f})")

            with c2:
                st.metric("Volume", f"${row['Volume']:,.0f}")
                st.metric("Ends In", f"{row['DaysLeft']:.1f}d")
                
            with c3:
                # AUDIT LOGIC
                # Check if we already have an audit for this slug
                existing_audit = st.session_state['audits'].get(slug)
                
                if existing_audit:
                    # Show cached result
                    score = existing_audit.get('risk_score')
                    verdict = existing_audit.get('verdict')
                    color = "red" if verdict == "RISKY" else "green"
                    st.markdown(f":{color}-background[**{verdict} ({score}/10)**]")
                    st.caption(existing_audit.get('reasoning'))
                else:
                    # Show button
                    if st.button("🧠 Audit Risk", key=f"btn_{slug}"):
                        # Perform Audit
                        with st.spinner("Analyzing..."):
                            analyze_risk_llm(row['Question'], row['Event'], slug)
                        st.rerun() # Refresh to show the result immediately
            
            st.divider()