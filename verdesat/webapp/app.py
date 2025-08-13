from __future__ import annotations

__doc__ = "Streamlit dashboard for visualising VerdeSat project metrics."

import json
import logging
import hashlib
from datetime import date
from pathlib import Path
from typing import cast

import geopandas as gpd
import pandas as pd
import streamlit as st

from verdesat.biodiv.bscore import BScoreCalculator
from verdesat.core.config import ConfigManager
from verdesat.core.logger import Logger
from verdesat.core.storage import LocalFS
from verdesat.project.project import Project
from verdesat.services.msa import MSAService
from verdesat.webapp.components.charts import (
    msavi_bar_chart_all,
    ndvi_component_chart,
)
from verdesat.webapp.components.kpi_cards import (
    aggregate_metrics,
    bscore_gauge,
    display_metrics,
)
from verdesat.webapp.components.map_widget import display_map
from verdesat.webapp.components.layout import (
    apply_theme,
    render_hero,
    render_navbar,
)
from verdesat.webapp.services.chip_service import EEChipServiceAdapter
from verdesat.webapp.services.project_compute import ProjectComputeService
from verdesat.webapp.services.r2 import signed_url
from verdesat.webapp.services.exports import export_project_pdf

# -------------------------------------------------------------------


logger = Logger.get_logger(__name__)

CONFIG = ConfigManager(
    str(Path(__file__).resolve().parents[1] / "resources" / "webapp.toml")
)
_demo_cfg = CONFIG.get("demo", {})
_defaults = CONFIG.get("defaults", {})
_map_fields = CONFIG.get("map", {}).get("fields", {})
DEMO_AOI_KEY = _demo_cfg.get("aoi_key", "resources/reference.geojson")

storage = LocalFS()
chip_service = EEChipServiceAdapter()
project_compute = ProjectComputeService(
    MSAService(), BScoreCalculator(), storage, chip_service, CONFIG
)


def load_demo_project() -> Project:
    """Load demo project from bundled GeoJSON and attach demo rasters."""

    gdf = gpd.read_file(signed_url(DEMO_AOI_KEY))
    geojson = json.loads(gdf.to_json())
    project = Project.from_geojson(
        geojson,
        CONFIG,
        name="Demo Project",
        customer="VerdeSat",
        storage=storage,
    )
    ndvi_paths: dict[str, str] = {}
    msavi_paths: dict[str, str] = {}
    for aoi_cfg in _demo_cfg.get("aois", []):
        aoi_id = str(aoi_cfg.get("id"))
        ndvi = aoi_cfg.get("ndvi")
        msavi = aoi_cfg.get("msavi")
        if ndvi:
            ndvi_paths[aoi_id] = ndvi
        if msavi:
            msavi_paths[aoi_id] = msavi
    if ndvi_paths or msavi_paths:
        project.attach_rasters(ndvi_paths, msavi_paths)
    return project


def compute_project(project: Project, start_year: int, end_year: int) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, str],
    dict[str, str],
    dict[str, dict[str, float | str]],
]:
    """Compute metrics and vegetation indices for *project*.

    The returned tuple includes per-AOI raster paths and metrics so callers can
    reattach them to freshly initialised :class:`Project` instances when
    rebuilding state from persisted caches.
    """

    progress_bar = st.progress(0.0, text="Running analysis...")

    def update_progress(frac: float) -> None:
        progress_bar.progress(frac, text="Running analysis...")

    metrics_df, ndvi_df, msavi_df = project_compute.compute(
        project,
        date(start_year, 1, 1),
        date(end_year, 12, 31),
        progress=update_progress,
    )
    progress_bar.empty()
    ndvi_paths = {
        aoi_id: layers.get("ndvi", "") for aoi_id, layers in project.rasters.items()
    }
    msavi_paths = {
        aoi_id: layers.get("msavi", "") for aoi_id, layers in project.rasters.items()
    }
    return (
        metrics_df,
        ndvi_df,
        msavi_df,
        ndvi_paths,
        msavi_paths,
        project.metrics.copy(),
    )


def report_controls(
    metrics_df: pd.DataFrame, project: Project, start_year: int, end_year: int
) -> None:
    """Display controls for generating a project-wide PDF report."""

    if st.button("Generate PDF report"):
        st.session_state["report_url"] = export_project_pdf(
            metrics_df, project, start_year, end_year
        )
    url = st.session_state.get("report_url")
    if url:
        st.markdown(f"[Download PDF report]({url})")


# ---- Page config -----------------------------------------------------------

if "sidebar_state" not in st.session_state:
    st.session_state.sidebar_state = "expanded"  # default

st.set_page_config(
    page_title="VerdeSat B-Score",
    page_icon="verdesat/webapp/themes/favicon.svg",
    layout="wide",
    initial_sidebar_state=st.session_state.sidebar_state,
)

apply_theme()
render_navbar()
render_hero(
    "VerdeSat Biodiversity Dashboard",
    "Screening-grade biodiversity & forest-health insights from satellites—ready for CSRD/TNFD drafts",
)


# ---- Sidebar ---------------------------------------------------------------
st.sidebar.header("VerdeSat B-Score v0.1.2")


# ---- Dev log pane ---------------------------------------------------------
class StreamlitHandler(logging.Handler):
    """Stream logging records to a Streamlit code block."""

    def __init__(self, container: st.delta_generator.DeltaGenerator) -> None:
        super().__init__()
        self.container = container
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - UI
        self.lines.append(self.format(record))
        self.container.code("\n".join(self.lines))


# Initialise run flag before drawing controls
if "run_requested" not in st.session_state:
    st.session_state["run_requested"] = False

if st.sidebar.button("Load demo project"):
    st.sidebar.caption(
        "Use case - Mexican reforestation project (AOI 1) next to a reference plot (AOI 2)."
    )
    st.session_state["project"] = load_demo_project()
    st.session_state["project_source"] = "demo"
    st.session_state.pop("results", None)
    st.session_state.pop("uploaded_filename", None)
    st.session_state.pop("uploaded_file_hash", None)
    st.session_state["run_requested"] = False
    # Drop any cached map from a previous project
    st.session_state.pop("main_map", None)
    st.session_state.pop("main_map_center", None)
    st.session_state.pop("main_map_zoom", None)

start_year, end_year = st.sidebar.slider(
    "Years",
    2019,
    2024,
    value=(
        int(_defaults.get("start_year", 2019)),
        int(_defaults.get("end_year", 2024)),
    ),
)

uploaded_file = st.sidebar.file_uploader("GeoJSON Project", type="geojson")
if uploaded_file is not None:
    # Always consider switching to the uploaded project if either the current
    # project was not sourced from an upload, or the file content has changed.
    try:
        uploaded_bytes = uploaded_file.getvalue()
    except Exception:
        uploaded_bytes = uploaded_file.read()  # fallback
    file_hash = hashlib.sha256(uploaded_bytes).hexdigest()

    should_reload = (
        st.session_state.get("project_source") != "upload"
        or st.session_state.get("uploaded_file_hash") != file_hash
    )

    if should_reload:
        max_bytes = 5 * 1024 * 1024  # 5MB
        if getattr(uploaded_file, "size", len(uploaded_bytes)) > max_bytes:
            st.sidebar.error("File too large; limit 5MB")
        else:
            try:
                geojson = json.loads(uploaded_bytes.decode("utf-8"))
            except Exception:
                st.sidebar.error("Invalid GeoJSON file")
            else:
                try:
                    meta = geojson.get("metadata", {})
                    st.session_state["project"] = Project.from_geojson(
                        geojson,
                        CONFIG,
                        name=meta.get("name"),
                        customer=meta.get("customer"),
                        storage=storage,
                    )
                except ValueError as exc:
                    st.sidebar.error(str(exc))
                else:
                    st.session_state["uploaded_filename"] = uploaded_file.name
                    st.session_state["uploaded_file_hash"] = file_hash
                    st.session_state["project_source"] = "upload"
                    st.session_state["run_requested"] = False
                    # Clear stale results and map state when switching projects
                    st.session_state.pop("results", None)
                    st.session_state.pop("main_map", None)
                    st.session_state.pop("main_map_center", None)
                    st.session_state.pop("main_map_zoom", None)

if st.sidebar.button(
    "Run analysis",
    help="Fetch satellite layers, compute metrics, and render results for your uploaded GeoJSON.",
):
    st.session_state["run_requested"] = True

show_log = st.sidebar.checkbox("Show log pane")
root_logger = logging.getLogger()
existing_handler = cast(logging.Handler | None, st.session_state.get("log_handler"))
if show_log:
    log_container = st.empty()
    if existing_handler:
        root_logger.removeHandler(existing_handler)
    handler = StreamlitHandler(log_container)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    root_logger.addHandler(handler)
    st.session_state["log_handler"] = handler
else:
    if existing_handler:
        root_logger.removeHandler(existing_handler)
        st.session_state.pop("log_handler")

if (
    _demo_cfg
    and st.session_state.get("project")
    and st.session_state.get("project_source") == "demo"
):
    st.session_state["run_requested"] = True

project: Project | None = st.session_state.get("project")

# Sidebar state helper ------------------------------------------------

# Draw a stub button; JS in layout.py will click it.
# We give it a title attr so we can target it from CSS & JS.
hidden_toggle = st.empty()
if hidden_toggle.button(
    "Toggle sidebar <<>>",  # no label
    key="Sidebar",
    help="Sidebar",  # used by JS to find the button
):
    st.session_state.sidebar_state = (
        "collapsed" if st.session_state.sidebar_state == "expanded" else "expanded"
    )
    st.rerun()


# ---- Main canvas -----------------------------------------------------------
col1, col2 = st.columns([3, 1])

if project is None:
    st.info("Upload a GeoJSON file or load the demo project to begin.")
elif st.session_state.get("run_requested"):
    (
        metrics_df,
        ndvi_df,
        msavi_df,
        ndvi_paths,
        msavi_paths,
        metrics_by_id,
    ) = compute_project(project, start_year, end_year)

    # Reattach artefacts when results are served from cache.
    project.attach_rasters(ndvi_paths, msavi_paths)
    project.attach_metrics(metrics_by_id)

    # Clear the flag so slider tweaks alone don’t recompute
    st.session_state["run_requested"] = False

    # Cache results in session_state so they persist on subsequent reruns
    gdf = gpd.GeoDataFrame(
        [{**a.static_props, "geometry": a.geometry} for a in project.aois],
        crs="EPSG:4326",
    )
    metrics = aggregate_metrics(metrics_df)
    st.session_state["results"] = {
        "gdf": gdf,
        "metrics_df": metrics_df,
        "ndvi_df": ndvi_df,
        "msavi_df": msavi_df,
        "metrics": metrics,
    }

    with col1:
        map_container = st.container(height=450)
        with map_container:
            display_map(gdf, project.rasters, project.metrics, info_fields=_map_fields)
    with col2:
        bscore_gauge(metrics.bscore)

    st.markdown("---")
    display_metrics(metrics)
    tab_obs, tab_trend, tab_season, tab_msavi = st.tabs(
        ["NDVI Observed", "NDVI Trend", "NDVI Seasonal", "MSAVI YE"]
    )
    with tab_obs:
        ndvi_component_chart(
            ndvi_df, "observed", start_year=start_year, end_year=end_year
        )
    with tab_trend:
        ndvi_component_chart(ndvi_df, "trend", start_year=start_year, end_year=end_year)
    with tab_season:
        ndvi_component_chart(
            ndvi_df, "seasonal", start_year=start_year, end_year=end_year
        )
    with tab_msavi:
        msavi_bar_chart_all(msavi_df, start_year=start_year, end_year=end_year)
    report_controls(metrics_df, project, start_year, end_year)
    st.dataframe(metrics_df)
elif "results" in st.session_state:
    res = st.session_state["results"]
    gdf = res["gdf"]
    metrics_df = res["metrics_df"]
    ndvi_df = res["ndvi_df"]
    msavi_df = res["msavi_df"]
    metrics = res["metrics"]

    with col1:
        map_container = st.container(height=450)
        with map_container:
            display_map(gdf, project.rasters, project.metrics, info_fields=_map_fields)
    with col2:
        bscore_gauge(metrics.bscore)

    st.markdown("---")
    display_metrics(metrics)
    tab_obs, tab_trend, tab_season, tab_msavi = st.tabs(
        ["NDVI Observed", "NDVI Trend", "NDVI Seasonal", "MSAVI YE"]
    )
    with tab_obs:
        ndvi_component_chart(
            ndvi_df, "observed", start_year=start_year, end_year=end_year
        )
    with tab_trend:
        ndvi_component_chart(ndvi_df, "trend", start_year=start_year, end_year=end_year)
    with tab_season:
        ndvi_component_chart(
            ndvi_df, "seasonal", start_year=start_year, end_year=end_year
        )
    with tab_msavi:
        msavi_bar_chart_all(msavi_df, start_year=start_year, end_year=end_year)
    report_controls(metrics_df, project, start_year, end_year)
    st.dataframe(metrics_df)
else:
    st.info("Adjust parameters, then press **Run analysis**.")

# ---- Footer ---------------------------------------------------------------
st.markdown(
    "<small>Data sources: Copernicus Sentinel-2, ESA, WDPA, Globio, and others</small>",
    unsafe_allow_html=True,
)
