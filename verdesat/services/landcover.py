from __future__ import annotations

"""Service to fetch land-cover data from Earth Engine."""

from datetime import datetime
import logging
from typing import Dict

import ee
import requests
from ee import EEException

from verdesat.core.logger import Logger
from verdesat.core.storage import LocalFS, StorageAdapter
from verdesat.geo.aoi import AOI
from verdesat.ingestion.eemanager import ee_manager

# Mapping of dataset-specific class codes to five-category scheme
CLASS_MAP_5: Dict[int, int] = {
    2: 1,  # ESRI Trees -> forest
    6: 2,  # ESRI Shrub
    5: 3,  # ESRI Crops
    7: 4,  # ESRI Built area
    8: 5,  # ESRI Bare ground
    10: 1,  # ESA Tree cover
    20: 2,  # ESA Shrubland
    40: 3,  # ESA Cropland
    50: 4,  # ESA Built-up
    60: 5,  # ESA Bare
}


class BaseService:
    """Minimal base class providing a logger."""

    def __init__(self, logger: logging.Logger | None = None) -> None:  # noqa: D401
        self.logger = logger or Logger.get_logger(self.__class__.__name__)


class LandcoverService(BaseService):
    """Retrieve annual 10 m land-cover rasters."""

    ESRI_COLLECTION = "projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m_TS"
    WORLD_COVER_COLLECTION = "ESA/WorldCover/v200"

    def __init__(
        self,
        storage: StorageAdapter | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(logger=logger)
        self.ee = ee_manager
        self.storage = storage or LocalFS()

    @staticmethod
    def _latest_year() -> int:
        return datetime.utcnow().year

    def _esri_image(self, year: int) -> ee.Image:
        coll = ee.ImageCollection(self.ESRI_COLLECTION).filter(
            ee.Filter.eq("year", year)
        )
        return coll.first()

    def _worldcover_image(self) -> ee.Image:
        coll = ee.ImageCollection(self.WORLD_COVER_COLLECTION).filter(
            ee.Filter.eq("year", 2021)
        )
        return coll.first().select("Map")

    def _get_raw_image(self, year: int) -> ee.Image:
        if 2017 <= year <= self._latest_year():
            return self._esri_image(year)
        return self._worldcover_image()

    def download(self, aoi: AOI, year: int, out_dir: str) -> str:
        """Download land-cover raster for *aoi* and *year* into *out_dir*."""
        self.ee.initialize()
        geom = aoi.buffered_ee_geometry(0)
        img = (
            self._get_raw_image(year)
            .remap(
                ee.List(list(CLASS_MAP_5.keys())),
                ee.List(list(CLASS_MAP_5.values())),
            )
            .clip(geom)
        )
        try:
            url = img.getDownloadURL({"scale": 10, "region": geom})
        except EEException as err:  # pragma: no cover - network error
            self.logger.error("Failed to create download URL: %s", err)
            raise

        pid = aoi.static_props.get("id", "aoi")
        filename = f"landcover_{pid}_{year}.tif"
        dest = self.storage.join(out_dir, filename)
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            self.storage.write_bytes(dest, resp.content)
            self.logger.info("\u2714 Wrote landcover: %s", dest)
        except requests.RequestException as err:  # pragma: no cover - network
            self.logger.error("Download failed: %s", err)
            raise
        return dest
