import streamlit as st
import pandas as pd
from datetime import datetime
import os, csv

st.set_page_config(page_title="POD System", layout="centered")

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
# LOAD FILE
# -----------------------------
today = datetime.now().strftime("%Y-%m-%d")

if not os.path.exists("current_day.txt"):
    st.warning("Upload today's file first")
    st.stop()

raw = pd.read_csv("current_day.txt", sep="\t")

# -----------------------------
# CLEAN DATA
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
jobs = jobs.drop(columns=["customer_x","customer_y"], errors="ignore")

jobs["driver"] = jobs["driver"].fillna("Unassigned")
jobs["route"] = jobs["route"].fillna("Unknown")

# -----------------------------
# POD STORAGE
# -----------------------------
os.makedirs("deliveries", exist_ok=True)
os.makedirs("photos", exist_ok=True)

pod_file = f"deliveries/{today}.csv"

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

    st.title("📊 Manager Dashboard")

    st.subheader("Completed Deliveries")

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
        st.info("No deliveries completed yet")

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

# ALWAYS show first job (NO dropdown issues)
row = driver_jobs.iloc[0]

customer = row["customer"]
order_id = row["order_id"]
route = row["route"]

st.markdown(f"""
### {customer}
Order: {order_id}  
Route: {route}
""")

# -----------------------------
# FLOW
# -----------------------------
if st.session_state.review:

    data = st.session_state.review

    st.warning("Confirm delivery")

    st.write(data)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Cancel"):
            st.session_state.review = None
            st.rerun()

    with col2:
        if st.button("Confirm"):

            df = pd.DataFrame([data])
            exists = os.path.isfile(pod_file)

            df.to_csv(
                pod_file,
                mode="a",
                header=not exists,
                index=False,
                quoting=csv.QUOTE_ALL
            )

            st.session_state.review = None
            st.rerun()

else:

    with st.form("form"):

        status = st.radio("Status", ["Delivered","Failed"])
        photo = st.file_uploader("Upload Photo", type=["jpg","png"])
        notes = st.text_area("Notes")

        submitted = st.form_submit_button("Submit")

        if submitted:

            filename = None

            if photo:
                filename = f"{order_id}_{datetime.now().strftime('%H%M%S')}.jpg"
                with open(f"photos/{filename}", "wb") as f:
                    f.write(photo.getbuffer())

            st.session_state.review = {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "driver": driver,
                "route": route,
                "customer": customer,
                "order_id": order_id,
                "status": status,
                "notes": notes,
                "image": filename
            }

            st.rerun()
