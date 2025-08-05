from __future__ import annotations

__doc__ = "Streamlit dashboard for visualising VerdeSat project metrics."

import json
import logging
from dataclasses import fields
from datetime import date
from pathlib import Path
from typing import Any, cast

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
from verdesat.webapp.components.kpi_cards import Metrics, bscore_gauge, display_metrics
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

logger = Logger.get_logger(__name__)

CONFIG = ConfigManager(
    str(Path(__file__).resolve().parents[1] / "resources" / "webapp.toml")
)
_demo_cfg = CONFIG.get("demo", {})
_defaults = CONFIG.get("defaults", {})
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
        "Demo Project", "VerdeSat", geojson, CONFIG, storage=storage
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

    metrics_df, ndvi_df, msavi_df = project_compute.compute(
        project, date(start_year, 1, 1), date(end_year, 12, 31)
    )
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
st.set_page_config(page_title="VerdeSat B-Score", page_icon="🌳", layout="wide")
apply_theme()
render_navbar()
render_hero("VerdeSat Biodiversity Dashboard")

# ---- Sidebar ---------------------------------------------------------------
st.sidebar.header("VerdeSat B-Score v0.1")

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

# --- Compute trigger --------------------------------------------------
if "run_requested" not in st.session_state:
    st.session_state["run_requested"] = False
if st.sidebar.button("Run analysis"):
    st.session_state["run_requested"] = True


# --- Years Slider --------------------------------------------------
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
if st.sidebar.button("Load demo project"):
    st.session_state["project"] = load_demo_project()
    st.session_state["run_requested"] = False
    # Drop any cached map from a previous project
    st.session_state.pop("main_map", None)
    st.session_state.pop("map_obj", None)
    st.session_state.pop("map_layers_key", None)

if uploaded_file is not None:
    # Create / refresh the project only when the user selects
    # *a different* file. On normal reruns `uploaded_file` is the
    # same  object and we must *not* wipe the run_requested flag.
    if st.session_state.get("uploaded_filename") != uploaded_file.name:
        geojson = json.load(uploaded_file)
        st.session_state["project"] = Project.from_geojson(
            "Uploaded Project", "Guest", geojson, CONFIG, storage=storage
        )
        st.session_state["uploaded_filename"] = uploaded_file.name
        st.session_state["run_requested"] = False
        st.session_state.pop("main_map", None)
        st.session_state.pop("map_obj", None)
        st.session_state.pop("map_layers_key", None)

if _demo_cfg and st.session_state.get("project") and not uploaded_file:
    st.session_state["run_requested"] = True

project: Project | None = st.session_state.get("project")

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
    first_row = metrics_df.iloc[0].to_dict()
    metric_fields = {f.name for f in fields(Metrics)}
    metric_data = {k: first_row[k] for k in metric_fields if k in first_row}
    metrics = Metrics(**cast(dict[str, Any], metric_data))
    st.session_state["results"] = {
        "gdf": gdf,
        "metrics_df": metrics_df,
        "ndvi_df": ndvi_df,
        "msavi_df": msavi_df,
        "metrics": metrics,
    }

    with col1:
        display_map(gdf, project.rasters)
    with col2:
        bscore_gauge(metrics.bscore)

    st.markdown("---")
    display_metrics(metrics)
    st.dataframe(metrics_df)
    report_controls(metrics_df, project, start_year, end_year)

    st.markdown("---")
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
elif "results" in st.session_state:
    res = st.session_state["results"]
    gdf = res["gdf"]
    metrics_df = res["metrics_df"]
    ndvi_df = res["ndvi_df"]
    msavi_df = res["msavi_df"]
    metrics = res["metrics"]

    with col1:
        display_map(gdf, project.rasters)
    with col2:
        bscore_gauge(metrics.bscore)

    st.markdown("---")
    display_metrics(metrics)
    st.dataframe(metrics_df)
    report_controls(metrics_df, project, start_year, end_year)

    st.markdown("---")
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
else:
    st.info("Adjust parameters, then press **Run analysis**.")
