"""Streamlit bridge for unified report generation."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from typing import Any, cast
import json
import tempfile

import pandas as pd
from shapely.geometry import mapping

from verdesat.analytics.timeseries import decomp_to_long
from verdesat.core.config import ConfigManager
from verdesat.core.logger import Logger
from verdesat.core.storage import LocalFS, StorageAdapter
from verdesat.project.project import Project
from verdesat.schemas.ai_report import AiReportRequest
from verdesat.schemas.reporting import AoiContext, MetricsRow, ProjectContext
from verdesat.services.ai_report import AiReportService, LlmClient
from verdesat.services.reporting import (
    PackResult,
    build_aoi_evidence_pack,
    build_project_pack as build_project_pack_service,
)
from verdesat.adapters.llm_openai import OpenAiLlmClient


def build_evidence_pack(
    metrics_df: pd.DataFrame,
    ndvi_df: pd.DataFrame,
    msavi_df: pd.DataFrame,
    project: Project,
    aoi_id: str,
    *,
    storage: StorageAdapter | None = None,
    include_ai: bool = False,
    ai_service: Any | None = None,
    ai_request: Any | None = None,
) -> PackResult:
    """Generate an evidence pack for ``aoi_id`` using current app state."""

    storage = storage or project.storage or LocalFS()
    id_col = project.config.get("id_col", "id")

    aoi = next(
        (a for a in project.aois if str(a.static_props.get(id_col)) == str(aoi_id)),
        None,
    )
    if aoi is None:
        raise ValueError(f"AOI {aoi_id} not found in project")

    project_ctx = ProjectContext(
        project_id=project.name,
        project_name=project.name,
    )

    centroid = aoi.geometry.centroid
    area_m2 = aoi.static_props.get("area_m2")
    tmp_geo = tempfile.NamedTemporaryFile(suffix=".geojson", delete=False)
    with open(tmp_geo.name, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": mapping(aoi.geometry),
                        "properties": {**aoi.static_props},
                    }
                ],
            },
            fh,
        )
    aoi_ctx = AoiContext(
        aoi_id=str(aoi_id),
        aoi_name=aoi.static_props.get("name"),
        project_id=project_ctx.project_id,
        geometry_path=tmp_geo.name,
        centroid_lon=float(centroid.x),
        centroid_lat=float(centroid.y),
        area_ha=(float(area_m2) / 10_000.0) if area_m2 is not None else None,
    )

    row = metrics_df[metrics_df[id_col].astype(str) == str(aoi_id)].iloc[0].to_dict()
    field_names = {f.name for f in fields(MetricsRow)}
    data = {k: row.get(k) for k in field_names if k in row}
    metrics_row = MetricsRow(**data)

    ndvi_single = ndvi_df[ndvi_df["id"].astype(str) == str(aoi_id)][
        ["date", "observed", "trend", "seasonal"]
    ].copy()
    ndvi_single["resid"] = float("nan")
    ndvi_long = decomp_to_long(
        ndvi_single,
        aoi_id=str(aoi_id),
        var="ndvi",
        freq="monthly",
        source="S2",
    )

    msavi_single = msavi_df[msavi_df["id"].astype(str) == str(aoi_id)][
        ["date", "mean_msavi"]
    ].rename(columns={"mean_msavi": "value"})
    msavi_long = msavi_single.assign(
        var="msavi",
        stat="raw",
        aoi_id=str(aoi_id),
        freq="monthly",
        source="S2",
    )[["date", "var", "stat", "value", "aoi_id", "freq", "source"]]

    ts_long = pd.concat([ndvi_long, msavi_long], ignore_index=True)

    lineage: dict[str, Any] = {
        "method_version": "0.2.0",
        "sources": [
            {
                "name": "Sentinel-2 L2A",
                "version": "v2024",
                "resolution": "10 m",
                "date_range": "2017–present",
                "notes": "NDVI/MSAVI composites",
            }
        ],
    }
    tmp_metrics_path: str | None = None
    tmp_ts_path: str | None = None
    tmp_lineage_path: str | None = None
    if include_ai and (ai_service is None or ai_request is None):
        config = ConfigManager()
        logger = Logger.get_logger(__name__)
        llm = OpenAiLlmClient(seed=int(config.get("ai_report_seed", 42)), logger=logger)
        ai_service = AiReportService(
            llm=cast(LlmClient, llm),
            storage=storage,
            logger=logger,
            config=config,
        )

        metrics_ai = metrics_df[metrics_df[id_col].astype(str) == str(aoi_id)].copy()
        metrics_ai["aoi_id"] = aoi_ctx.aoi_id
        metrics_ai["project_id"] = project_ctx.project_id
        metrics_ai["method_version"] = lineage["method_version"]
        window_start = pd.to_datetime(ts_long["date"].min()).date().isoformat()
        window_end = pd.to_datetime(ts_long["date"].max()).date().isoformat()
        metrics_ai["window_start"] = window_start
        metrics_ai["window_end"] = window_end
        tmp_metrics = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        metrics_ai.to_csv(tmp_metrics.name, index=False)
        tmp_metrics_path = tmp_metrics.name

        ndvi_ai = ndvi_long[ndvi_long["stat"] == "raw"][
            ["date", "value", "aoi_id"]
        ].assign(metric="ndvi_mean")
        ndvi_ai["date"] = pd.to_datetime(ndvi_ai["date"]).dt.date
        msavi_ai = msavi_long[["date", "value", "aoi_id"]].assign(metric="msavi_mean")
        msavi_ai["date"] = pd.to_datetime(msavi_ai["date"]).dt.date
        ts_ai = pd.concat([ndvi_ai, msavi_ai], ignore_index=True)[
            ["date", "metric", "value", "aoi_id"]
        ]
        tmp_ts = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        ts_ai.to_csv(tmp_ts.name, index=False)
        tmp_ts_path = tmp_ts.name

        tmp_lineage = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp_lineage.write(json.dumps(lineage).encode("utf-8"))
        tmp_lineage.flush()
        tmp_lineage_path = tmp_lineage.name

        ai_request = AiReportRequest(
            aoi_id=str(aoi_id),
            project_id=project_ctx.project_id,
            metrics_path=tmp_metrics_path,
            timeseries_path=tmp_ts_path,
            lineage_path=tmp_lineage_path,
        )

    result = build_aoi_evidence_pack(
        aoi=aoi_ctx,
        project=project_ctx,
        metrics=metrics_row,
        ts_long=ts_long,
        lineage=lineage,
        storage=storage,
        include_ai=include_ai,
        ai_service=ai_service,
        ai_request=ai_request,
    )
    Path(tmp_geo.name).unlink(missing_ok=True)
    for path in (tmp_metrics_path, tmp_ts_path, tmp_lineage_path):
        if path:
            Path(path).unlink(missing_ok=True)
    return result


def build_project_pack(
    metrics_df: pd.DataFrame,
    ndvi_df: pd.DataFrame,
    msavi_df: pd.DataFrame,
    project: Project,
    *,
    start_year: int | None = None,
    end_year: int | None = None,
    storage: StorageAdapter | None = None,
    lineage: dict[str, Any] | None = None,
) -> PackResult:
    """Generate a project-wide report pack using current app state."""

    storage = storage or project.storage or LocalFS()
    project_ctx = ProjectContext(
        project_id=project.name,
        project_name=project.name,
    )

    id_col = project.config.get("id_col", "id")

    if start_year is not None and end_year is not None:
        ndvi_mask = (ndvi_df["date"].dt.year >= start_year) & (
            ndvi_df["date"].dt.year <= end_year
        )
        ndvi_df = ndvi_df.loc[ndvi_mask]
        msavi_mask = (msavi_df["date"].dt.year >= start_year) & (
            msavi_df["date"].dt.year <= end_year
        )
        msavi_df = msavi_df.loc[msavi_mask]
    ndvi_frames: list[pd.DataFrame] = []
    for aoi_id in metrics_df[id_col].astype(str).unique():
        ndvi_single = ndvi_df[ndvi_df[id_col].astype(str) == str(aoi_id)][
            ["date", "observed", "trend", "seasonal"]
        ].copy()
        if ndvi_single.empty:
            continue
        ndvi_single["resid"] = float("nan")
        ndvi_frames.append(
            decomp_to_long(
                ndvi_single,
                aoi_id=str(aoi_id),
                var="ndvi",
                freq="monthly",
                source="S2",
            )
        )

    msavi_frames: list[pd.DataFrame] = []
    for aoi_id in metrics_df[id_col].astype(str).unique():
        msavi_single = msavi_df[msavi_df[id_col].astype(str) == str(aoi_id)][
            ["date", "mean_msavi"]
        ].copy()
        if msavi_single.empty:
            continue
        msavi_frames.append(
            msavi_single.assign(
                var="msavi",
                stat="raw",
                value=msavi_single["mean_msavi"],
                aoi_id=str(aoi_id),
                freq="monthly",
                source="S2",
            )[["date", "var", "stat", "value", "aoi_id", "freq", "source"]]
        )

    ts_parts = ndvi_frames + msavi_frames
    ts_long = pd.concat(ts_parts, ignore_index=True) if ts_parts else None

    lineage = lineage or {
        "method_version": "0.2.0",
        "sources": [
            {
                "name": "Sentinel-2 L2A",
                "version": "v2024",
                "resolution": "10 m",
                "date_range": "2017–present",
                "notes": "NDVI/MSAVI composites",
            }
        ],
    }

    return build_project_pack_service(
        project=project_ctx,
        metrics_df=metrics_df,
        ts_long=ts_long,
        lineage=lineage,
        storage=storage,
    )
