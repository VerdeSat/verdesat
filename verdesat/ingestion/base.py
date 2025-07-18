from __future__ import annotations

"""Abstract base class for data ingestion backends."""

from abc import ABC, abstractmethod
from typing import Literal, Optional, List

import pandas as pd

from verdesat.core.logger import Logger
from verdesat.geo.aoi import AOI
from ..visualization._chips_config import ChipsConfig
from .sensorspec import SensorSpec
from verdesat.core.storage import StorageAdapter


class BaseDataIngestor(ABC):
    """Base interface for data ingestion implementations."""

    def __init__(self, sensor: SensorSpec, logger=None):
        self.sensor = sensor
        self.logger = logger or Logger.get_logger(__name__)

    @abstractmethod
    def download_timeseries(
        self,
        aoi: AOI,
        start_date: str,
        end_date: str,
        scale: int,
        index: str,
        value_col: str | None = None,
        chunk_freq: Literal["D", "ME", "YE"] = "YE",
        freq: Optional[Literal["D", "ME", "YE"]] = None,
    ) -> pd.DataFrame:
        """Download and optionally aggregate an index time series for an AOI."""

    @abstractmethod
    def download_chips(
        self,
        aois: List[AOI],
        config: ChipsConfig,
        storage: StorageAdapter | None = None,
    ) -> None:
        """Export image chips for the given AOIs using configuration."""
        raise NotImplementedError
