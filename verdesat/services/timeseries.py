from __future__ import annotations

"""Service functions for time-series operations."""

from typing import List, Optional, Literal

import pandas as pd

import logging
from verdesat.core.logger import Logger
from verdesat.core.config import ConfigManager
from verdesat.geo.aoi import AOI
from verdesat.ingestion.sensorspec import SensorSpec
from verdesat.ingestion import create_ingestor
from verdesat.ingestion.eemanager import ee_manager


def download_timeseries(
    geojson: str,
    collection: str = "NASA/HLS/HLSL30/v002",
    start: str = "2015-01-01",
    end: str = "2024-12-31",
    scale: int = 30,
    index: str = ConfigManager.DEFAULT_INDEX,
    value_col: str | None = None,
    chunk_freq: Literal["D", "ME", "YE"] = "YE",
    agg: Optional[Literal["D", "ME", "YE"]] = None,
    output: str | None = None,
    backend: str = "ee",
    logger: logging.Logger | None = None,
) -> pd.DataFrame:
    """Download spectral index time series for polygons in *geojson*.

    Parameters largely mirror the ``verdesat`` CLI ``download timeseries``
    command. When *output* is provided the resulting DataFrame is written to
    CSV. The concatenated DataFrame is always returned.
    """

    log = logger or Logger.get_logger(__name__)
    log.info("Loading AOIs from %s", geojson)

    aois = AOI.from_geojson(geojson, id_col="id")
    sensor = SensorSpec.from_collection_id(collection)
    ingestor = create_ingestor(
        backend, sensor, ee_manager_instance=ee_manager, logger=log
    )

    value_column = value_col or ConfigManager.VALUE_COL_TEMPLATE.format(index=index)
    df_list: List[pd.DataFrame] = []

    for aoi in aois:
        df = ingestor.download_timeseries(
            aoi,
            start,
            end,
            scale,
            index,
            value_column,
            chunk_freq,
            agg,
        )
        df_list.append(df)

    result = pd.concat(df_list, ignore_index=True)

    if output:
        log.info("Writing results to %s", output)
        result.to_csv(output, index=False)
    return result
