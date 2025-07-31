from __future__ import annotations

"""Lightweight helpers for computing demo metrics."""

import numpy as np
import rasterio

import tempfile
import geopandas as gpd
import pandas as pd

from verdesat.webapp.services.r2 import signed_url, upload_bytes
from verdesat.services.bscore import compute_bscores

from verdesat.biodiv.bscore import BScoreCalculator, WeightsConfig
from verdesat.biodiv.metrics import MetricsResult, FragmentStats


THRESHOLD = 0.5


def _read_remote_raster(key: str) -> np.ndarray:
    """Return first band of a COG stored on R2 as a float array."""
    url = signed_url(key)
    with rasterio.open(url) as src:
        arr = src.read(1, masked=True).astype(float)
        return arr.filled(np.nan)


def _basic_stats(arr: np.ndarray) -> tuple[float, float]:
    mask = ~np.isnan(arr)
    return float(np.nanmean(arr[mask])), float(np.nanstd(arr[mask]))


def load_demo_metrics(aoi_id: int) -> dict[str, float]:
    """Compute metrics for a demo AOI using rasters stored on R2."""

    ndvi = _read_remote_raster(f"resources/NDVI_{aoi_id}_2024-01-01.tif")
    msavi = _read_remote_raster(f"resources/MSAVI_{aoi_id}_2024-01-01.tif")
    landcover = _read_remote_raster(f"resources/LANDCOVER_{aoi_id}_2024.tiff")

    intactness = float(np.isin(landcover, [1, 2, 6]).sum() / landcover.size)

    vals = landcover[~np.isnan(landcover)].astype(int).ravel()
    counts = np.bincount(vals)
    probs = counts[counts > 0] / vals.size
    shannon = float(-np.sum(probs * np.log(probs)))

    edges = np.count_nonzero(landcover[:, 1:] != landcover[:, :-1]) + np.count_nonzero(
        landcover[1:, :] != landcover[:-1, :]
    )
    fragmentation = float(edges / landcover.size)

    ndvi_mean, ndvi_std = _basic_stats(ndvi)
    msavi_mean, msavi_std = _basic_stats(msavi)

    calc = BScoreCalculator(WeightsConfig())
    metrics = MetricsResult(
        intactness=intactness,
        shannon=shannon,
        fragmentation=FragmentStats(
            edge_density=fragmentation,
            normalised_density=fragmentation,
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


def compute_live_metrics(gdf: gpd.GeoDataFrame, *, year: int) -> dict[str, float]:
    """Compute metrics for an uploaded AOI and persist the CSV to R2."""

    with tempfile.TemporaryDirectory() as tmpdir:
        aoi_path = f"{tmpdir}/aoi.geojson"
        gdf.to_file(aoi_path, driver="GeoJSON")
        df: pd.DataFrame = compute_bscores(aoi_path, year=year)
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        upload_bytes("results/live_metrics.csv", csv_bytes, content_type="text/csv")
    row = df.iloc[0]
    return {
        "intactness": float(row["intactness"]),
        "shannon": float(row["shannon"]),
        "fragmentation": float(row["fragmentation"]),
        "ndvi_mean": float("nan"),
        "ndvi_std": float("nan"),
        "msavi_mean": row.get("msa", float("nan")),
        "msavi_std": float("nan"),
        "bscore": float(row["bscore"]),
    }
