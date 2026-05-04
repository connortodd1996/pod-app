import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import base64
from PIL import Image
import io

st.set_page_config(page_title="POD System", layout="centered", page_icon="🚚")

# ========================= STYLE =========================
st.markdown("""
<style>
    .card {
        padding: 18px;
        border-radius: 12px;
        background: white;
        margin-bottom: 16px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        border: 1px solid #f0f0f0;
    }
    .success { color: #16a34a; font-weight: 600; }
    button { height: 52px; border-radius: 10px; }
    .stButton>button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# ========================= CONFIG & AUTH =========================
DRIVERS = {
    "Connor": "1234",
    "Andy": "5678",
    "Kelvin": "1111",
    "Ken": "2222",
    "Mark": "3333"
}
MANAGER_PIN = "9999"

# ========================= SESSION STATE =========================
if "auth" not in st.session_state:
    st.session_state.auth = {"ok": False, "role": None, "driver": None}
if "review" not in st.session_state:
    st.session_state.review = None
if "data_version" not in st.session_state:
    st.session_state.data_version = 0  # For forcing refresh

# ========================= GOOGLE SHEETS =========================
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

def get_completed_df():
    try:
        client = get_gspread_client()
        sheet = client.open("POD_DATA").sheet1
        records = sheet.get_all_records()
        df = pd.DataFrame(records)
        if not df.empty:
            df['order_id'] = df['order_id'].astype(str)
        return df
    except Exception as e:
        st.error(f"Failed to load Google Sheet: {e}")
        return pd.DataFrame()

# ========================= DATA LOADING =========================
@st.cache_data(ttl=60)  # Refresh every minute
def load_data(_data_version):
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
        jobs["customer"] = jobs["customer_x"]
        jobs = jobs.drop(columns=["customer_x", "customer_y"], errors="ignore")
        jobs["driver"] = jobs.get("driver", "Unassigned")
        jobs["order_id"] = jobs["order_id"].astype(str)
        
        completed = get_completed_df()
        if not completed.empty:
            completed_orders = completed["order_id"].astype(str).unique()
            jobs = jobs[~jobs["order_id"].isin(completed_orders)]
            
        return jobs
    except Exception as e:
        st.error(f"Error loading data files: {e}")
        return pd.DataFrame()

# ========================= LOGIN =========================
def login_page():
    st.title("🚚 POD System")
    
    role = st.selectbox("Login as", ["Driver", "Manager"])
    
    if role == "Driver":
        driver_name = st.selectbox("Driver", list(DRIVERS.keys()))
        pin = st.text_input("PIN", type="password")
        
        if st.button("Login", type="primary"):
            if DRIVERS.get(driver_name) == pin:
                st.session_state.auth = {"ok": True, "role": "driver", "driver": driver_name}
                st.rerun()
            else:
                st.error("❌ Incorrect PIN")
    else:
        pin = st.text_input("Manager PIN", type="password")
        if st.button("Login", type="primary"):
            if pin == MANAGER_PIN:
                st.session_state.auth = {"ok": True, "role": "manager", "driver": None}
                st.rerun()
            else:
                st.error("❌ Incorrect PIN")

# ========================= MAIN APP =========================
if not st.session_state.auth["ok"]:
    login_page()
    st.stop()

# Header
col1, col2 = st.columns([4, 1])
col1.title("🚚 POD System")
if col2.button("Logout"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

st.divider()

# Load data
jobs = load_data(st.session_state.data_version)

# ========================= MANAGER VIEW =========================
if st.session_state.auth["role"] == "manager":
    st.title("📊 Manager Dashboard")
    
    completed = get_completed_df()
    
    if completed.empty:
        st.info("No deliveries completed yet.")
    else:
        st.subheader(f"Completed Deliveries ({len(completed)})")
        
        # Search
        search = st.text_input("🔍 Search customer or order", "")
        
        display_df = completed.copy()
        if search:
            mask = display_df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
            display_df = display_df[mask]
        
        st.dataframe(
            display_df[["time", "driver", "customer", "order_id", "status", "notes"]],
            use_container_width=True,
            hide_index=True
        )
        
        # Detailed view
        if not display_df.empty:
            selected = st.selectbox(
                "View POD Details",
                options=display_df.index,
                format_func=lambda x: f"{display_df.loc[x, 'customer']} - {display_df.loc[x, 'order_id']}"
            )
            
            r = display_df.loc[selected]
            st.markdown(f"""
            <div class="card">
                <b>{r['customer']}</b><br>
                Order: {r['order_id']}<br>
                Driver: {r['driver']}<br>
                Time: {r['time']}<br>
                Status: <span style='color:{"#16a34a" if r["status"]=="Delivered" else "#dc2626"}'>
                    {r['status']}
                </span><br>
                Notes: {r.get('notes', '')}
            </div>
            """, unsafe_allow_html=True)
            
            if r.get("image"):
                try:
                    image_bytes = base64.b64decode(r["image"])
                    st.image(image_bytes)
                except:
                    st.warning("Could not display image")
    
    if st.button("🔄 Refresh Data"):
        st.session_state.data_version += 1
        st.rerun()
    
    st.stop()

# ========================= DRIVER VIEW =========================
driver = st.session_state.auth["driver"]
driver_jobs = jobs[jobs["driver"] == driver]

if driver_jobs.empty:
    st.success("🎉 All deliveries for today are complete!")
    st.balloons()
    st.stop()

st.subheader(f"👋 Welcome back, {driver}")

# Select delivery
options = driver_jobs.index.tolist()
idx = st.selectbox(
    "Select Delivery",
    options,
    format_func=lambda i: f"{driver_jobs.loc[i, 'customer']} — {driver_jobs.loc[i, 'order_id']}"
)

row = driver_jobs.loc[idx]

st.markdown(f"""
<div class="card">
    <b>{row['customer']}</b><br>
    Order: {row['order_id']}<br>
    Route: {row.get('route', 'N/A')}
</div>
""", unsafe_allow_html=True)

# ========================= DELIVERY FORM =========================
if st.session_state.review:
    d = st.session_state.review
    st.warning("**Confirm Submission**")
    
    st.markdown(f"""
    <div class="card">
        <b>{d['customer']}</b><br>
        Order: {d['order_id']}<br>
        Status: <span style='color:{"#16a34a" if d["status"]=="Delivered" else "#dc2626"}'>
            {d['status']}
        </span><br>
        Notes: {d.get('notes', 'None')}
    </div>
    """, unsafe_allow_html=True)
    
    if d.get("image"):
        try:
            st.image(base64.b64decode(d["image"]), caption="Proof of Delivery")
        except:
            pass

    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Cancel", use_container_width=True):
            st.session_state.review = None
            st.rerun()
    with col2:
        if st.button("✅ Confirm & Save", type="primary", use_container_width=True):
            try:
                client = get_gspread_client()
                sheet = client.open("POD_DATA").sheet1
                
                sheet.append_row([
                    d["time"], d["driver"], d["route"], d["customer"],
                    d["order_id"], d["status"], d["notes"], d["image"]
                ])
                
                st.success("✅ Delivery saved successfully!")
                st.session_state.review = None
                st.session_state.data_version += 1
                st.rerun()
            except Exception as e:
                st.error(f"Failed to save: {e}")
else:
    with st.form("delivery_form", clear_on_submit=False):
        status = st.radio("Delivery Status", ["Delivered", "Failed"], horizontal=True)
        notes = st.text_area("Notes / Reason (if failed)", placeholder="Left at reception, customer not home, etc.")
        
        photo = st.file_uploader("Upload Proof of Delivery", type=["jpg", "jpeg", "png"])
        
        if photo:
            st.image(photo, width=300)
        
        submitted = st.form_submit_button("Submit Delivery", type="primary")
        
        if submitted:
            img_str = ""
            if photo:
                try:
                    # Compress image
                    image = Image.open(photo)
                    if image.size[0] > 1200:
                        ratio = 1200 / image.size[0]
                        new_size = (1200, int(image.size[1] * ratio))
                        image = image.resize(new_size, Image.Resampling.LANCZOS)
                    
                    buffer = io.BytesIO()
                    image.save(buffer, format="JPEG", quality=85, optimize=True)
                    img_str = base64.b64encode(buffer.getvalue()).decode()
                except:
                    st.error("Failed to process image")
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
