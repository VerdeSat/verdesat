"""Earth Engine backend for data ingestion."""

from typing import Literal, Optional, List


import ee
import pandas as pd

from verdesat.geo.aoi import AOI

from ..analytics.timeseries import TimeSeries
from .eemanager import ee_manager
from .sensorspec import SensorSpec
from .base import BaseDataIngestor
from .downloader import EarthEngineDownloader
from ..analytics.ee_masking import mask_collection
from ..analytics.ee_chipping import export_chips
from verdesat.core.storage import StorageAdapter
from ..visualization._chips_config import ChipsConfig


class EarthEngineIngestor(BaseDataIngestor):
    """
    Handles data ingestion for spectral index time series and image chips.
    """

    def __init__(
        self,
        sensor: SensorSpec,
        ee_manager_instance=None,
        logger=None,
    ):
        """Create an ingestor using the given sensor and EE manager."""
        super().__init__(sensor, logger=logger)
        self.ee = ee_manager_instance or ee_manager
        self.downloader = EarthEngineDownloader(
            sensor=sensor, ee_manager=self.ee, logger=logger
        )

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
        """
        Download & optionally aggregate the index time series for an AOI.

        Args:
            aoi: AOI instance to process.
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).
            scale: Spatial resolution in meters.
            index: Spectral index name (e.g., 'ndvi').
            chunk_freq: Frequency for chunking requests to Earth Engine ('D','ME','YE').
            freq: Aggregation frequency for output ('D','ME','YE'). If None, no aggregation.

        Returns:
            pd.DataFrame with columns ['id', 'date', value_col].
        """
        raw_df = self.downloader.download_with_chunks(
            start=start_date,
            end=end_date,
            chunk_freq=chunk_freq,
            aoi=aoi,
            scale=scale,
            index=index,
            value_col=value_col,
        )
        # 2. Aggregate by frequency if needed
        if freq:
            ts = TimeSeries.from_dataframe(raw_df, index=index)
            aggregated = ts.aggregate(freq)
            return aggregated.df
        return raw_df

    def download_chips(
        self,
        aois: List[AOI],
        config: ChipsConfig,
        storage: StorageAdapter | None = None,
    ) -> None:
        """Export chips for the supplied AOIs using the given configuration."""
        self.ee.initialize()
        export_chips(
            aois=aois,
            config=config,
            ee_manager=self.ee,
            sensor=self.sensor,
            storage=storage,
            logger=self.logger,
        )
