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
from shapely.ops import unary_union

from verdesat.geo.aoi import AOI

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
from verdesat.core.logger import Logger

logger = logging.getLogger(__name__)


def _to_geometry(
    aoi_geojson: dict | str | gpd.GeoDataFrame | BaseGeometry | AOI,
) -> BaseGeometry:
    """Return WGS84 geometry from various AOI representations."""

    if isinstance(aoi_geojson, AOI):
        return _to_geometry(aoi_geojson.geometry)
    if isinstance(aoi_geojson, BaseGeometry):
        gdf = gpd.GeoDataFrame({"geometry": [aoi_geojson]}, crs="EPSG:4326")
    elif isinstance(aoi_geojson, gpd.GeoDataFrame):
        gdf = aoi_geojson
    elif isinstance(aoi_geojson, str):
        gdf = gpd.read_file(aoi_geojson)
    elif isinstance(aoi_geojson, dict):
        if "features" in aoi_geojson:
            geoms = [shape(f["geometry"]) for f in aoi_geojson["features"]]
            gdf = gpd.GeoDataFrame({"geometry": geoms}, crs="EPSG:4326")
        elif "geometry" in aoi_geojson:
            gdf = gpd.GeoDataFrame(
                {"geometry": [shape(aoi_geojson["geometry"])]}, crs="EPSG:4326"
            )
        else:
            raise TypeError("Unsupported input type for AOI")
    else:
        raise TypeError("Unsupported input type for AOI")

    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    return unary_union(gdf.geometry)


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

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """Create service with module-aware logger by default."""
        super().__init__(logger or Logger.get_logger(__name__))

    def fetch_occurrences(
        self,
        aoi_geojson: dict | str | gpd.GeoDataFrame | BaseGeometry | AOI,
        start_year: int = 2000,
    ) -> gpd.GeoDataFrame:
        """Return occurrences for *aoi_geojson* since *start_year*.

        Attempts a GBIF polygon search first and falls back to the
        bounding box if GBIF rejects the geometry.
        """

        geom = _to_geometry(aoi_geojson)
        bbox = geom.bounds
        gbif_geom = geom
        use_bbox = False
        if len(geom.wkt) > 5000:
            self.logger.info(
                "AOI geometry too large for GBIF; using bounding box instead"
            )
            from shapely.geometry import box

            gbif_geom = box(*bbox)
            use_bbox = True
        records: list[gpd.GeoDataFrame] = []
        self.logger.info("Fetching occurrences since %s for bbox %s", start_year, bbox)

        gbif_gdf: gpd.GeoDataFrame
        gbif_count = 0
        if gbif_occ is not None:
            year_param = f"{start_year},{datetime.date.today().year}"
            try:
                res = gbif_occ.search(
                    geometry=gbif_geom.wkt, year=year_param, limit=300
                )
            except Exception as exc:  # pragma: no cover - optional broad catch
                if not use_bbox:
                    self.logger.warning(
                        "GBIF search failed: %s; retrying with bounding box", exc
                    )
                    from shapely.geometry import box

                    gbif_geom = box(*bbox)
                    use_bbox = True
                    try:
                        res = gbif_occ.search(
                            geometry=gbif_geom.wkt, year=year_param, limit=300
                        )
                    except Exception as exc2:  # pragma: no cover - optional broad catch
                        self.logger.warning("GBIF retry failed: %s", exc2)
                        res = {"results": []}
                else:
                    self.logger.warning("GBIF search failed: %s", exc)
                    res = {"results": []}
            gbif_gdf = _records_to_gdf(res.get("results", []), "gbif")
            gbif_count = len(gbif_gdf)
            records.append(gbif_gdf)
            self.logger.info("Fetched %d GBIF records", gbif_count)
        else:  # pragma: no cover - optional path
            self.logger.info("pygbif not available; skipping GBIF search")
            gbif_gdf = gpd.GeoDataFrame(
                columns=["geometry", "source"], geometry="geometry", crs="EPSG:4326"
            )
            records.append(gbif_gdf)

        if gbif_count < 250 and get_nearby_observations is not None:
            token = os.getenv("EBIRD_TOKEN")
            if token:
                try:
                    center = geom.centroid
                    self.logger.info(
                        "Querying eBird around (%f, %f)", center.y, center.x
                    )
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
            else:
                self.logger.info("EBIRD_TOKEN not set; skipping eBird fallback")
        elif gbif_count < 250:
            self.logger.info("ebird.api not available; skipping eBird fallback")
        if gbif_count < 250 and inat_get_observations is not None:
            try:
                self.logger.info("Querying iNaturalist within bbox %s", bbox)
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
        elif gbif_count < 250:
            self.logger.info(
                "pyinaturalist not available; skipping iNaturalist fallback"
            )

        if records:
            final = gpd.GeoDataFrame(
                pd.concat(records, ignore_index=True), crs="EPSG:4326"
            )
            counts = final["source"].value_counts().to_dict()
            self.logger.info("Total records: %s", counts)
            return final

        self.logger.info("No occurrence records found")
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
