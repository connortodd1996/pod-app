import streamlit as st
import pandas as pd
from datetime import datetime
import os, csv
import urllib.parse
import base64

# -----------------------------
# LOAD LOGO
# -----------------------------
def get_base64_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

logo_base64 = ""
if os.path.exists("logo.png"):
    logo_base64 = get_base64_image("logo.png")

# -----------------------------
# STYLE
# -----------------------------
st.set_page_config(page_title="POD System", layout="centered")

st.markdown(f"""
<style>
.stApp {{
    background-color: #f9fafb;
    background-image: url("data:image/png;base64,{logo_base64}");
    background-repeat: no-repeat;
    background-position: center;
    background-size: 300px;
    background-attachment: fixed;
}}

.stApp::before {{
    content: "";
    position: fixed;
    width: 100%;
    height: 100%;
    background: rgba(255,255,255,0.92);
    z-index: -1;
}}

.card {{
    padding: 15px;
    border-radius: 12px;
    background-color: white;
    margin-bottom: 10px;
}}

.stButton>button {{
    height: 60px;
    width: 100%;
    font-size: 18px;
    border-radius: 12px;
}}
</style>
""", unsafe_allow_html=True)

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

if "auth" not in st.session_state:
    st.session_state.auth = {"ok": False, "role": None, "driver": None}

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
                st.session_state.auth = {"ok": True, "role": "manager"}
                st.rerun()
            else:
                st.error("Wrong PIN")

    st.stop()

# -----------------------------
# LOAD ROUTE MAP
# -----------------------------
route_map = pd.read_csv("route_map.csv")
route_map.columns = route_map.columns.str.strip()

# -----------------------------
# MANAGER DATE SELECTOR
# -----------------------------
if st.session_state.auth["role"] == "manager":

    st.sidebar.header("📅 Select Date")

    files = []
    if os.path.exists("data"):
        files = sorted(os.listdir("data"), reverse=True)

    selected_file = st.sidebar.selectbox("Choose a date", files)

    if selected_file:
        raw = pd.read_csv(f"data/{selected_file}", sep="\t")
    else:
        st.warning("No data files found")
        st.stop()

else:
    # DRIVER uses current day
    if os.path.exists("current_day.txt"):
        raw = pd.read_csv("current_day.txt", sep="\t")
    else:
        st.warning("🚧 Waiting for today's delivery file")
        st.stop()

# -----------------------------
# CLEAN DATA
# -----------------------------
raw.columns = raw.columns.str.strip()

clean = raw[["Co./Last Name", "Invoice No.", "Record ID"]].dropna().drop_duplicates()
clean.columns = ["customer", "order_id", "zone"]

clean["key"] = clean["customer"].str.strip().str.lower()
route_map["key"] = route_map["customer"].str.strip().str.lower()

jobs = clean.merge(route_map, on="key", how="left")

jobs["customer"] = jobs["customer_x"]
jobs = jobs.drop(columns=["customer_x", "customer_y"], errors="ignore")

jobs["driver"] = jobs["driver"].fillna("Unassigned")
jobs["route"] = jobs["route"].fillna("Unknown")

# -----------------------------
# COMPLETED (PODS)
# -----------------------------
if os.path.exists("deliveries.csv"):
    completed = pd.read_csv("deliveries.csv")
else:
    completed = pd.DataFrame()

# -----------------------------
# MANAGER VIEW
# -----------------------------
if st.session_state.auth["role"] == "manager":

    st.title("📊 Manager Dashboard")

    st.subheader("📦 Deliveries for selected date")
    st.dataframe(jobs[["driver", "route", "customer", "order_id"]])

    st.subheader("📸 Completed PODs")

    if not completed.empty:
        i = st.selectbox(
            "Select delivery",
            completed.index,
            format_func=lambda x: f"{completed.loc[x,'customer']} ({completed.loc[x,'driver']})"
        )

        r = completed.loc[i]

        st.markdown(f"""
        <div class="card">
        <b>{r['customer']}</b><br>
        Driver: {r['driver']}<br>
        Status: {r['status']}<br>
        Notes: {r['notes']}
        </div>
        """, unsafe_allow_html=True)

        if pd.notna(r.get("image")):
            path = f"photos/{r['image']}"
            if os.path.exists(path):
                st.image(path)

    else:
        st.info("No completed deliveries yet")

    st.stop()

# -----------------------------
# DRIVER VIEW (UNCHANGED)
# -----------------------------
driver = st.session_state.auth["driver"]
st.title(f"🚚 {driver}")

driver_jobs = jobs[jobs["driver"] == driver]

if driver_jobs.empty:
    st.success("🎉 All deliveries complete")
    st.stop()

idx = st.selectbox(
    "📦 Select Delivery",
    driver_jobs.index,
    format_func=lambda i: driver_jobs.loc[i, "customer"]
)

row = driver_jobs.loc[idx]

customer = row["customer"]
order_id = row["order_id"]
route = row["route"]

st.write(customer)
st.write(order_id)
