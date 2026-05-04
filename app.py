import streamlit as st
import pandas as pd
from datetime import datetime
import os, csv
import urllib.parse

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
# MANAGER: UPLOAD + DATE SELECT
# -----------------------------
if st.session_state.auth["role"] == "manager":

    st.sidebar.header("📂 Daily File")

    uploaded_file = st.sidebar.file_uploader("Upload today's file", type=["txt"])

    if uploaded_file:
        today = datetime.now().strftime("%Y-%m-%d")

        os.makedirs("data", exist_ok=True)

        # Save today's file
        with open("current_day.txt", "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Save historical copy
        with open(f"data/{today}.txt", "wb") as f:
            f.write(uploaded_file.getbuffer())

        st.sidebar.success(f"Saved for {today}")

    # Date selector
    files = sorted(os.listdir("data"), reverse=True) if os.path.exists("data") else []
    selected_file = st.sidebar.selectbox("📅 View date", ["Today"] + files)

    if selected_file == "Today":
        if os.path.exists("current_day.txt"):
            raw = pd.read_csv("current_day.txt", sep="\t")
        else:
            st.warning("Upload today's file")
            st.stop()
    else:
        raw = pd.read_csv(f"data/{selected_file}", sep="\t")

else:
    # DRIVER always uses current day
    if os.path.exists("current_day.txt"):
        raw = pd.read_csv("current_day.txt", sep="\t")
    else:
        st.warning("🚧 Waiting for today's delivery file")
        st.stop()

# -----------------------------
# LOAD ROUTE MAP
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
# COMPLETED
# -----------------------------
if os.path.exists("deliveries.csv"):
    completed = pd.read_csv("deliveries.csv")
else:
    completed = pd.DataFrame()

os.makedirs("photos", exist_ok=True)

# -----------------------------
# MANAGER VIEW
# -----------------------------
if st.session_state.auth["role"] == "manager":

    st.title("📊 Manager Dashboard")

    st.subheader("📦 Deliveries")
    st.dataframe(jobs[["driver", "route", "customer", "order_id"]])

    st.subheader("📸 PODs")

    if not completed.empty:
        i = st.selectbox(
            "Select delivery",
            completed.index,
            format_func=lambda x: f"{completed.loc[x,'customer']} ({completed.loc[x,'driver']})"
        )

        r = completed.loc[i]

        st.write(r)

        if pd.notna(r.get("image")):
            path = f"photos/{r['image']}"
            if os.path.exists(path):
                st.image(path)

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
    st.success("🎉 All deliveries complete")
    st.stop()

idx = st.selectbox(
    "Select Delivery",
    driver_jobs.index,
    format_func=lambda i: driver_jobs.loc[i, "customer"]
)

row = driver_jobs.loc[idx]

st.write(row["customer"])
st.write(row["order_id"])
