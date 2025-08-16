"""Streamlit bridge for unified report generation."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import tempfile

import geopandas as gpd
import pandas as pd

from verdesat.analytics.timeseries import decomp_to_long
from verdesat.core.storage import LocalFS, StorageAdapter
from verdesat.project.project import Project
from verdesat.schemas.reporting import AoiContext, MetricsRow, ProjectContext
from verdesat.services.reporting import PackResult, build_aoi_evidence_pack


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
    gpd.GeoDataFrame(
        [{**aoi.static_props}], geometry=[aoi.geometry], crs="EPSG:4326"
    ).to_file(tmp_geo.name, driver="GeoJSON")
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
    if include_ai:
        if ai_service is None:
            ai_service = SimpleNamespace(
                generate_summary=lambda _req: SimpleNamespace(
                    narrative="AI summary unavailable",
                    summary={"status": "unavailable"},
                )
            )
        if ai_request is None:
            ai_request = {"aoi_id": str(aoi_id)}

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
    return result
