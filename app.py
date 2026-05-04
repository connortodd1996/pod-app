import streamlit as st
import pandas as pd
from datetime import datetime
import os, csv

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
div.stButton > button {
    height:60px;
    font-size:18px;
    border-radius:12px;
}
.green button {
    background-color:#16a34a !important;
    color:white !important;
}
.red button {
    background-color:#dc2626 !important;
    color:white !important;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# SESSION STATE
# -----------------------------
if "review_data" not in st.session_state:
    st.session_state.review_data = None

if "auth" not in st.session_state:
    st.session_state.auth = {"ok": False, "role": None, "driver": None}

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
# FILE SYSTEM
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
jobs = jobs.drop(columns=["customer_x", "customer_y"], errors="ignore")

jobs["driver"] = jobs["driver"].fillna("Unassigned")
jobs["route"] = jobs["route"].fillna("Unknown")

# -----------------------------
# POD STORAGE
# -----------------------------
os.makedirs("deliveries", exist_ok=True)
os.makedirs("photos", exist_ok=True)

pod_file = f"deliveries/{selected_date}.csv"

if os.path.exists(pod_file):
    try:
        completed = pd.read_csv(pod_file, on_bad_lines='skip')
        done_ids = completed["order_id"].astype(str)
    except:
        completed = pd.DataFrame()
        done_ids = []
else:
    completed = pd.DataFrame()
    done_ids = []

jobs = jobs[~jobs["order_id"].astype(str).isin(done_ids)]

# -----------------------------
# MANAGER VIEW
# -----------------------------
if st.session_state.auth["role"] == "manager":

    st.title(f"📊 Manager Dashboard ({selected_date})")

    st.dataframe(jobs[["driver","route","customer","order_id"]])

    if not completed.empty:
        i = st.selectbox("View POD", completed.index)
        r = completed.loc[i]

        st.write(r)

        if pd.notna(r.get("image")):
            path = f"photos/{r['image']}"
            if os.path.exists(path):
                st.image(path)

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

options = driver_jobs.index.tolist()

idx = st.selectbox(
    "Select Delivery",
    options,
    index=0,
    format_func=lambda i: driver_jobs.loc[i,"customer"]
)

row = driver_jobs.loc[idx]

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
if st.session_state.review_data:

    data = st.session_state.review_data

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
        if st.button("❌ Cancel"):
            st.session_state.review_data = None
            st.rerun()

    with col2:
        if st.button("✅ Confirm"):

            df = pd.DataFrame([data])
            exists = os.path.isfile(pod_file)

            df.to_csv(
                pod_file,
                mode="a",
                header=not exists,
                index=False,
                quoting=csv.QUOTE_ALL
            )

            st.session_state.review_data = None
            st.rerun()

else:

    with st.form("form"):

        status = st.radio("Status", ["Delivered","Failed"])
        photo = st.file_uploader("Upload Photo", type=["jpg","png"])
        notes = st.text_area("Notes")

        if photo:
            st.image(photo)

        submitted = st.form_submit_button("Submit")

        if submitted:

            filename = None

            if photo:
                filename = f"{order_id}_{datetime.now().strftime('%H%M%S')}.jpg"
                with open(f"photos/{filename}", "wb") as f:
                    f.write(photo.getbuffer())

            st.session_state.review_data = {
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
