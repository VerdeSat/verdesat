from __future__ import annotations

"""Thin wrapper around ChipService for analytics workflows."""

from typing import List

from verdesat.geo.aoi import AOI
from verdesat.ingestion.eemanager import EarthEngineManager
from verdesat.ingestion.sensorspec import SensorSpec
from verdesat.visualization._chips_config import ChipsConfig
from verdesat.visualization.chips import ChipService
from verdesat.core.storage import StorageAdapter
from verdesat.core.logger import Logger


def export_chips(
    aois: List[AOI],
    config: ChipsConfig,
    ee_manager: EarthEngineManager,
    sensor: SensorSpec,
    storage: StorageAdapter | None = None,
    logger=None,
) -> None:
    """Export chips using ChipService."""
    service = ChipService(
        ee_manager=ee_manager,
        sensor_spec=sensor,
        storage=storage,
        logger=logger or Logger.get_logger(__name__),
    )
    service.run(aois=aois, config=config)
