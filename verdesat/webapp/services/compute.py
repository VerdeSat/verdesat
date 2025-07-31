from __future__ import annotations

"""Lightweight helpers for computing demo metrics."""

import numpy as np
import rasterio

from verdesat.biodiv.bscore import BScoreCalculator, WeightsConfig
from verdesat.biodiv.metrics import MetricsResult, FragmentStats


THRESHOLD = 0.5


def _basic_stats(arr: np.ndarray) -> tuple[float, float]:
    mask = ~np.isnan(arr)
    return float(np.nanmean(arr[mask])), float(np.nanstd(arr[mask]))


def load_demo_metrics(ndvi_path: str, msavi_path: str) -> dict[str, float]:
    """Compute simple metrics from local NDVI/MSAVI rasters."""

    with rasterio.open(ndvi_path) as src:
        ndvi = src.read(1, masked=True).filled(np.nan)
    with rasterio.open(msavi_path) as src:
        msavi = src.read(1, masked=True).filled(np.nan)

    intactness = float(np.nanmean(ndvi > THRESHOLD))
    hist, _ = np.histogram(ndvi[~np.isnan(ndvi)], bins=6, range=(0, 1))
    probs = hist / hist.sum()
    shannon = float(-np.sum(probs[probs > 0] * np.log(probs[probs > 0])))
    edges = np.count_nonzero(
        (ndvi > THRESHOLD)[:, 1:] != (ndvi > THRESHOLD)[:, :-1]
    ) + np.count_nonzero((ndvi > THRESHOLD)[1:, :] != (ndvi > THRESHOLD)[:-1, :])
    fragmentation = float(edges / ndvi.size)

    ndvi_mean, ndvi_std = _basic_stats(ndvi)
    msavi_mean, msavi_std = _basic_stats(msavi)

    calc = BScoreCalculator(WeightsConfig())
    metrics = MetricsResult(
        intactness=intactness,
        shannon=shannon,
        fragmentation=FragmentStats(
            edge_density=fragmentation, normalised_density=fragmentation
        ),
        msa=msavi_mean,
    )
    bscore = calc.score(metrics)

    return {
        "intactness": intactness,
        "shannon": shannon,
        "fragmentation": fragmentation,
        "ndvi_mean": ndvi_mean,
        "ndvi_std": ndvi_std,
        "msavi_mean": msavi_mean,
        "msavi_std": msavi_std,
        "bscore": bscore,
    }
