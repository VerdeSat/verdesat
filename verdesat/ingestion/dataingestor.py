from ..analytics.timeseries import TimeSeries
import logging
from .indices import compute_index
import pandas as pd
from typing import Literal, List
from shapely.geometry import mapping
from shapely.geometry import mapping  # (Retain, but will comment out if not used below)
from .eemanager import ee_manager
from .sensorspec import SensorSpec
from verdesat.geo.aoi import AOI
import ee


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
        freq: Literal["D", "M", "Y"] = "M",
    ) -> pd.DataFrame:
        """
        Download & aggregate the index time series for the AOI.
        Returns a DataFrame with columns ['id','date',f'mean_{index}'].
        """
        # 1. Fetch raw daily values in chunks
        raw_df = self._chunked_timeseries(aoi, start_date, end_date, scale, index)
        # 2. Aggregate by frequency if needed
        if freq:
            ts = TimeSeries.from_dataframe(raw_df, index=index)
            aggregated = ts.aggregate(freq)
            return aggregated.df
        return raw_df

    def _chunked_timeseries(
        self, aoi: AOI, start_date: str, end_date: str, scale: int, index: str
    ) -> pd.DataFrame:
        """
        Break date range into chunks and fetch daily time series for each,
        then concatenate results to avoid GEE limits.
        """
        # 1. Build chunk boundaries
        dates = pd.date_range(start=start_date, end=end_date, freq="M")
        bounds = zip(
            [start_date] + list(dates.strftime("%Y-%m-%d")),
            list(dates.strftime("%Y-%m-%d")) + [end_date],
        )
        dfs = []
        for s, e in bounds:
            try:
                df_chunk = self._daily_timeseries(aoi, s, e, scale, index)
                dfs.append(df_chunk)
            except Exception as err:
                logging.warning(f"Chunk {s}–{e} failed: {err}")
        if not dfs:
            raise RuntimeError("All chunks failed for time series retrieval")
        return pd.concat(dfs, ignore_index=True)

    def _daily_timeseries(
        self, aoi: AOI, start_date: str, end_date: str, scale: int, index: str
    ) -> pd.DataFrame:
        """
        Fetch the index values for each date in the range [start_date, end_date].
        Returns a DataFrame with columns ['id', 'date', f'mean_{index}'].
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
            idx_img = compute_index(img, index)
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
