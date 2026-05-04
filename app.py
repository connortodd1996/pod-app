import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import base64
from PIL import Image
import io

st.set_page_config(page_title="POD System", layout="centered", page_icon="🚚", initial_sidebar_state="collapsed")

# ========================= STYLES =========================
st.markdown("""
<style>
    .main { background-color: #f8fafc; }
    .card {
        padding: 20px;
        border-radius: 16px;
        background: white;
        box-shadow: 0 4px 20px rgba(0,0,0,0.06);
        margin-bottom: 20px;
    }
    .success-card { border-left: 5px solid #16a34a; }
    .failed-card { border-left: 5px solid #dc2626; }
    h1, h2, h3 { font-weight: 600; }
    .metric { font-size: 2.2rem; font-weight: 700; color: #1e2937; }
</style>
""", unsafe_allow_html=True)

# ========================= SESSION STATE =========================
for key in ["auth", "review", "completed_orders", "history_view"]:
    if key not in st.session_state:
        st.session_state[key] = {"ok": False, "role": None, "driver": None} if key == "auth" else None if key == "review" else set() if key == "completed_orders" else False

# ========================= CONFIG =========================
DRIVERS = {"Connor": "1234", "Andy": "5678", "Kelvin": "1111", "Ken": "2222", "Mark": "3333"}
MANAGER_PIN = "9999"

# ========================= GOOGLE SHEETS =========================
@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    return gspread.authorize(creds)

def load_completed():
    try:
        sheet = get_gspread_client().open("POD_DATA").sheet1
        df = pd.DataFrame(sheet.get_all_records())
        if not df.empty:
            df['order_id'] = df['order_id'].astype(str)
        return df
    except:
        return pd.DataFrame()

# ========================= DATA =========================
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
        st.error(f"Data load error: {e}")
        return pd.DataFrame()

# ========================= LOGIN =========================
def login():
    st.title("🚚 POD System")
    st.markdown("**Proof of Delivery**")
    
    role = st.selectbox("Login as", ["Driver", "Manager"], label_visibility="collapsed")
    
    if role == "Driver":
        driver_name = st.selectbox("Select Driver", list(DRIVERS.keys()))
        pin = st.text_input("Enter PIN", type="password")
        if st.button("Login", type="primary", use_container_width=True):
            if DRIVERS.get(driver_name) == pin:
                st.session_state.auth = {"ok": True, "role": "driver", "driver": driver_name}
                st.rerun()
            else:
                st.error("Incorrect PIN")
    else:
        pin = st.text_input("Manager PIN", type="password")
        if st.button("Login", type="primary", use_container_width=True):
            if pin == MANAGER_PIN:
                st.session_state.auth = {"ok": True, "role": "manager", "driver": None}
                st.rerun()
            else:
                st.error("Incorrect PIN")

if not st.session_state.auth["ok"]:
    login()
    st.stop()

# ========================= HEADER =========================
col1, col2 = st.columns([5,1])
col1.title(f"🚚 POD System")
if col2.button("Logout", use_container_width=True):
    st.session_state.clear()
    st.rerun()

# Load Data
jobs = load_jobs()
completed_df = load_completed()
all_completed_orders = set(completed_df["order_id"].tolist()) | st.session_state.completed_orders

active_jobs = jobs[~jobs["order_id"].isin(all_completed_orders)].copy()

# ========================= MANAGER DASHBOARD =========================
if st.session_state.auth["role"] == "manager":
    st.title("📊 Manager Dashboard")
    
    total = len(jobs)
    done = len(completed_df)
    pending = total - done
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Jobs", total)
    c2.metric("Completed", done, delta=done)
    c3.metric("Remaining", pending)
    
    tab1, tab2 = st.tabs(["Live Deliveries", "Completed PODs"])
    
    with tab1:
        if active_jobs.empty:
            st.success("All deliveries completed today!")
        else:
            st.dataframe(active_jobs[["customer", "order_id", "driver", "route"]], use_container_width=True, hide_index=True)
    
    with tab2:
        if not completed_df.empty:
            search = st.text_input("Search", placeholder="Customer or Order ID")
            df_view = completed_df.copy()
            if search:
                df_view = df_view[df_view.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
            
            st.dataframe(df_view[["time", "driver", "customer", "order_id", "status", "notes"]], 
                        use_container_width=True, hide_index=True)
            
            if st.button("Refresh Data"):
                st.cache_data.clear()
                st.rerun()
        else:
            st.info("No completed deliveries yet.")
    
    st.stop()

# ========================= DRIVER DASHBOARD =========================
driver = st.session_state.auth["driver"]
driver_jobs = active_jobs[active_jobs["driver"] == driver]

st.subheader(f"👋 Welcome back, **{driver}**")

if driver_jobs.empty:
    st.success("🎉 You have completed all your deliveries for today!")
    st.balloons()
    st.stop()

completed_count = len(completed_df[completed_df["driver"] == driver]) if not completed_df.empty else 0
total_for_driver = len(jobs[jobs["driver"] == driver])
remaining = len(driver_jobs)

st.progress(completed_count / total_for_driver if total_for_driver > 0 else 0)
st.caption(f"**{remaining} deliveries remaining** • {completed_count}/{total_for_driver} done")

# Select Delivery
selected_idx = st.selectbox(
    "Select Delivery",
    options=driver_jobs.index,
    format_func=lambda i: f"{driver_jobs.loc[i, 'customer']} — {driver_jobs.loc[i, 'order_id']}"
)

row = driver_jobs.loc[selected_idx]

st.markdown(f"""
<div class="card">
    <b>{row['customer']}</b><br>
    Order ID: <b>{row['order_id']}</b><br>
    Route: {row.get('route', 'N/A')}
</div>
""", unsafe_allow_html=True)

# ========================= FORM & REVIEW =========================
if st.session_state.review:
    d = st.session_state.review
    st.warning("### Confirm Delivery")
    
    card_class = "success-card" if d["status"] == "Delivered" else "failed-card"
    st.markdown(f"""
    <div class="card {card_class}">
        <b>{d['customer']}</b><br>
        Order: {d['order_id']}<br>
        Status: <span style='color:{"#16a34a" if d["status"]=="Delivered" else "#dc2626"}; font-weight:600;'>
            {d['status']}
        </span><br>
        Notes: {d.get('notes', '—')}
    </div>
    """, unsafe_allow_html=True)
    
    if d.get("image"):
        try:
            st.image(base64.b64decode(d["image"]), caption="📸 Proof of Delivery", use_column_width=True)
        except:
            pass

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
                    d["time"], d["driver"], d["route"], d["customer"],
                    d["order_id"], d["status"], d.get("notes", ""), d.get("image", "")
                ])
                
                st.session_state.completed_orders.add(d["order_id"])
                st.success("✅ Successfully Saved!")
                st.session_state.review = None
                st.rerun()
            except Exception as e:
                st.error(f"Save failed: {e}")

else:
    with st.form("delivery_form"):
        status = st.radio("Delivery Status", ["Delivered", "Failed"], horizontal=True)
        notes = st.text_area("Notes / Remarks", placeholder="Customer not home, left with neighbor, etc.")
        
        photo = st.file_uploader("Upload Proof of Delivery", type=["jpg", "jpeg", "png"])
        if photo:
            st.image(photo, width=350)
        
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
                except Exception as e:
                    st.error("Image processing failed")
                    st.stop()

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
