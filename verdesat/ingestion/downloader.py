from __future__ import annotations

"""Base downloader and Earth Engine implementation."""

from abc import ABC, abstractmethod
from datetime import timedelta
from typing import List, Tuple
import time

import pandas as pd
import ee

from verdesat.core.logger import Logger
from verdesat.geo.aoi import AOI
from .sensorspec import SensorSpec
from .eemanager import ee_manager as default_manager
from ..analytics.ee_masking import mask_collection


class BaseDownloader(ABC):
    """Abstract downloader with chunking and retry logic."""

    def __init__(self, max_retries: int = 3, logger=None) -> None:
        self.max_retries = max_retries
        self.logger = logger or Logger.get_logger(__name__)

    @staticmethod
    def build_chunks(start: str, end: str, freq: str) -> List[Tuple[str, str]]:
        dates = pd.date_range(start=start, end=end, freq=freq)
        boundaries = list(dates)
        bounds: List[Tuple[str, str]] = []
        prev_start = pd.to_datetime(start)
        for b in boundaries:
            bounds.append((prev_start.strftime("%Y-%m-%d"), b.strftime("%Y-%m-%d")))
            prev_start = b + timedelta(days=1)
        if prev_start <= pd.to_datetime(end):
            bounds.append((prev_start.strftime("%Y-%m-%d"), end))
        return bounds

    def download_with_chunks(
        self,
        start: str,
        end: str,
        chunk_freq: str,
        *args,
        **kwargs,
    ):
        bounds = self.build_chunks(start, end, chunk_freq)
        results = []
        for s, e in bounds:
            for attempt in range(1, self.max_retries + 1):
                try:
                    result = self.download_chunk(s, e, *args, **kwargs)
                    results.append(result)
                    break
                except Exception as err:  # pragma: no cover - general safety
                    if attempt == self.max_retries:
                        self.logger.warning(
                            "Chunk %s-%s failed after %d attempts: %s",
                            s,
                            e,
                            attempt,
                            err,
                        )
                    else:
                        backoff = 2 ** (attempt - 1)
                        self.logger.warning(
                            "Chunk %s-%s failed (attempt %d/%d): %s; retrying in %d s",
                            s,
                            e,
                            attempt,
                            self.max_retries,
                            err,
                            backoff,
                        )
                        time.sleep(backoff)
        if not results:
            raise RuntimeError("All chunks failed for download")
        return self.combine_results(results)

    @staticmethod
    def combine_results(results):
        if isinstance(results[0], pd.DataFrame):
            return pd.concat(results, ignore_index=True)
        return results

    @abstractmethod
    def download_chunk(self, start: str, end: str, *args, **kwargs):
        """Download one chunk of data."""
        raise NotImplementedError


class EarthEngineDownloader(BaseDownloader):
    """Downloader that fetches index values from Earth Engine."""

    def __init__(
        self,
        sensor: SensorSpec,
        ee_manager: default_manager = default_manager,
        max_retries: int = 3,
        logger=None,
    ) -> None:
        super().__init__(max_retries=max_retries, logger=logger)
        self.sensor = sensor
        self.ee = ee_manager

    def download_chunk(
        self,
        start: str,
        end: str,
        aoi: AOI,
        scale: int,
        index: str,
        value_col: str | None,
    ) -> pd.DataFrame:
        self.ee.initialize()

        geom_geojson = aoi.geometry.__geo_interface__
        ee_geom = ee.Geometry(geom_geojson)
        feature = ee.Feature(ee_geom, {"id": aoi.static_props.get("id")})
        region = ee.FeatureCollection([feature])

        coll = self.ee.get_image_collection(
            self.sensor.collection_id, start, end, region, mask_clouds=False
        )
        coll = mask_collection(coll, self.sensor)

        def _reduce(img):
            idx_img = self.sensor.compute_index(img, index)
            stats = idx_img.reduceRegions(region, ee.Reducer.mean(), scale=scale)
            date = ee.Date(img.get("system:time_start")).format("YYYY-MM-dd")
            return stats.map(lambda f: f.set("date", date))

        features = coll.map(_reduce).flatten().getInfo().get("features", [])
        col = value_col or f"mean_{index}"
        rows = [
            {
                "id": feat["properties"].get("id"),
                "date": feat["properties"].get("date"),
                col: feat["properties"].get("mean"),
            }
            for feat in features
        ]
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        return df
