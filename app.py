import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import base64

st.set_page_config(page_title="POD System", layout="centered")

# -----------------------------
# STYLE
# -----------------------------
st.markdown("""
<style>
.card {
    padding:15px;
    border-radius:12px;
    background:white;
    margin-bottom:10px;
    box-shadow:0 2px 6px rgba(0,0,0,0.05);
}
.green button {
    background-color:#16a34a !important;
    color:white !important;
    height:60px;
}
.red button {
    background-color:#dc2626 !important;
    color:white !important;
    height:60px;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# GOOGLE SHEETS
# -----------------------------
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    st.secrets["gcp_service_account"], scope
)
client = gspread.authorize(creds)
sheet = client.open("POD_DATA").sheet1

# -----------------------------
# SESSION
# -----------------------------
if "auth" not in st.session_state:
    st.session_state.auth = {"ok": False, "role": None, "driver": None}

if "review" not in st.session_state:
    st.session_state.review = None

# -----------------------------
# LOGIN
# -----------------------------
DRIVER_PINS = {
    "Connor": "1234",
    "Andy": "5678",
    "Kelvin": "1111",
    "Ken": "2222",
    "Mark": "3333"
}
MANAGER_PIN = "9999"

if not st.session_state.auth["ok"]:

    st.title("🚚 POD System")

    role = st.selectbox("Login as", ["Driver", "Manager"])

    if role == "Driver":
        d = st.selectbox("Driver", list(DRIVER_PINS.keys()))
        p = st.text_input("PIN", type="password")

        if st.button("Login"):
            if DRIVER_PINS.get(d) == p:
                st.session_state.auth = {"ok": True, "role": "driver", "driver": d}
                st.rerun()
            else:
                st.error("Wrong PIN")

    else:
        p = st.text_input("Manager PIN", type="password")

        if st.button("Login"):
            if p == MANAGER_PIN:
                st.session_state.auth = {"ok": True, "role": "manager", "driver": None}
                st.rerun()
            else:
                st.error("Wrong PIN")

    st.stop()

# -----------------------------
# HEADER
# -----------------------------
col1, col2 = st.columns([4,1])
with col1:
    st.markdown("### 🚚 POD System")
with col2:
    if st.button("Logout"):
        st.session_state.auth = {"ok": False, "role": None, "driver": None}
        st.rerun()

# -----------------------------
# LOAD DATA
# -----------------------------
records = sheet.get_all_records()
completed = pd.DataFrame(records)

raw = pd.read_csv("current_day.txt", sep="\t")
route_map = pd.read_csv("route_map.csv")

raw.columns = raw.columns.str.strip()
route_map.columns = route_map.columns.str.strip()

clean = raw[["Co./Last Name", "Invoice No.", "Record ID"]].dropna().drop_duplicates()
clean.columns = ["customer", "order_id", "zone"]

clean["key"] = clean["customer"].str.strip().str.lower()
route_map["key"] = route_map["customer"].str.strip().str.lower()

jobs = clean.merge(route_map, on="key", how="left")

jobs["customer"] = jobs["customer_x"]
jobs = jobs.drop(columns=["customer_x","customer_y"], errors="ignore")

jobs["driver"] = jobs["driver"].fillna("Unassigned")

# Remove completed
if not completed.empty:
    jobs = jobs[~jobs["order_id"].astype(str).isin(completed["order_id"].astype(str))]

# -----------------------------
# MANAGER
# -----------------------------
if st.session_state.auth["role"] == "manager":

    st.title("📊 Manager Dashboard")

    if completed.empty:
        st.info("No deliveries yet")
    else:
        i = st.selectbox(
            "Select Delivery",
            completed.index,
            format_func=lambda x: completed.loc[x,"customer"]
        )

        row = completed.loc[i]

        st.markdown(f"""
        <div class="card">
        <b>{row['customer']}</b><br>
        Order: {row['order_id']}<br>
        Driver: {row['driver']}<br>
        Status: {row['status']}<br>
        Notes: {row['notes']}
        </div>
        """, unsafe_allow_html=True)

        if row["image"]:
            st.image(base64.b64decode(row["image"]))

    st.stop()

# -----------------------------
# DRIVER
# -----------------------------
driver = st.session_state.auth["driver"]

driver_jobs = jobs[jobs["driver"] == driver]

if driver_jobs.empty:
    st.success("All deliveries complete")
    st.stop()

row = driver_jobs.iloc[0]

customer = row["customer"]
order_id = row["order_id"]
route = row["route"]

st.markdown(f"""
<div class="card">
<b>{customer}</b><br>
Order: {order_id}<br>
Route: {route}
</div>
""", unsafe_allow_html=True)

# -----------------------------
# FLOW
# -----------------------------
if st.session_state.review:

    data = st.session_state.review

    st.warning("⚠️ Confirm Delivery")

    st.markdown(f"""
    <div class="card">
    <b>{data['customer']}</b><br>
    Order: {data['order_id']}<br>
    Status: {data['status']}<br>
    Notes: {data['notes']}
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="red">', unsafe_allow_html=True)
        if st.button("Cancel"):
            st.session_state.review = None
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="green">', unsafe_allow_html=True)
        if st.button("Confirm"):

            new_row = [
                data["time"],
                data["driver"],
                data["route"],
                data["customer"],
                data["order_id"],
                data["status"],
                data["notes"],
                data["image"]
            ]

            sheet.append_row(new_row)

            st.session_state.review = None
            st.success("Saved ✅")
            st.rerun()

else:

    with st.form("form"):

        status = st.radio("Status", ["Delivered","Failed"])
        notes = st.text_area("Notes")
        photo = st.file_uploader("Upload Photo", type=["jpg","png"])

        if photo:
            st.image(photo)

        submitted = st.form_submit_button("Submit")

        if submitted:

            image_data = ""
            if photo:
                image_data = base64.b64encode(photo.read()).decode()

            st.session_state.review = {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "driver": driver,
                "route": route,
                "customer": customer,
                "order_id": order_id,
                "status": status,
                "notes": notes,
                "image": image_data
            }

            st.rerun()
