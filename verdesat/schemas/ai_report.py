from __future__ import annotations

"""Data models for AI report generation.

The original design proposed using Pydantic models. To stay aligned with the
rest of the codebase, these schemas use :mod:`dataclasses` instead.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict


@dataclass
class MetricsSummary:
    """Aggregated AOI metrics passed to the language model."""

    aoi_id: str
    project_id: str
    method_version: str
    window_start: date
    window_end: date
    intactness_pct: float | None = None
    frag_norm: float | None = None
    shannon: float | None = None
    bscore: float | None = None
    ndvi_mean: float | None = None
    ndvi_slope_per_year: float | None = None
    ndvi_delta_yoy: float | None = None
    valid_obs_pct: float | None = None
    pixel_count_total: int | None = None
    pixel_count_valid: int | None = None
    msa_mean_2015: float | None = None
    landcover_mode: int | None = None
    landcover_entropy: float | None = None
    wdpa_inside: bool | None = None
    nearest_pa_name: str | None = None
    nearest_pa_distance_km: float | None = None
    nearest_kba_name: str | None = None
    nearest_kba_distance_km: float | None = None
    area_ha: float | None = None
    centroid_lat: float | None = None
    centroid_lon: float | None = None
    ecoregion: str | None = None
    elevation_mean_m: float | None = None
    slope_mean_deg: float | None = None


@dataclass
class TimeseriesRow:
    """Single observation from the VI time series."""

    date: date
    metric: str
    value: float
    aoi_id: str


@dataclass
class AiReportRequest:
    """Parameters for :class:`AiReportService.generate_summary`."""

    aoi_id: str
    project_id: str
    metrics_path: str
    timeseries_path: str
    lineage_path: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    force: bool = False


@dataclass
class AiReportResult:
    """Result returned by the AI report service."""

    aoi_id: str
    project_id: str
    model: str
    prompt_version: str
    summary: Dict[str, Any]
    narrative: str
    uri: str | None = None


__all__ = [
    "MetricsSummary",
    "TimeseriesRow",
    "AiReportRequest",
    "AiReportResult",
]
