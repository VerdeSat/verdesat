import streamlit as st
from pathlib import Path

# ---- Page config -----------------------------------------------------------
st.set_page_config(
    page_title="VerdeSat B-Score",
    page_icon="🌳",
    layout="wide",
)

# ---- Assets & theme --------------------------------------------------------
# (we'll inject CSS later; keep it simple for now)

# ---- Sidebar controls ------------------------------------------------------
st.sidebar.header("VerdeSat B-Score v0.1")
mode = st.sidebar.radio("Mode", ["Demo AOI", "Upload AOI"])
year = st.sidebar.slider("Year", 2017, 2024, value=2024)
run_button = st.sidebar.button("Run 🚀")

# ---- Main canvas placeholders ---------------------------------------------
st.title("VerdeSat Biodiversity Dashboard (Skeleton)")

col1, col2 = st.columns([3, 1])
with col1:
    st.write("🗺️  Map will appear here")
with col2:
    st.metric("B-Score", "—")

st.markdown("---")
st.info("This is just the skeleton—compute & map coming next.")

# ---- Dev helper ------------------------------------------------------------
if st.sidebar.checkbox("Show log pane"):
    st.code("Logger output placeholder")
