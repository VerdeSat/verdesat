import json
import logging
from pathlib import Path
from typing import Any, cast

import geopandas as gpd
import pandas as pd
import streamlit as st

from verdesat.biodiv.bscore import BScoreCalculator
from verdesat.core.config import ConfigManager
from verdesat.core.logger import Logger
from verdesat.core.storage import LocalFS
from verdesat.geo.aoi import AOI
from verdesat.project.project import VerdeSatProject
from verdesat.services.msa import MSAService
from verdesat.webapp.components.charts import (
    msavi_bar_chart,
    ndvi_decomposition_chart,
)
from verdesat.webapp.components.kpi_cards import Metrics, bscore_gauge, display_metrics
from verdesat.webapp.components.map_widget import display_map
from verdesat.webapp.services.compute import ComputeService
from verdesat.webapp.services.exports import export_metrics_csv, export_metrics_pdf
from verdesat.webapp.services.r2 import signed_url


logger = Logger.get_logger(__name__)

CONFIG = ConfigManager(
    str(Path(__file__).resolve().parents[1] / "resources" / "webapp.toml")
)
_demo_cfg = CONFIG.get("demo", {})
_defaults = CONFIG.get("defaults", {})

DEMO_AOI_KEY = _demo_cfg.get("aoi_key", "resources/reference.geojson")
_demo_aois = _demo_cfg.get("aois", [])

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
start_year, end_year = st.sidebar.slider(
    "Years",
    2017,
    2024,
    value=(
        int(_defaults.get("start_year", 2019)),
        int(_defaults.get("end_year", 2024)),
    ),
)
_aoi_options = [a["id"] for a in _demo_aois] or [1, 2]


def _fmt_aoi(x: int) -> str:
    for a in _demo_aois:
        if a["id"] == x:
            return a.get("name", f"AOI {x}")
    return f"AOI {x}"


aoi_id = st.sidebar.selectbox("Demo AOI", _aoi_options, format_func=_fmt_aoi)
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


@st.cache_data
def load_demo_aoi() -> gpd.GeoDataFrame:
    """Fetch the demo AOI from R2 and cache it locally."""

    logger.info("Loading demo AOI from %s", DEMO_AOI_KEY)
    try:
        return gpd.read_file(signed_url(DEMO_AOI_KEY))
    except Exception:
        logger.exception("Failed to load demo AOI")
        raise


@st.cache_data
def load_demo_cogs() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Return lists of NDVI and MSAVI COGs for the demo AOIs."""
    ndvi_cogs = [(f"NDVI {a['name']}", a["ndvi"]) for a in _demo_aois]
    msavi_cogs = [(f"MSAVI {a['name']}", a["msavi"]) for a in _demo_aois]
    return ndvi_cogs, msavi_cogs


DEMO_AOI = load_demo_aoi()
NDVI_COGS, MSAVI_COGS = load_demo_cogs()

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
            feature_collection = json.load(uploaded_file)
            aois = AOI.from_geojson(feature_collection)
            st.session_state["aois"] = aois
            project = VerdeSatProject("Web Upload", "WebApp", aois, ConfigManager())
            st.session_state["project"] = project
            gdf = gpd.GeoDataFrame(
                [{**a.static_props, "geometry": a.geometry} for a in aois],
                crs="EPSG:4326",
            )
            logger.info("Computing live metrics")
            metrics_data, metrics_df, ndvi_chart_df, msavi_chart_df = (
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
            metrics_df = pd.DataFrame(
                [
                    {
                        k: v
                        for k, v in metrics_data.items()
                        if k in {"intactness", "shannon", "fragmentation", "bscore"}
                    }
                ]
            )
            current_gdf = demo_gdf
            current_aoi_id = aoi_id
        metrics = Metrics(**cast(dict[str, Any], metrics_data))
        with col2:
            bscore_gauge(metrics.bscore)
        st.markdown("---")
        display_metrics(metrics)

        aois = st.session_state.get("aois", AOI.from_gdf(current_gdf))
        export_links: list[tuple[Any, str, str]] = []
        for idx, (aoi, row) in enumerate(
            zip(aois, metrics_df.to_dict(orient="records"))
        ):
            ndvi_df = ndvi_chart_df if idx == 0 else None
            msavi_df = msavi_chart_df if idx == 0 else None
            csv_url = export_metrics_csv(row, aoi)
            project_name = (
                st.session_state.get("project").name
                if st.session_state.get("project")
                else "VerdeSat Demo"
            )
            pdf_url = export_metrics_pdf(
                row,
                aoi,
                project=project_name,
                ndvi_df=ndvi_df,
                msavi_df=msavi_df,
            )
            export_links.append((aoi.static_props.get("id", idx), csv_url, pdf_url))
        for pid, csv_url, pdf_url in export_links:
            st.markdown(
                f"AOI {pid}: [⬇️ Download CSV]({csv_url}) | [⬇️ Download PDF]({pdf_url})"
            )

        if st.session_state.get("user") and st.session_state.get("project"):
            compute_service.persist_project(st.session_state["project"])
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
