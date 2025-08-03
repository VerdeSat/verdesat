from __future__ import annotations

"""Wrapper around :mod:`visualization.chips` for webapp usage."""

from typing import Dict
import logging

from verdesat.geo.aoi import AOI
from verdesat.core.storage import StorageAdapter


class EEChipServiceAdapter:
    """Download NDVI and MSAVI annual composites for a single AOI."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(__name__)

    def download_chips(
        self, aoi: AOI, year: int, storage: StorageAdapter
    ) -> Dict[str, str]:
        """Return local paths of NDVI and MSAVI composites for ``aoi``."""

        from verdesat.visualization._chips_config import ChipsConfig
        from verdesat.visualization.chips import ChipService
        from verdesat.ingestion.sensorspec import SensorSpec
        from verdesat.ingestion.eemanager import EarthEngineManager

        ee_manager = EarthEngineManager()
        ee_manager.initialize()
        sensor = SensorSpec.from_collection_id("COPERNICUS/S2_SR_HARMONIZED")
        service = ChipService(
            ee_manager=ee_manager,
            sensor_spec=sensor,
            storage=storage,
            logger=self.logger,
        )

        start = f"{year}-01-01"
        end = f"{year}-12-31"
        out_dir = "chips"
        result: Dict[str, str] = {}
        for chip_type in ("ndvi", "msavi"):
            cfg = ChipsConfig(
                collection_id="COPERNICUS/S2_SR_HARMONIZED",
                start=start,
                end=end,
                period="YE",
                chip_type=chip_type,
                scale=10,
                buffer=0,
                buffer_percent=None,
                min_val=0,
                max_val=1,
                gamma=None,
                percentile_low=None,
                percentile_high=None,
                palette=("white", "green"),
                fmt="tif",
                out_dir=out_dir,
                mask_clouds=True,
            )
            service.run([aoi], cfg)
            aoi_id = str(aoi.static_props.get("id"))
            filename = f"{chip_type.upper()}_{aoi_id}_{end}.tif"
            result[chip_type] = storage.join(out_dir, filename)
        return result
