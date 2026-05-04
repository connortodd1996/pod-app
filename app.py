import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import base64
from PIL import Image
import io

st.set_page_config(
    page_title="POD • Proof of Delivery",
    layout="centered",
    page_icon="🚚",
    initial_sidebar_state="collapsed"
)

# ====================== MODERN STYLES ======================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    .main {
        background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
    }
    .stApp {
        font-family: 'Inter', sans-serif;
    }
    
    .card {
        background: white;
        border-radius: 20px;
        padding: 24px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
        border: 1px solid #f1f5f9;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .card:hover {
        transform: translateY(-4px);
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.12);
    }
    
    .header {
        background: linear-gradient(90deg, #1e2937, #334155);
        color: white;
        padding: 20px 24px;
        border-radius: 20px;
        margin-bottom: 24px;
    }
    
    .status-badge {
        padding: 6px 16px;
        border-radius: 50px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .delivered { background: #dcfce7; color: #166534; }
    .failed { background: #fee2e2; color: #991b1b; }
    
    .progress-ring {
        position: relative;
        width: 120px;
        height: 120px;
    }
    .metric-value {
        font-size: 2.8rem;
        font-weight: 700;
        background: linear-gradient(90deg, #1e40af, #3b82f6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
</style>
""", unsafe_allow_html=True)

# ====================== SESSION & CONFIG ======================
if "auth" not in st.session_state:
    st.session_state.auth = {"ok": False, "role": None, "driver": None}
if "review" not in st.session_state:
    st.session_state.review = None
if "completed_orders" not in st.session_state:
    st.session_state.completed_orders = set()

DRIVERS = {"Connor": "1234", "Andy": "5678", "Kelvin": "1111", "Ken": "2222", "Mark": "3333"}
MANAGER_PIN = "9999"

# ====================== GOOGLE SHEETS ======================
@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    return gspread.authorize(creds)

# (Keep your existing load_completed() and load_jobs() functions - same as previous version)

# ====================== LOGIN (Modern) ======================
if not st.session_state.auth["ok"]:
    st.markdown('<div class="header"><h1 style="margin:0">🚚 POD System</h1><p style="margin:0; opacity:0.9">Proof of Delivery</p></div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([1,1])
    with col1:
        role = st.selectbox("I am a", ["Driver", "Manager"], label_visibility="collapsed")
    with col2:
        if role == "Driver":
            driver_name = st.selectbox("Driver Name", list(DRIVERS.keys()))
            pin = st.text_input("PIN", type="password", placeholder="••••")
            if st.button("Sign In", type="primary", use_container_width=True):
                if DRIVERS.get(driver_name) == pin:
                    st.session_state.auth = {"ok": True, "role": "driver", "driver": driver_name}
                    st.rerun()
                else:
                    st.error("Invalid PIN")
        else:
            pin = st.text_input("Manager PIN", type="password", placeholder="••••")
            if st.button("Sign In", type="primary", use_container_width=True):
                if pin == MANAGER_PIN:
                    st.session_state.auth = {"ok": True, "role": "manager", "driver": None}
                    st.rerun()
                else:
                    st.error("Invalid PIN")
    st.stop()

# ====================== HEADER ======================
driver = st.session_state.auth.get("driver")

st.markdown(f"""
<div class="header">
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
            <h2 style="margin:0">POD System</h2>
            <p style="margin:0; opacity:0.85">Proof of Delivery • {datetime.now().strftime('%B %d, %Y')}</p>
        </div>
        <div style="text-align:right">
            <p style="margin:0; font-size:0.95rem">👋 {driver or 'Manager'}</p>
            <small style="opacity:0.7">Online</small>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

if st.button("Logout", use_container_width=False):
    st.session_state.clear()
    st.rerun()

# ====================== DATA LOADING ======================
# ... (use the same load_jobs() and load_completed() from previous version)

jobs = load_jobs()
completed_df = load_completed()
all_completed = set(completed_df["order_id"].astype(str)) | st.session_state.completed_orders
active_jobs = jobs[~jobs["order_id"].isin(all_completed)].copy()

# ====================== MANAGER VIEW ======================
if st.session_state.auth["role"] == "manager":
    st.title("📊 Overview")
    
    total = len(jobs)
    done = len(completed_df)
    progress = done / total if total > 0 else 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Deliveries", total)
    c2.metric("Completed", f"{done} ✅")
    c3.metric("Pending", total - done)
    
    st.progress(progress)
    st.caption(f"{done}/{total} deliveries completed today")
    
    # ... rest of manager tabs (same as before)

# ====================== DRIVER VIEW ======================
else:
    driver_jobs = active_jobs[active_jobs["driver"] == driver]
    
    if driver_jobs.empty:
        st.success("🎉 All deliveries completed!")
        st.balloons()
        st.stop()

    # Progress Ring + Stats
    completed_today = len(completed_df[completed_df["driver"] == driver]) if not completed_df.empty else 0
    total_today = len(jobs[jobs["driver"] == driver])
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown(f"""
        <div style="text-align:center; padding:20px;">
            <div class="progress-ring">
                <h1 class="metric-value">{completed_today}</h1>
            </div>
            <p style="margin-top:8px; color:#64748b">of {total_today}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.subheader(f"Good morning, {driver} 👋")
        st.write(f"You have **{len(driver_jobs)} deliveries** remaining today.")

    # Delivery Selection
    selected_idx = st.selectbox(
        "Choose next delivery",
        options=driver_jobs.index,
        format_func=lambda i: f"#{driver_jobs.loc[i, 'order_id']} — {driver_jobs.loc[i, 'customer']}"
    )

    row = driver_jobs.loc[selected_idx]

    # Modern Delivery Card
    st.markdown(f"""
    <div class="card">
        <h3>{row['customer']}</h3>
        <p style="margin:8px 0; font-size:1.1rem"><strong>Order #{row['order_id']}</strong></p>
        <p>Route: <strong>{row.get('route', '—')}</strong></p>
    </div>
    """, unsafe_allow_html=True)

    # Form (same logic as before, but with improved styling)
    # ... (keep the review + form section from the previous version)
