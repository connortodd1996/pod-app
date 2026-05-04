import streamlit as st
import pandas as pd
from datetime import datetime
import os, csv
import base64

# -----------------------------
# CONFIG
# -----------------------------
st.set_page_config(page_title="POD System", layout="centered")

# -----------------------------
# HEADER STYLE
# -----------------------------
st.markdown("""
<style>
.header {
    display:flex;
    justify-content:space-between;
    align-items:center;
    padding:10px 0;
}
.card {
    padding:15px;
    border-radius:12px;
    background-color:#ffffff;
    margin-bottom:10px;
    box-shadow:0 2px 6px rgba(0,0,0,0.05);
}
.stButton>button {
    height:50px;
    width:100%;
    border-radius:10px;
    font-size:16px;
}
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
# HEADER BAR
# -----------------------------
col1, col2 = st.columns([4,1])

with col1:
    st.markdown("### 🚚 POD System")

with col2:
    if st.button("Logout"):
        st.session_state.auth = {"ok": False, "role": None, "driver": None}
        st.rerun()

# -----------------------------
# DATE + FILE HANDLING
# -----------------------------
today = datetime.now().strftime("%Y-%m-%d")

if st.session_state.auth["role"] == "manager":

    st.sidebar.header("📂 Daily File")

    uploaded_file = st.sidebar.file_uploader("Upload today's file", type=["txt"])

    if uploaded_file:
        os.makedirs("data", exist_ok=True)

        with open("current_day.txt", "wb") as f:
            f.write(uploaded_file.getbuffer())

        with open(f"data/{today}.txt", "wb") as f:
            f.write(uploaded_file.getbuffer())

        st.sidebar.success(f"Saved for {today}")

    files = sorted(os.listdir("data"), reverse=True) if os.path.exists("data") else []
    selected = st.sidebar.selectbox("📅 View date", ["Today"] + files)

    if selected == "Today":
        if os.path.exists("current_day.txt"):
            raw = pd.read_csv("current_day.txt", sep="\t")
            selected_date = today
        else:
            st.warning("Upload today's file")
            st.stop()
    else:
        raw = pd.read_csv(f"data/{selected}", sep="\t")
        selected_date = selected.replace(".txt", "")

else:
    if os.path.exists("current_day.txt"):
        raw = pd.read_csv("current_day.txt", sep="\t")
        selected_date = today
    else:
        st.warning("Waiting for today's file")
        st.stop()

# -----------------------------
# DATA CLEAN
# -----------------------------
route_map = pd.read_csv("route_map.csv")

raw.columns = raw.columns.str.strip()
route_map.columns = route_map.columns.str.strip()

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
# POD STORAGE BY DATE
# -----------------------------
os.makedirs("deliveries", exist_ok=True)
pod_file = f"deliveries/{selected_date}.csv"

if os.path.exists(pod_file):
    completed = pd.read_csv(pod_file)
    done_ids = completed["order_id"].astype(str)
else:
    completed = pd.DataFrame()
    done_ids = []

jobs = jobs[~jobs["order_id"].astype(str).isin(done_ids)]

# -----------------------------
# MANAGER VIEW
# -----------------------------
if st.session_state.auth["role"] == "manager":

    st.title(f"📊 Dashboard ({selected_date})")

    st.subheader("📦 Deliveries")
    st.dataframe(jobs[["driver", "route", "customer", "order_id"]])

    st.subheader("📸 PODs")

    if not completed.empty:
        idx = st.selectbox(
            "Select delivery",
            completed.index,
            format_func=lambda i: f"{completed.loc[i,'customer']} ({completed.loc[i,'driver']})"
        )

        r = completed.loc[idx]

        st.markdown(f"""
        <div class="card">
        <b>{r['customer']}</b><br>
        Driver: {r['driver']}<br>
        Time: {r['time']}
        </div>
        """, unsafe_allow_html=True)

    else:
        st.info("No PODs yet")

    st.stop()

# -----------------------------
# DRIVER VIEW
# -----------------------------
driver = st.session_state.auth["driver"]
st.title(f"🚚 {driver}")

driver_jobs = jobs[jobs["driver"] == driver]

if driver_jobs.empty:
    st.success("All deliveries complete")
    st.stop()

idx = st.selectbox(
    "Select delivery",
    driver_jobs.index,
    format_func=lambda i: driver_jobs.loc[i, "customer"]
)

row = driver_jobs.loc[idx]

st.markdown(f"""
<div class="card">
<b>{row['customer']}</b><br>
Order: {row['order_id']}<br>
Route: {row['route']}
</div>
""", unsafe_allow_html=True)

if st.button("Confirm Delivery"):

    data = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "driver": driver,
        "route": row["route"],
        "customer": row["customer"],
        "order_id": row["order_id"]
    }

    df = pd.DataFrame([data])
    exists = os.path.isfile(pod_file)

    df.to_csv(
        pod_file,
        mode="a",
        header=not exists,
        index=False,
        quoting=csv.QUOTE_ALL
    )

    st.success("Delivery saved")
    st.rerun()
