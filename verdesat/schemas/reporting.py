from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

# Data transfer objects for reporting services. Fields follow the canonical
# snake_case schema described in ``docs/report_unification.md``. ``LABELS``
# maps these field names to human-readable captions for templates.


@dataclass
class ProjectContext:
    """Minimal project metadata used in reports."""

    project_id: str
    project_name: str
    owner: str | None = None
    created_at_utc: str | None = None
    # Static context (extendable)
    countries_iso3: List[str] | None = None
    primary_country_iso3: str | None = None
    climate_zones: List[str] | None = None
    ecoregions: List[str] | None = None


@dataclass
class AoiContext:
    """Static Area of Interest metadata."""

    aoi_id: str
    aoi_name: str | None = None
    project_id: str | None = None
    geometry_path: str | None = None
    centroid_lon: float | None = None
    centroid_lat: float | None = None
    area_ha: float | None = None
    country_iso3: str | None = None
    admin1: str | None = None
    admin2: str | None = None
    biome: str | None = None
    ecoregion: str | None = None
    climate_zone: str | None = None
    tags: Dict[str, str] | None = None


@dataclass
class MetricsRow:
    """Snapshot metrics for a single AOI."""

    # Vegetation
    ndvi_mean: float | None = None
    ndvi_slope: float | None = None  # per year
    ndvi_delta: float | None = None  # last_year - prev_year
    ndvi_p_value: float | None = None
    msavi_mean: float | None = None
    # Biodiversity proxies
    intactness_pct: float | None = None
    frag_norm: float | None = None
    shannon: float | None = None
    msa: float | None = None
    # Composite
    bscore: float | None = None  # 0..100
    bscore_band: str | None = None  # "low|moderate|high"
    # Validity
    obs_count: int | None = None
    valid_obs_pct: float | None = None
    # Sensitivity context
    inside_pa: bool | None = None
    nearest_pa_name: str | None = None
    nearest_pa_distance_km: float | None = None
    nearest_kba_name: str | None = None
    nearest_kba_distance_km: float | None = None
    # Time window used
    window_start: str | None = None
    window_end: str | None = None


LABELS: Dict[str, str] = {
    "ndvi_mean": "NDVI μ",
    "ndvi_slope": "NDVI slope/yr",
    "ndvi_delta": "ΔNDVI (YoY)",
    "ndvi_p_value": "NDVI p-value",
    "msavi_mean": "MSAVI μ",
    "intactness_pct": "Intactness %",
    "frag_norm": "Frag‑Norm",
    "shannon": "Shannon H′",
    "msa": "MSA",
    "bscore": "B‑Score",
    "bscore_band": "B‑Score band",
    "obs_count": "# obs",
    "valid_obs_pct": "% valid obs",
}

__all__ = [
    "ProjectContext",
    "AoiContext",
    "MetricsRow",
    "LABELS",
]
