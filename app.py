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
    
    .main { background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%); }
    .stApp { font-family: 'Inter', sans-serif; }
    
    .card {
        background: white;
        border-radius: 20px;
        padding: 24px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
        border: 1px solid #f1f5f9;
        transition: all 0.3s ease;
    }
    .card:hover { transform: translateY(-4px); box-shadow: 0 20px 40px rgba(0, 0, 0, 0.12); }
    
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
    
    .metric-value {
        font-size: 2.8rem;
        font-weight: 700;
        background: linear-gradient(90deg, #1e40af, #3b82f6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
</style>
""", unsafe_allow_html=True)

# ====================== SESSION STATE ======================
if "auth" not in st.session_state:
    st.session_state.auth = {"ok": False, "role": None, "driver": None}
if "review" not in st.session_state:
    st.session_state.review = None
if "completed_orders" not in st.session_state:
    st.session_state.completed_orders = set()

# ====================== CONFIG ======================
DRIVERS = {
    "Connor": "1234", "Andy": "5678", "Kelvin": "1111",
    "Ken": "2222", "Mark": "3333"
}
MANAGER_PIN = "9999"

# ====================== GOOGLE SHEETS ======================
@st.cache_resource
def get_gspread_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    return gspread.authorize(creds)

# ====================== DATA LOADING ======================
@st.cache_data(ttl=120)
def load_jobs():
    try:
        raw = pd.read_csv("current_day.txt", sep="\t")
        routes = pd.read_csv("route_map.csv")
        
        raw.columns = raw.columns.str.strip()
        routes.columns = routes.columns.str.strip()

        clean = raw[["Co./Last Name", "Invoice No.", "Record ID"]].dropna().drop_duplicates()
        clean.columns = ["customer", "order_id", "zone"]
        
        clean["key"] = clean["customer"].str.lower().str.strip()
        routes["key"] = routes["customer"].str.lower().str.strip()
        
        jobs = clean.merge(routes, on="key", how="left")
        jobs["customer"] = jobs.get("customer_x", clean["customer"])
        jobs = jobs.drop(columns=["customer_x", "customer_y"], errors="ignore")
        jobs["driver"] = jobs.get("driver", "Unassigned").fillna("Unassigned")
        jobs["order_id"] = jobs["order_id"].astype(str)
        return jobs
    except Exception as e:
        st.error(f"Error loading jobs: {e}")
        return pd.DataFrame()

def load_completed():
    try:
        sheet = get_gspread_client().open("POD_DATA").sheet1
        df = pd.DataFrame(sheet.get_all_records())
        if not df.empty:
            df['order_id'] = df['order_id'].astype(str)
        return df
    except:
        return pd.DataFrame()

# ====================== LOGIN ======================
if not st.session_state.auth["ok"]:
    st.markdown('<div class="header"><h1 style="margin:0">🚚 POD System</h1><p style="margin:4px 0 0 0; opacity:0.9">Proof of Delivery</p></div>', unsafe_allow_html=True)
    
    role = st.selectbox("Login as", ["Driver", "Manager"])
    
    if role == "Driver":
        driver_name = st.selectbox("Driver", list(DRIVERS.keys()))
        pin = st.text_input("PIN", type="password")
        if st.button("Sign In", type="primary", use_container_width=True):
            if DRIVERS.get(driver_name) == pin:
                st.session_state.auth = {"ok": True, "role": "driver", "driver": driver_name}
                st.rerun()
            else:
                st.error("❌ Incorrect PIN")
    else:
        pin = st.text_input("Manager PIN", type="password")
        if st.button("Sign In", type="primary", use_container_width=True):
            if pin == MANAGER_PIN:
                st.session_state.auth = {"ok": True, "role": "manager", "driver": None}
                st.rerun()
            else:
                st.error("❌ Incorrect PIN")
    st.stop()

# ====================== HEADER ======================
driver = st.session_state.auth.get("driver")
st.markdown(f"""
<div class="header">
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
            <h2 style="margin:0">POD System</h2>
            <p style="margin:0; opacity:0.85">{datetime.now().strftime('%A, %B %d')}</p>
        </div>
        <div style="text-align:right">
            <p style="margin:0">👋 {driver or 'Manager'}</p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

if st.button("Logout"):
    st.session_state.clear()
    st.rerun()

# ====================== LOAD DATA ======================
jobs = load_jobs()
completed_df = load_completed()
all_completed = set(completed_df["order_id"].astype(str)) | st.session_state.completed_orders
active_jobs = jobs[~jobs["order_id"].isin(all_completed)].copy()

# ====================== MANAGER VIEW ======================
if st.session_state.auth["role"] == "manager":
    st.title("📊 Manager Dashboard")
    
    total = len(jobs)
    done = len(completed_df)
    pending = total - done
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Jobs", total)
    c2.metric("Completed", done)
    c3.metric("Remaining", pending)
    
    st.progress(done / total if total > 0 else 0)
    
    tab1, tab2 = st.tabs(["Active Deliveries", "Completed PODs"])
    with tab1:
        st.dataframe(active_jobs[["customer", "order_id", "driver", "route"]], use_container_width=True, hide_index=True)
    with tab2:
        if not completed_df.empty:
            st.dataframe(completed_df[["time", "driver", "customer", "order_id", "status"]], 
                        use_container_width=True, hide_index=True)
        else:
            st.info("No completed deliveries yet.")
    st.stop()

# ====================== DRIVER VIEW ======================
driver_jobs = active_jobs[active_jobs["driver"] == driver]

if driver_jobs.empty:
    st.success("🎉 All your deliveries are complete for today!")
    st.balloons()
    st.stop()

completed_today = len(completed_df[completed_df["driver"] == driver]) if not completed_df.empty else 0
total_today = len(jobs[jobs["driver"] == driver])

col1, col2 = st.columns([1, 3])
with col1:
    st.markdown(f"""
    <div style="text-align:center; padding:20px 10px;">
        <h1 class="metric-value">{completed_today}</h1>
        <p style="margin:0; color:#64748b">of {total_today}</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.subheader(f"Welcome back, {driver} 👋")
    st.write(f"**{len(driver_jobs)} deliveries** remaining today.")

# Delivery Selection
selected_idx = st.selectbox(
    "Select Delivery",
    options=driver_jobs.index,
    format_func=lambda i: f"#{driver_jobs.loc[i, 'order_id']} — {driver_jobs.loc[i, 'customer']}"
)

row = driver_jobs.loc[selected_idx]

st.markdown(f"""
<div class="card">
    <h3>{row['customer']}</h3>
    <p style="font-size:1.1rem; margin:8px 0;"><strong>Order #{row['order_id']}</strong></p>
    <p>Route: <strong>{row.get('route', '—')}</strong></p>
</div>
""", unsafe_allow_html=True)

# ====================== FORM & CONFIRMATION ======================
if st.session_state.review:
    d = st.session_state.review
    st.warning("### Confirm Submission")
    
    st.markdown(f"""
    <div class="card">
        <h4>{d['customer']}</h4>
        Order: {d['order_id']}<br>
        Status: <span style='color:{"#16a34a" if d["status"]=="Delivered" else "#dc2626"}; font-weight:600;'>
            {d['status']}
        </span><br>
        Notes: {d.get('notes', '—')}
    </div>
    """, unsafe_allow_html=True)
    
    if d.get("image"):
        st.image(base64.b64decode(d["image"]), caption="Proof of Delivery")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("← Cancel", use_container_width=True):
            st.session_state.review = None
            st.rerun()
    with c2:
        if st.button("✅ Confirm & Save", type="primary", use_container_width=True):
            try:
                sheet = get_gspread_client().open("POD_DATA").sheet1
                sheet.append_row([
                    d["time"], d["driver"], d.get("route", ""), d["customer"],
                    d["order_id"], d["status"], d.get("notes", ""), d.get("image", "")
                ])
                st.session_state.completed_orders.add(d["order_id"])
                st.success("✅ Delivery saved successfully!")
                st.session_state.review = None
                st.rerun()
            except Exception as e:
                st.error(f"Save failed: {e}")
else:
    with st.form("delivery_form"):
        status = st.radio("Status", ["Delivered", "Failed"], horizontal=True)
        notes = st.text_area("Notes / Remarks", placeholder="Left at door, customer unavailable, etc.")
        
        photo = st.file_uploader("Upload Proof Photo", type=["jpg", "jpeg", "png"])
        if photo:
            st.image(photo, width=400)
        
        if st.form_submit_button("Submit Delivery", type="primary", use_container_width=True):
            img_str = ""
            if photo:
                try:
                    image = Image.open(photo)
                    if image.width > 1280:
                        ratio = 1280 / image.width
                        image = image.resize((1280, int(image.height * ratio)), Image.Resampling.LANCZOS)
                    buf = io.BytesIO()
                    image.save(buf, format="JPEG", quality=85, optimize=True)
                    img_str = base64.b64encode(buf.getvalue()).decode()
                except:
                    st.error("Failed to process image")

            st.session_state.review = {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "driver": driver,
                "route": row.get("route", ""),
                "customer": row["customer"],
                "order_id": row["order_id"],
                "status": status,
                "notes": notes,
                "image": img_str
            }
            st.rerun()
