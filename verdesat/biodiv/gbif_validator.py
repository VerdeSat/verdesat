from __future__ import annotations

"""Utilities for validating biodiversity scores using occurrence data."""

from typing import Iterable
import os
import logging
import datetime
import pandas as pd
import geopandas as gpd
from shapely.geometry import shape, Point
from shapely.geometry.base import BaseGeometry

try:
    from pygbif import occurrences as gbif_occ
except Exception:  # pragma: no cover - optional
    gbif_occ = None

try:
    from ebird.api.requests import get_nearby_observations
except Exception:  # pragma: no cover - optional
    get_nearby_observations = None

try:
    from pyinaturalist import get_observations as inat_get_observations
except Exception:  # pragma: no cover - optional
    inat_get_observations = None


from verdesat.services.base import BaseService

logger = logging.getLogger(__name__)


def _to_geometry(aoi_geojson: dict | str | gpd.GeoDataFrame) -> BaseGeometry:
    """Extract shapely geometry from GeoJSON string/dict or GeoDataFrame."""
    if isinstance(aoi_geojson, gpd.GeoDataFrame):
        return aoi_geojson.unary_union
    if isinstance(aoi_geojson, str):
        gdf = gpd.read_file(aoi_geojson)
        return gdf.unary_union
    if isinstance(aoi_geojson, dict):
        if "features" in aoi_geojson:
            geoms = [shape(f["geometry"]) for f in aoi_geojson["features"]]
            return gpd.GeoSeries(geoms).unary_union
        if "geometry" in aoi_geojson:
            return shape(aoi_geojson["geometry"])
    raise TypeError("Unsupported input type for AOI")


def _records_to_gdf(records: Iterable[dict], source: str) -> gpd.GeoDataFrame:
    rows = []
    for rec in records:
        lon = rec.get("decimalLongitude") or rec.get("lng")
        lat = rec.get("decimalLatitude") or rec.get("lat")
        if lat is None or lon is None:
            coords = rec.get("geojson", {}).get("coordinates")
            if coords:
                lon, lat = coords
        if lat is None or lon is None:
            continue
        rows.append({"geometry": Point(float(lon), float(lat)), "source": source})
    if rows:
        return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    return gpd.GeoDataFrame(
        columns=["geometry", "source"], geometry="geometry", crs="EPSG:4326"
    )


class OccurrenceService(BaseService):
    """Fetch species occurrences from citizen-science portals."""

    def fetch_occurrences(
        self, aoi_geojson: dict | str | gpd.GeoDataFrame, start_year: int = 2000
    ) -> gpd.GeoDataFrame:
        """Return occurrences for *aoi_geojson* since *start_year*."""

        geom = _to_geometry(aoi_geojson)
        bbox = geom.bounds
        records: list[gpd.GeoDataFrame] = []

        gbif_gdf: gpd.GeoDataFrame
        if gbif_occ is not None:
            try:
                year_param = f"{start_year},{datetime.date.today().year}"
                res = gbif_occ.search(geometry=geom.wkt, year=year_param, limit=300)
                gbif_gdf = _records_to_gdf(res.get("results", []), "gbif")
                records.append(gbif_gdf)
                self.logger.info("Fetched %d GBIF records", len(gbif_gdf))
            except Exception as exc:  # pragma: no cover - optional broad catch
                self.logger.warning("GBIF search failed: %s", exc)
                gbif_gdf = gpd.GeoDataFrame(
                    columns=["geometry", "source"], geometry="geometry", crs="EPSG:4326"
                )
                records.append(gbif_gdf)
        else:  # pragma: no cover - optional path
            gbif_gdf = gpd.GeoDataFrame(
                columns=["geometry", "source"], geometry="geometry", crs="EPSG:4326"
            )
            records.append(gbif_gdf)

        if len(gbif_gdf) >= 250:
            return gpd.GeoDataFrame(
                pd.concat(records, ignore_index=True), crs="EPSG:4326"
            )

        if get_nearby_observations is not None:
            token = os.getenv("EBIRD_TOKEN")
            if token:
                try:
                    center = geom.centroid
                    ebird_res = get_nearby_observations(
                        token,
                        center.y,
                        center.x,
                        dist=50,
                        back=30,
                        max_results=10000,
                    )
                    ebird_gdf = _records_to_gdf(ebird_res or [], "ebird")
                    self.logger.info("Fetched %d eBird records", len(ebird_gdf))
                    records.append(ebird_gdf)
                except Exception as exc:  # pragma: no cover - optional broad catch
                    self.logger.warning("eBird request failed: %s", exc)

        if inat_get_observations is not None:
            try:
                inat_res = inat_get_observations(
                    nelat=bbox[3],
                    nelng=bbox[2],
                    swlat=bbox[1],
                    swlng=bbox[0],
                    d1=f"{start_year}-01-01",
                )
                items = inat_res.get("results", inat_res)
                inat_gdf = _records_to_gdf(items, "inat")
                self.logger.info("Fetched %d iNaturalist records", len(inat_gdf))
                records.append(inat_gdf)
            except Exception as exc:  # pragma: no cover - optional broad catch
                self.logger.warning("iNaturalist request failed: %s", exc)

        if records:
            return gpd.GeoDataFrame(
                pd.concat(records, ignore_index=True), crs="EPSG:4326"
            )
        return gpd.GeoDataFrame(
            columns=["geometry", "source"], geometry="geometry", crs="EPSG:4326"
        )

    @staticmethod
    def occurrence_density_km2(gdf: gpd.GeoDataFrame, aoi_area_km2: float) -> float:
        """Return occurrence density (records per square km)."""
        if aoi_area_km2 <= 0:
            return 0.0
        return float(len(gdf) / aoi_area_km2)


def plot_score_vs_density(
    scores: list[float], densities: list[float], out_png: str
) -> None:
    """Plot score versus occurrence density and save to *out_png*."""
    import matplotlib.pyplot as plt  # imported lazily

    fig, ax = plt.subplots()
    ax.scatter(densities, scores, alpha=0.6)
    ax.set_xlabel("Occurrence Density (per km²)")
    ax.set_ylabel("Score")
    ax.set_title("Score vs. Occurrence Density")
    plt.figtext(
        0.5,
        0.01,
        "Citizen-science data are spatially biased; treat correlation as exploratory only.",
        ha="center",
        va="bottom",
        fontsize=8,
    )
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close(fig)
