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
from verdesat.services.msa import MSAService


def compute_bscores(
    geojson: str,
    *,
    year: int,
    weights: WeightsConfig | None = None,
    dataset_uri: str | None = None,
    budget_bytes: int = 50_000_000,
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
    dataset_uri:
        Optional URI of the MSA raster. Defaults to
        :data:`MSAService.DEFAULT_DATASET_URI`.
    budget_bytes:
        Maximum bytes allowed to be read from the dataset.
    output:
        Optional CSV path. If provided, the resulting DataFrame is written.
    logger:
        Optional logger for progress messages.
    storage:
        Storage backend used by ``MetricEngine``. Defaults to ``LocalFS``.

    Returns
    -------
    pandas.DataFrame
        A dataframe containing ``id`` and all metric values alongside the
        computed ``bscore`` for each AOI.
    """

    log = logger or Logger.get_logger(__name__)
    log.info("Loading AOIs from %s", geojson)
    aois = AOI.from_geojson(geojson, id_col="id")

    engine = MetricEngine(storage=storage or LocalFS(), logger=log)
    msa_svc = MSAService(
        storage=storage or LocalFS(),
        logger=log,
        budget_bytes=budget_bytes,
        dataset_uri=dataset_uri,
    )
    calc = BScoreCalculator(weights)

    records = []
    for aoi in aois:
        metrics = engine.run_all(aoi, year)
        metrics.msa = msa_svc.mean_msa(aoi.geometry)
        score = calc.score(metrics)
        records.append(
            {
                "id": aoi.static_props.get("id"),
                "intactness": metrics.intactness,
                "shannon": metrics.shannon,
                "edge_density": metrics.fragmentation.edge_density,
                "fragmentation": metrics.fragmentation.normalised_density,
                "msa": metrics.msa,
                "bscore": score,
            }
        )

    df = pd.DataFrame.from_records(records)
    if output:
        log.info("Writing results to %s", output)
        df.to_csv(output, index=False)
    return df
