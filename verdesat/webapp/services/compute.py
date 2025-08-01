from __future__ import annotations

"""Utility functions for computing biodiversity metrics for the web app.

The original implementation was a thin mock that returned hard-coded or
placeholder values (e.g. ``msa`` was set to the MSAVI mean).  This module now
leverages the real service layer used by the CLI, providing consistent
calculations for the Streamlit dashboard.  It exposes helpers for both the
demo AOIs and user provided uploads.
"""

from pathlib import Path
import tempfile

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio

from verdesat.analytics.stats import compute_summary_stats
from verdesat.services.bscore import compute_bscores
from verdesat.services.msa import MSAService
from verdesat.services.timeseries import download_timeseries
from verdesat.webapp.services.r2 import signed_url, upload_bytes

from verdesat.biodiv.bscore import BScoreCalculator, WeightsConfig
from verdesat.biodiv.metrics import FragmentStats, MetricsResult


def _read_remote_raster(key: str) -> np.ndarray:
    """Return first band of a COG stored on R2 as a float array."""
    url = signed_url(key)
    with rasterio.open(url) as src:
        arr = src.read(1, masked=True).astype(float)
        return arr.filled(np.nan)


def _basic_stats(arr: np.ndarray) -> tuple[float, float]:
    mask = ~np.isnan(arr)
    return float(np.nanmean(arr[mask])), float(np.nanstd(arr[mask]))


def load_demo_metrics(
    aoi_id: int, gdf: gpd.GeoDataFrame, *, year: int
) -> dict[str, float]:
    """Compute metrics for a demo AOI using rasters stored on R2.

    Parameters
    ----------
    aoi_id:
        Identifier of the AOI within ``gdf``.
    gdf:
        GeoDataFrame containing all demo AOIs. The geometry is required to
        compute MSA using :class:`~verdesat.services.msa.MSAService`.
    year:
        Year used for land-cover based metrics. Currently only 2024 demo rasters
        are available.
    """

    ndvi = _read_remote_raster(f"resources/NDVI_{aoi_id}_{year}-01-01.tif")
    msavi = _read_remote_raster(f"resources/MSAVI_{aoi_id}_{year}-01-01.tif")
    landcover = _read_remote_raster(f"resources/LANDCOVER_{aoi_id}_{year}.tiff")

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

    msa_val = float("nan")
    try:
        geom = gdf.loc[gdf["id"] == aoi_id].geometry.iloc[0]
        msa_val = MSAService().mean_msa(geom)
    except Exception:  # pragma: no cover - network or raster issues
        pass

    calc = BScoreCalculator(WeightsConfig())
    metrics = MetricsResult(
        intactness=intactness,
        shannon=shannon,
        fragmentation=FragmentStats(
            edge_density=fragmentation,
            normalised_density=fragmentation,
        ),
        msa=msa_val,
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


def _vi_stats(aoi_path: str, index: str, year: int) -> tuple[float, float]:
    """Return mean and standard deviation for a spectral index.

    The function downloads a time series for ``index`` using the existing
    :func:`~verdesat.services.timeseries.download_timeseries` helper and then
    summarises it via :func:`~verdesat.analytics.stats.compute_summary_stats`.
    Any error while fetching the time series results in ``nan`` values to avoid
    breaking the web application when optional dependencies are missing.
    """

    try:
        ts_df = download_timeseries(
            geojson=aoi_path,
            start=f"{year}-01-01",
            end=f"{year}-12-31",
            index=index,
            chunk_freq="ME",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / f"{index}.csv"
            ts_df.to_csv(csv_path, index=False)
            stats_df = compute_summary_stats(
                str(csv_path), value_col=f"mean_{index}"
            ).to_dataframe()
        row = stats_df.iloc[0]
        mean_key = f"Mean {index.upper()}"
        std_key = f"Std {index.upper()}"
        return float(row[mean_key]), float(row[std_key])
    except Exception:  # pragma: no cover - network or EE failures
        return float("nan"), float("nan")


def compute_live_metrics(gdf: gpd.GeoDataFrame, *, year: int) -> dict[str, float]:
    """Compute metrics for an uploaded AOI and persist the CSV to R2."""

    with tempfile.TemporaryDirectory() as tmpdir:
        aoi_path = Path(tmpdir) / "aoi.geojson"
        gdf.to_file(aoi_path, driver="GeoJSON")
        df: pd.DataFrame = compute_bscores(str(aoi_path), year=year)
        ndvi_mean, ndvi_std = _vi_stats(str(aoi_path), "ndvi", year)
        msavi_mean, msavi_std = _vi_stats(str(aoi_path), "msavi", year)
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        upload_bytes("results/live_metrics.csv", csv_bytes, content_type="text/csv")

    row = df.iloc[0]
    return {
        "intactness": float(row["intactness"]),
        "shannon": float(row["shannon"]),
        "fragmentation": float(row["fragmentation"]),
        "ndvi_mean": ndvi_mean,
        "ndvi_std": ndvi_std,
        "msavi_mean": msavi_mean,
        "msavi_std": msavi_std,
        "bscore": float(row["bscore"]),
    }
