from __future__ import annotations

"""Service for computing biodiversity scores from AOI collections."""

from typing import Optional
import logging
import pandas as pd

from verdesat.core.logger import Logger
from verdesat.core.storage import LocalFS, StorageAdapter
from verdesat.geo.aoi import AOI
from verdesat.biodiv.metrics import MetricEngine
from verdesat.biodiv.bscore import BScoreCalculator, WeightsConfig


def compute_bscores(
    geojson: str,
    *,
    year: int,
    weights: WeightsConfig | None = None,
    output: str | None = None,
    logger: logging.Logger | None = None,
    storage: StorageAdapter | None = None,
) -> pd.DataFrame:
    """Compute biodiversity scores for AOIs in ``geojson``.

    Parameters
    ----------
    geojson:
        Path to the AOI GeoJSON file with an ``id`` property for each feature.
    year:
        Land-cover year used for metric calculation.
    weights:
        Optional ``WeightsConfig``. When not provided values are loaded from the
        default YAML file.
    output:
        Optional CSV path. If provided, the resulting DataFrame is written.
    logger:
        Optional logger for progress messages.
    storage:
        Storage backend used by ``MetricEngine``. Defaults to ``LocalFS``.
    """

    log = logger or Logger.get_logger(__name__)
    log.info("Loading AOIs from %s", geojson)
    aois = AOI.from_geojson(geojson, id_col="id")

    engine = MetricEngine(storage=storage or LocalFS(), logger=log)
    calc = BScoreCalculator(weights)

    records = []
    for aoi in aois:
        metrics = engine.run_all(aoi, year)
        score = calc.score(metrics)
        records.append({"id": aoi.static_props.get("id"), "bscore": score})

    df = pd.DataFrame.from_records(records)
    if output:
        log.info("Writing results to %s", output)
        df.to_csv(output, index=False)
    return df
