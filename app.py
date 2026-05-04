import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="POD System", layout="centered")

# -----------------------------
# GOOGLE SHEETS SETUP
# -----------------------------
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = json.loads(st.secrets["gcp_service_account"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

sheet = client.open("POD_DATA").sheet1

# -----------------------------
# SESSION STATE
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
# LOAD COMPLETED FROM SHEET
# -----------------------------
records = sheet.get_all_records()
completed = pd.DataFrame(records)

# -----------------------------
# LOAD TODAY'S JOBS
# -----------------------------
try:
    raw = pd.read_csv("current_day.txt", sep="\t")
except:
    st.error("Missing current_day.txt file")
    st.stop()

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
jobs["route"] = jobs["route"].fillna("Unknown")

# REMOVE COMPLETED
if not completed.empty:
    jobs = jobs[~jobs["order_id"].astype(str).isin(completed["order_id"].astype(str))]

# -----------------------------
# MANAGER VIEW
# -----------------------------
if st.session_state.auth["role"] == "manager":

    st.title("📊 Manager Dashboard")

    if completed.empty:
        st.info("No deliveries yet")
    else:
        st.dataframe(completed)

    st.stop()

# -----------------------------
# DRIVER VIEW
# -----------------------------
driver = st.session_state.auth["driver"]

driver_jobs = jobs[jobs["driver"] == driver]

if driver_jobs.empty:
    st.success("All deliveries complete")
    st.stop()

# Always show next job
row = driver_jobs.iloc[0]

customer = row["customer"]
order_id = row["order_id"]
route = row["route"]

st.title(customer)
st.write(f"Order: {order_id}")
st.write(f"Route: {route}")

# -----------------------------
# CONFIRM FLOW
# -----------------------------
if st.session_state.review:

    data = st.session_state.review

    st.warning("⚠️ Confirm Delivery")

    st.write(data)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Cancel"):
            st.session_state.review = None
            st.rerun()

    with col2:
        if st.button("Confirm"):

            sheet.append_row(list(data.values()))

            st.session_state.review = None
            st.rerun()

else:

    with st.form("form"):

        status = st.radio("Status", ["Delivered","Failed"])
        notes = st.text_area("Notes")

        submitted = st.form_submit_button("Submit")

        if submitted:

            st.session_state.review = {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "driver": driver,
                "route": route,
                "customer": customer,
                "order_id": order_id,
                "status": status,
                "notes": notes,
                "image": ""
            }

            st.rerun()
