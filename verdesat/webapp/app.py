from __future__ import annotations

"""Streamlit dashboard for visualising VerdeSat project metrics."""

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
from verdesat.webapp.services.chip_service import EEChipServiceAdapter
from verdesat.webapp.services.project_compute import ProjectComputeService
from verdesat.webapp.services.r2 import signed_url

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


@st.cache_data
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


@st.cache_data(hash_funcs={Project: project_compute._hash_project})
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
    reattach them to freshly initialised :class:`Project` instances on cache
    hits where the function body is not executed.
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


# ---- Page config -----------------------------------------------------------
st.set_page_config(page_title="VerdeSat B-Score", page_icon="🌳", layout="wide")

# ---- Sidebar ---------------------------------------------------------------
st.sidebar.header("VerdeSat B-Score v0.1")
start_year, end_year = st.sidebar.slider(
    "Years",
    2017,
    2024,
    value=(
        int(_defaults.get("start_year", 2019)),
        int(_defaults.get("end_year", 2024)),
    ),
)

uploaded_file = st.sidebar.file_uploader("GeoJSON Project", type="geojson")
if st.sidebar.button("Load demo project"):
    st.session_state["project"] = load_demo_project()

if uploaded_file is not None:
    geojson = json.load(uploaded_file)
    st.session_state["project"] = Project.from_geojson(
        "Uploaded Project", "Guest", geojson, CONFIG, storage=storage
    )

project: Project | None = st.session_state.get("project")

# ---- Main canvas -----------------------------------------------------------
st.title("VerdeSat Biodiversity Dashboard")
col1, col2 = st.columns([3, 1])

if project is None:
    st.info("Upload a GeoJSON file or load the demo project to begin.")
else:
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

    gdf = gpd.GeoDataFrame(
        [{**a.static_props, "geometry": a.geometry} for a in project.aois],
        crs="EPSG:4326",
    )
    with col1:
        display_map(gdf, project.rasters)
    with col2:
        first_row = metrics_df.iloc[0].to_dict()
        metric_fields = {f.name for f in fields(Metrics)}
        metric_data = {k: first_row[k] for k in metric_fields if k in first_row}
        metrics = Metrics(**cast(dict[str, Any], metric_data))
        bscore_gauge(metrics.bscore)

    st.markdown("---")
    display_metrics(metrics)
    st.dataframe(metrics_df)

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

# ---- Dev log pane ---------------------------------------------------------
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

    log_handler = StreamlitHandler(log_container)
    logging.getLogger().addHandler(log_handler)

if log_handler is not None:  # pragma: no cover - UI
    logging.getLogger().removeHandler(log_handler)
