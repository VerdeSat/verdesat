import streamlit as st
import geopandas as gpd
from verdesat.webapp.components.map_widget import display_map

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

# --- load demo AOI & rasters (fast; cached) -------------------
DEMO_AOI = gpd.read_file(
    Path(__file__).parent / ".." / "resources" / "reference.geojson"
)
NDVI_COGS = [
    ("NDVI AOI 1", "resources/NDVI_1_2024-01-01.tif"),
    ("NDVI AOI 2", "resources/NDVI_2_2024-01-01.tif"),
]

MSAVI_COGS = [
    ("MSAVI AOI 1", "resources/MSAVI_1_2024-01-01.tif"),
    ("MSAVI AOI 2", "resources/MSAVI_2_2024-01-01.tif"),
]

layer_state = {"ndvi": True, "msavi": True}

with col1:
    layer_state = display_map(
        DEMO_AOI, NDVI_COGS, MSAVI_COGS, layer_state
    )
