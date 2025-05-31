"""
DataIngestor: download and aggregate spectral index time series and image chips from Earth Engine.
Provides chunking, daily retrieval, and aggregation functionality.
"""

import logging
from datetime import timedelta
from typing import Literal, Optional

import ee
import pandas as pd

from verdesat.geo.aoi import AOI

from ..analytics.timeseries import TimeSeries
from .eemanager import ee_manager
from .sensorspec import SensorSpec

logger = logging.getLogger(__name__)


class DataIngestor:
    """
    Handles data ingestion for spectral index time series and image chips.
    """

    def __init__(self, sensor: SensorSpec, ee_manager_instance=None):
        """
        sensor: SensorSpec defining bands, collection, cloud mask method.
        ee_manager_instance: EarthEngineManager for EE interactions.
        """
        self.sensor = sensor
        self.ee = ee_manager_instance or ee_manager

    def download_timeseries(
        self,
        aoi: AOI,
        start_date: str,
        end_date: str,
        scale: int,
        index: str,
        chunk_freq: Literal["D", "M", "Y"] = "Y",
        freq: Optional[Literal["D", "M", "Y"]] = None,
    ) -> pd.DataFrame:
        """
        Download & optionally aggregate the index time series for an AOI.

        Args:
            aoi: AOI instance to process.
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).
            scale: Spatial resolution in meters.
            index: Spectral index name (e.g., 'ndvi').
            chunk_freq: Frequency for chunking requests to Earth Engine ('D','M','Y').
            freq: Aggregation frequency for output ('D','M','Y'). If None, no aggregation.

        Returns:
            pd.DataFrame with columns ['id','date',f'mean_{index}'].
        """
        # 1. Fetch raw daily values in chunks
        raw_df = self._chunked_timeseries(
            aoi, start_date, end_date, scale, index, chunk_freq
        )
        # 2. Aggregate by frequency if needed
        if freq:
            ts = TimeSeries.from_dataframe(raw_df, index=index)
            aggregated = ts.aggregate(freq)
            return aggregated.df
        return raw_df

    def _chunked_timeseries(
        self,
        aoi: AOI,
        start_date: str,
        end_date: str,
        scale: int,
        index: str,
        chunk_freq: str,
    ) -> pd.DataFrame:
        """
        Break date range into smaller chunks and fetch daily time series to avoid GEE limits.

        Args:
            aoi: AOI instance.
            start_date: Chunk start date (YYYY-MM-DD).
            end_date: Chunk end date (YYYY-MM-DD).
            scale: Spatial resolution in meters.
            index: Spectral index name.
            chunk_freq: Frequency string for chunk boundaries ('D','M','Y').

        Returns:
            Concatenated pd.DataFrame of daily time series.
        """
        # 1. Build chunk boundaries using period end dates
        dates = pd.date_range(start=start_date, end=end_date, freq=chunk_freq)
        boundaries = list(dates)

        # Initialize
        bounds = []
        prev_start = pd.to_datetime(start_date)

        for b in boundaries:
            end_chunk = b
            # Convert to strings for EE calls
            bounds.append((prev_start.strftime("%Y-%m-%d"), end_chunk.strftime("%Y-%m-%d")))
            # Next chunk starts the day after this boundary
            prev_start = b + timedelta(days=1)

        # If last boundary day is before end_date, add final chunk
        if prev_start <= pd.to_datetime(end_date):
            bounds.append((prev_start.strftime("%Y-%m-%d"), end_date))

        dfs = []
        for s, e in bounds:
            # pylint: disable=broad-exception-caught
            try:
                df_chunk = self._daily_timeseries(aoi, s, e, scale, index)
                dfs.append(df_chunk)
            except Exception as err:
                logger.warning("Chunk %s–%s failed: %s", s, e, err)
        if not dfs:
            raise RuntimeError("All chunks failed for time series retrieval")
        return pd.concat(dfs, ignore_index=True)

    def _daily_timeseries(
        self, aoi: AOI, start_date: str, end_date: str, scale: int, index: str
    ) -> pd.DataFrame:
        """
        Fetch the index values for each date in the given date range.

        Args:
            aoi: AOI instance.
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).
            scale: Spatial resolution in meters.
            index: Spectral index name.

        Returns:
            pd.DataFrame with ['id','date',f'mean_{index}'].
        """
        # Ensure Earth Engine is initialized
        self.ee.initialize()

        # Convert AOI geometry to an EE FeatureCollection with an 'id' property
        geom_geojson = aoi.geometry.__geo_interface__
        ee_geom = ee.Geometry(geom_geojson)
        # Attach the AOI id as a property for reduction
        feature = ee.Feature(ee_geom, {"id": aoi.static_props.get("id")})
        region = ee.FeatureCollection([feature])

        # Fetch and mask images
        coll = self.ee.get_image_collection(
            self.sensor.collection_id,
            start_date,
            end_date,
            region,
            mask_clouds=True,
        )

        # Helper to reduce one image
        def _reduce(img):
            idx_img = self.sensor.compute_index(img, index)
            stats = idx_img.reduceRegions(region, ee.Reducer.mean(), scale=scale)
            date = ee.Date(img.get("system:time_start")).format("YYYY-MM-dd")
            return stats.map(lambda f: f.set("date", date))

        # Execute and parse results
        features = coll.map(_reduce).flatten().getInfo().get("features", [])
        rows = [
            {
                "id": feat["properties"].get("id"),
                "date": feat["properties"].get("date"),
                f"mean_{index}": feat["properties"].get("mean"),
            }
            for feat in features
        ]
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        return df
