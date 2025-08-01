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
from verdesat.analytics.timeseries import TimeSeries
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
) -> tuple[dict[str, float | str], pd.DataFrame, pd.DataFrame]:
    """Compute metrics and VI datasets for a demo AOI.

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

    # ---- NDVI stats from demo decomposition/time-series -----------------
    ndvi_decomp_url = signed_url(f"resources/decomp/{aoi_id}_decomposition.csv")
    ndvi_decomp_df = pd.read_csv(ndvi_decomp_url, parse_dates=["date"])
    ndvi_ts = ndvi_decomp_df[["date", "observed"]].rename(
        columns={"observed": "mean_ndvi"}
    )
    ndvi_ts["id"] = aoi_id
    with tempfile.TemporaryDirectory() as tmpdir:
        ts_path = Path(tmpdir) / "ndvi.csv"
        decomp_path = Path(tmpdir) / f"{aoi_id}_decomposition.csv"
        ndvi_ts.to_csv(ts_path, index=False)
        ndvi_decomp_df.to_csv(decomp_path, index=False)
        stats_df = compute_summary_stats(
            str(ts_path), decomp_dir=tmpdir, value_col="mean_ndvi"
        ).to_dataframe()
    ndvi_row = stats_df.iloc[0]

    # ---- MSAVI stats/time-series -----------------------------------------
    msavi_url = signed_url("resources/msavi.csv")
    msavi_df = pd.read_csv(msavi_url, parse_dates=["date"])
    if "id" in msavi_df.columns:
        msavi_df = msavi_df[msavi_df["id"] == aoi_id]
    with tempfile.TemporaryDirectory() as tmpdir:
        msavi_path = Path(tmpdir) / "msavi.csv"
        msavi_df.to_csv(msavi_path, index=False)
        msavi_stats_df = compute_summary_stats(
            str(msavi_path), value_col="mean_msavi"
        ).to_dataframe()
    msavi_row = msavi_stats_df.iloc[0]

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

    data = {
        "intactness": intactness,
        "shannon": shannon,
        "fragmentation": fragmentation,
        "ndvi_mean": float(ndvi_row["Mean NDVI"]),
        "ndvi_std": float(ndvi_row["Std NDVI"]),
        "ndvi_slope": float(ndvi_row["Sen's Slope (NDVI/yr)"]),
        "ndvi_delta": float(ndvi_row["Trend ΔNDVI"]),
        "ndvi_p_value": float(ndvi_row["Mann–Kendall p-value"]),
        "ndvi_peak": ndvi_row["Peak Month"] if pd.notna(ndvi_row["Peak Month"]) else "",
        "ndvi_pct_fill": float(ndvi_row["% Gapfilled"]),
        "msavi_mean": float(msavi_row["Mean MSAVI"]),
        "msavi_std": float(msavi_row["Std MSAVI"]),
        "bscore": bscore,
    }
    return data, ndvi_decomp_df, msavi_df


def _ndvi_stats(
    aoi_path: str, year: int
) -> tuple[dict[str, float | str], pd.DataFrame]:
    """Return NDVI stats and decomposition for ``aoi_path``."""

    ts_df = download_timeseries(
        geojson=aoi_path,
        start=f"{year}-01-01",
        end=f"{year}-12-31",
        index="ndvi",
        chunk_freq="ME",
    )
    ts = TimeSeries.from_dataframe(ts_df, index="ndvi").fill_gaps()
    decomp = ts.decompose(period=12)
    pid = ts.df["id"].iloc[0]
    res = decomp.get(pid)
    if res is None:  # pragma: no cover - requires non-empty series
        raise ValueError("decomposition failed")
    decomp_df = pd.DataFrame(
        {
            "date": res.observed.index,
            "observed": res.observed.values,
            "trend": res.trend.values,
            "seasonal": res.seasonal.values,
            "resid": res.resid.values,
        }
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        ts_path = Path(tmpdir) / "ndvi.csv"
        decomp_path = Path(tmpdir) / f"{pid}_decomposition.csv"
        ts.df.to_csv(ts_path, index=False)
        decomp_df.to_csv(decomp_path, index=False)
        stats_df = compute_summary_stats(
            str(ts_path), decomp_dir=tmpdir, value_col="mean_ndvi"
        ).to_dataframe()
    row = stats_df.iloc[0]
    stats = {
        "ndvi_mean": float(row["Mean NDVI"]),
        "ndvi_std": float(row["Std NDVI"]),
        "ndvi_slope": float(row["Sen's Slope (NDVI/yr)"]),
        "ndvi_delta": float(row["Trend ΔNDVI"]),
        "ndvi_p_value": float(row["Mann–Kendall p-value"]),
        "ndvi_peak": row["Peak Month"] if pd.notna(row["Peak Month"]) else "",
        "ndvi_pct_fill": float(row["% Gapfilled"]),
    }
    return stats, decomp_df[["date", "observed", "trend", "seasonal"]]


def _msavi_stats(aoi_path: str, year: int) -> tuple[dict[str, float], pd.DataFrame]:
    """Return MSAVI stats and monthly time series for ``aoi_path``."""

    ts_df = download_timeseries(
        geojson=aoi_path,
        start=f"{year}-01-01",
        end=f"{year}-12-31",
        index="msavi",
        chunk_freq="ME",
    )
    ts = TimeSeries.from_dataframe(ts_df, index="msavi").fill_gaps()
    with tempfile.TemporaryDirectory() as tmpdir:
        ts_path = Path(tmpdir) / "msavi.csv"
        ts.df.to_csv(ts_path, index=False)
        stats_df = compute_summary_stats(
            str(ts_path), value_col="mean_msavi"
        ).to_dataframe()
    row = stats_df.iloc[0]
    stats = {
        "msavi_mean": float(row["Mean MSAVI"]),
        "msavi_std": float(row["Std MSAVI"]),
    }
    return stats, ts.df


def compute_live_metrics(
    gdf: gpd.GeoDataFrame, *, year: int
) -> tuple[dict[str, float | str], pd.DataFrame, pd.DataFrame]:
    """Compute metrics and VI datasets for an uploaded AOI."""

    with tempfile.TemporaryDirectory() as tmpdir:
        aoi_path = Path(tmpdir) / "aoi.geojson"
        gdf.to_file(aoi_path, driver="GeoJSON")
        df: pd.DataFrame = compute_bscores(str(aoi_path), year=year)
        ndvi_stats, ndvi_decomp = _ndvi_stats(str(aoi_path), year)
        msavi_stats, msavi_df = _msavi_stats(str(aoi_path), year)
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        upload_bytes("results/live_metrics.csv", csv_bytes, content_type="text/csv")

    row = df.iloc[0]
    data: dict[str, float | str] = {
        "intactness": float(row["intactness"]),
        "shannon": float(row["shannon"]),
        "fragmentation": float(row["fragmentation"]),
        "bscore": float(row["bscore"]),
    }
    data.update(ndvi_stats)
    data.update(msavi_stats)
    return data, ndvi_decomp, msavi_df
