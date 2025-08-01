import logging

import geopandas as gpd
import streamlit as st
from typing import Any, cast

from verdesat.geo.aoi import AOI
from verdesat.services.msa import MSAService
from verdesat.biodiv.bscore import BScoreCalculator
from verdesat.core.logger import Logger
from verdesat.core.storage import LocalFS
from verdesat.webapp.services.compute import ComputeService
from verdesat.webapp.services.r2 import signed_url
from verdesat.webapp.components.map_widget import display_map
from verdesat.webapp.components.kpi_cards import Metrics, bscore_gauge, display_metrics
from verdesat.webapp.components.charts import (
    msavi_bar_chart,
    ndvi_decomposition_chart,
)
from verdesat.webapp.services.exports import export_metrics_csv, export_metrics_pdf


logger = Logger.get_logger(__name__)
compute_service = ComputeService(MSAService(), BScoreCalculator(), LocalFS())

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
start_year, end_year = st.sidebar.slider("Years", 2017, 2024, value=(2019, 2024))
aoi_id = st.sidebar.selectbox("Demo AOI", [1, 2], format_func=lambda x: f"AOI {x}")
uploaded_file = None
if mode == "Upload AOI":
    uploaded_file = st.sidebar.file_uploader("GeoJSON AOI", type="geojson")
run_button = st.sidebar.button("Run 🚀")

# ---- Main canvas placeholders ---------------------------------------------
st.title("VerdeSat Biodiversity Dashboard (Skeleton)")

col1, col2 = st.columns([3, 1])
with col1:
    st.write("🗺️  Map will appear here")
with col2:
    placeholder_gauge = st.empty()

st.markdown("---")
st.info("This is just the skeleton—compute & map coming next.")

# ---- Dev helper ------------------------------------------------------------
log_handler: logging.Handler | None = None
if st.sidebar.checkbox("Show log pane"):
    log_container = st.empty()

    class StreamlitHandler(logging.Handler):
        """Stream logging records to a Streamlit code block."""

        def __init__(self, container: st.delta_generator.DeltaGenerator) -> None:
            super().__init__()
            self.container = container
            self.lines: list[str] = []

        def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - UI
            self.lines.append(self.format(record))
            self.container.code("\n".join(self.lines))

    root_logger = logging.getLogger()
    for existing in list(root_logger.handlers):
        if isinstance(existing, StreamlitHandler):
            root_logger.removeHandler(existing)

    log_handler = StreamlitHandler(log_container)
    log_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    root_logger.addHandler(log_handler)

#
# --- load demo AOI & rasters (fast; cached) -------------------
DEMO_AOI_KEY = "resources/reference.geojson"  # adjust if key differs
logger.info("Loading demo AOI from %s", DEMO_AOI_KEY)
try:
    DEMO_AOI = gpd.read_file(signed_url(DEMO_AOI_KEY))
except Exception:
    logger.exception("Failed to load demo AOI")
    raise
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
    layer_state = display_map(DEMO_AOI, NDVI_COGS, MSAVI_COGS, layer_state)
ndvi_chart_df = None
msavi_chart_df = None
current_aoi_id = aoi_id

if run_button:
    try:
        if mode == "Upload AOI" and uploaded_file is not None:
            logger.info("Loading uploaded AOI")
            gdf = gpd.read_file(uploaded_file)
            logger.info("Computing live metrics")
            metrics_data, ndvi_chart_df, msavi_chart_df = (
                compute_service.compute_live_metrics(
                    gdf, start_year=start_year, end_year=end_year
                )
            )
            current_gdf = gdf
            current_aoi_id = 0
        else:
            logger.info("Loading demo AOI %s", aoi_id)
            demo_gdf = DEMO_AOI[DEMO_AOI["id"] == aoi_id]
            logger.info("Computing demo metrics")
            metrics_data, ndvi_chart_df, msavi_chart_df = (
                compute_service.load_demo_metrics(
                    aoi_id, demo_gdf, start_year=start_year, end_year=end_year
                )
            )
            current_gdf = demo_gdf
            current_aoi_id = aoi_id
        metrics = Metrics(**cast(dict[str, Any], metrics_data))
        with col2:
            bscore_gauge(metrics.bscore)
        st.markdown("---")
        display_metrics(metrics)

        aoi_obj = AOI.from_gdf(current_gdf)[0]
        logger.info("Exporting metrics")
        csv_url = export_metrics_csv(metrics, aoi_obj)
        pdf_url = export_metrics_pdf(
            metrics,
            aoi_obj,
            project="VerdeSat Demo",
            ndvi_df=ndvi_chart_df,
            msavi_df=msavi_chart_df,
        )
        st.markdown(f"[⬇️ Download CSV]({csv_url})")
        st.markdown(f"[⬇️ Download PDF]({pdf_url})")
    except Exception:
        logger.exception("Processing failed")
        st.error("Processing failed; see log pane for details.")

# ---- Charts tab ------------------------------------------------------------
st.markdown("---")
tab_decomp, tab_msavi, tab_about = st.tabs(["NDVI Decomp", "MSAVI", "About"])
with tab_decomp:
    if ndvi_chart_df is not None:
        ndvi_decomposition_chart(
            data=ndvi_chart_df, start_year=start_year, end_year=end_year
        )
    else:
        ndvi_decomposition_chart(
            current_aoi_id, start_year=start_year, end_year=end_year
        )
with tab_msavi:
    if msavi_chart_df is not None:
        msavi_bar_chart(data=msavi_chart_df, start_year=start_year, end_year=end_year)
    else:
        msavi_bar_chart(current_aoi_id, start_year=start_year, end_year=end_year)
with tab_about:
    st.write("NDVI decomposition and MSAVI plots from demo datasets.")
