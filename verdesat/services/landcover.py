from __future__ import annotations

"""Service for retrieving 10 m land-cover rasters."""

from typing import Dict
import logging

import os
import ee
import requests

try:
    import rasterio
    from rasterio.enums import Resampling
except ImportError:  # pragma: no cover - optional
    rasterio = None
    Resampling = None

from verdesat.geo.aoi import AOI
from verdesat.ingestion.eemanager import EarthEngineManager, ee_manager
from .base import BaseService


class LandcoverService(BaseService):
    """Retrieve annual land-cover rasters from Earth Engine."""

    ESRI_COLLECTION = "projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m_TS"
    WORLD_COVER = "ESA/WorldCover/v200/2021"
    LATEST_ESRI_YEAR = 2023

    # Mapping of raw dataset classes to 6 consolidated classes
    CLASS_MAP_6: Dict[int, int] = {
        1: 6,  # Water
        2: 1,  # Trees -> Forest
        3: 2,  # Grass -> Shrub
        4: 1,  # Flooded vegetation -> Forest
        5: 3,  # Crops
        6: 2,  # Shrub/Scrub -> Shrub
        7: 4,  # Built area -> Urban
        8: 5,  # Bare ground -> Bare
        9: 5,  # Snow/Ice -> Bare
        10: 5,  # Clouds -> Bare
    }

    def __init__(
        self,
        ee_manager_instance: EarthEngineManager = ee_manager,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(logger)
        self.ee_manager = ee_manager_instance

    def _dataset_for_year(self, year: int) -> str:
        """Return dataset identifier appropriate for *year*."""

        if 2017 <= year <= self.LATEST_ESRI_YEAR:
            return f"{self.ESRI_COLLECTION}/{year}"
        if year > self.LATEST_ESRI_YEAR:
            self.logger.warning(
                "ESRI landcover for %s unavailable; falling back to WorldCover", year
            )
        return self.WORLD_COVER

    def get_image(self, aoi: AOI, year: int) -> ee.Image:
        """Return the remapped land-cover image clipped to *aoi*."""

        image_id = self._dataset_for_year(year)
        self.logger.info("Loading landcover image %s", image_id)
        self.ee_manager.initialize()
        img = ee.Image(image_id)
        remapped = img.remap(
            list(self.CLASS_MAP_6.keys()),
            list(self.CLASS_MAP_6.values()),
        ).rename("landcover")
        return remapped.clip(aoi.ee_geometry())

    def _convert_to_cog(self, path: str) -> None:
        """Convert GeoTIFF at ``path`` to a Cloud Optimized GeoTIFF."""

        if rasterio is None or Resampling is None:
            self.logger.warning(
                "rasterio not installed; skipping COG conversion for %s", path
            )
            return

        try:
            with rasterio.open(path) as src:
                profile = src.profile
                data = src.read()

            profile.update(
                driver="GTiff",
                compress="deflate",
                tiled=True,
                blockxsize=512,
                blockysize=512,
            )

            with rasterio.open(path, "w", **profile) as dst:
                dst.write(data)
                dst.build_overviews([2, 4, 8, 16], Resampling.nearest)
                dst.update_tags(OVR_RESAMPLING="NEAREST")

            self.logger.info("✔ Converted to COG: %s", path)
        except rasterio.errors.RasterioError as cog_err:  # pragma: no cover - opt
            self.logger.warning("⚠ COG conversion failed for %s: %s", path, cog_err)

    def download(self, aoi: AOI, year: int, out_dir: str, scale: int = 10) -> str:
        """Download the land-cover raster and return the output path."""

        img = self.get_image(aoi, year)
        geom = aoi.ee_geometry()
        url = img.getDownloadURL({"scale": scale, "region": geom, "format": "GEOTIFF"})

        pid = aoi.static_props.get("id") or aoi.static_props.get(
            "system:index", "unknown"
        )
        filename = f"LANDCOVER_{pid}_{year}.tiff"
        os.makedirs(out_dir, exist_ok=True)
        output = os.path.join(out_dir, filename)

        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        with open(output, "wb") as f:
            f.write(resp.content)

        self._convert_to_cog(output)
        self.logger.info("Wrote landcover raster to %s", output)
        return output
