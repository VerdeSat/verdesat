"""Service for computing biodiversity scores from AOI collections."""

from __future__ import annotations

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
    project_id: str | None = None,
    project_name: str | None = None,
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
    project_id, project_name:
        Optional project metadata to add to each record.

    Returns
    -------
    pandas.DataFrame
        A dataframe containing ``aoi_id`` and canonical metric columns
        alongside the computed ``bscore`` for each AOI.
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

        if score < 33.3:
            band = "low"
        elif score < 66.6:
            band = "moderate"
        else:
            band = "high"

        rec = {
            "aoi_id": aoi.static_props.get("id"),
            "intactness_pct": metrics.intactness_pct,
            "shannon": metrics.shannon,
            "frag_norm": metrics.fragmentation.frag_norm,
            "msa": metrics.msa,
            "bscore": score,
            "bscore_band": band,
            "window_start": f"{year}-01-01",
            "window_end": f"{year}-12-31",
            "method_version": "0.2.0",
            "geometry_path": geojson,
        }
        rec["project_id"] = project_id or aoi.static_props.get("project_id")
        rec["project_name"] = project_name or aoi.static_props.get("project_name")
        if "aoi_name" in aoi.static_props:
            rec["aoi_name"] = aoi.static_props.get("aoi_name")
        records.append(rec)

    df = pd.DataFrame.from_records(records)
    if output:
        log.info("Writing results to %s", output)
        df.to_csv(output, index=False)
    return df
