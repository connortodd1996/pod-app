import streamlit as st
import pandas as pd
from datetime import datetime
import os, csv
import urllib.parse
import base64

# -----------------------------
# LOAD LOGO AS BASE64 (for background)
# -----------------------------
def get_base64_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

logo_base64 = ""
if os.path.exists("logo.png"):
    logo_base64 = get_base64_image("logo.png")

# -----------------------------
# PAGE CONFIG + STYLE
# -----------------------------
st.set_page_config(page_title="POD System", layout="centered")

st.markdown(f"""
<style>

/* Background */
.stApp {{
    background-color: #f9fafb;
    background-image: url("data:image/png;base64,{logo_base64}");
    background-repeat: no-repeat;
    background-position: center;
    background-size: 300px;
    background-attachment: fixed;
}}

/* Overlay fade */
.stApp::before {{
    content: "";
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(255,255,255,0.92);
    z-index: -1;
}}

/* Cards */
.card {{
    padding: 15px;
    border-radius: 12px;
    background-color: white;
    margin-bottom: 10px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}}

/* Buttons */
.stButton>button {{
    height: 60px;
    width: 100%;
    font-size: 18px;
    border-radius: 12px;
}}

/* Text */
h1, h2, h3, p, label {{
    color: #111827 !important;
}}

</style>
""", unsafe_allow_html=True)

# -----------------------------
# LOGIN DATA
# -----------------------------
DRIVER_PINS = {
    "Connor": "1234",
    "Andy": "5678",
    "Kelvin": "1111",
    "Ken": "2222",
    "Mark": "3333"
}

MANAGER_PIN = "9999"

# -----------------------------
# SESSION
# -----------------------------
if "auth" not in st.session_state:
    st.session_state.auth = {"ok": False, "role": None, "driver": None}

# -----------------------------
# LOGIN
# -----------------------------
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
# LOAD DATA
# -----------------------------
raw = pd.read_csv("MYOB_Transactions_2026-05-02.TXT", sep="\t")
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
    done_ids = completed["order_id"].astype(str)
else:
    completed = pd.DataFrame()
    done_ids = []

jobs = jobs[~jobs["order_id"].astype(str).isin(done_ids)]

os.makedirs("photos", exist_ok=True)

def maps_link(q):
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(q)

# -----------------------------
# LOGOUT
# -----------------------------
if st.button("🚪 Logout"):
    st.session_state.auth = {"ok": False, "role": None, "driver": None}
    st.rerun()

# -----------------------------
# MANAGER VIEW
# -----------------------------
if st.session_state.auth["role"] == "manager":

    st.title("📊 Manager Dashboard")

    st.subheader("📦 Pending Deliveries")
    st.dataframe(jobs[["driver", "route", "customer", "order_id"]])

    st.subheader("✅ Completed Deliveries")

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

        st.link_button("🧭 Open in Maps", maps_link(r["customer"]))

        if pd.notna(r.get("image")):
            path = f"photos/{r['image']}"
            if os.path.exists(path):
                st.image(path)

    else:
        st.info("No completed deliveries yet")

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
    "📦 Select Delivery",
    driver_jobs.index,
    format_func=lambda i: driver_jobs.loc[i, "customer"]
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

st.link_button("🧭 Navigate", maps_link(customer))

# -----------------------------
# FORM
# -----------------------------
with st.form("form"):

    status = st.radio("Status", ["Delivered", "Failed"])
    photo = st.file_uploader("📸 Upload Photo", type=["jpg", "png"])
    notes = st.text_area("Notes")

    if photo:
        st.image(photo)

    submitted = st.form_submit_button("✅ Submit Delivery")

    if submitted:
        filename = None

        if photo:
            filename = f"{order_id}_{datetime.now().strftime('%H%M%S')}.jpg"
            with open(f"photos/{filename}", "wb") as f:
                f.write(photo.getbuffer())

        data = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "driver": driver,
            "route": route,
            "customer": customer,
            "order_id": order_id,
            "status": status,
            "notes": notes,
            "image": filename
        }

        df = pd.DataFrame([data])
        exists = os.path.isfile("deliveries.csv")

        df.to_csv(
            "deliveries.csv",
            mode="a",
            header=not exists,
            index=False,
            quoting=csv.QUOTE_ALL
        )

        st.success("Saved ✅")
        st.rerun()