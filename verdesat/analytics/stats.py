# verdesat/analytics/stats.py

from typing import IO

import numpy as np
import pandas as pd
from pandas import Timestamp
from scipy.stats import kendalltau, theilslopes

from verdesat.core.config import ConfigManager
from verdesat.core.logger import Logger
from .results import StatsResult


logger = Logger.get_logger(__name__)


def compute_summary_stats(
    timeseries_csv: str | IO[bytes] | pd.DataFrame,
    *,
    var: str = ConfigManager.DEFAULT_INDEX,
    period: int | None = 1,
) -> StatsResult:
    """Build per-site summary stats from a ``TimeseriesLong`` dataset."""

    if isinstance(timeseries_csv, pd.DataFrame):
        df = timeseries_csv.copy()
    else:
        df = pd.read_csv(timeseries_csv, parse_dates=["date"])

    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"])

    df = df[df["var"] == var]
    stats: list[dict[str, float | int | str | None]] = []

    for aid, grp in df.groupby("aoi_id"):
        raw = grp[grp["stat"] == "raw"].sort_values("date")
        if raw.empty:
            continue
        n = len(raw)
        start, end = raw["date"].iloc[0], raw["date"].iloc[-1]

        mean_val = raw["value"].mean()
        median_val = raw["value"].median()
        min_val, max_val = raw["value"].min(), raw["value"].max()
        sd_val = raw["value"].std()

        seasonal_amp = np.nan
        resid_rms = np.nan
        peak_month: str | None = None
        seasonal = grp[grp["stat"] == "seasonal"].set_index("date")["value"]
        resid = grp[grp["stat"] == "anomaly"].set_index("date")["value"]
        if period is not None and len(seasonal) >= 2 * period:
            seasonal_amp = seasonal.max() - seasonal.min()
            if not seasonal.empty:
                idx = seasonal.idxmax()
                peak_month = (
                    idx.strftime("%Y-%m") if isinstance(idx, Timestamp) else str(idx)
                )
        if period is not None and len(resid) >= 2 * period:
            resid_rms = np.sqrt((resid**2).mean())

        sen_slope = np.nan
        p_value = np.nan
        trend_change = np.nan
        trend = grp[grp["stat"] == "trend"].set_index("date")["value"].dropna()
        if period is not None and len(trend) >= 2 * period:
            t = (trend.index - trend.index[0]).days / 365.25
            sen_slope, _, _, _ = theilslopes(trend.values, t)
            _, p_value = kendalltau(t, trend.values)
            trend_change = trend.iloc[-1] - trend.iloc[0]

        label = var.upper()
        stats.append(
            {
                "Site ID": str(aid),
                "Start Date": start.strftime("%Y-%m"),
                "End Date": end.strftime("%Y-%m"),
                "Num Periods": n,
                "% Gapfilled": np.nan,
                f"Mean {label}": mean_val,
                f"Median {label}": median_val,
                f"Min {label}": min_val,
                f"Max {label}": max_val,
                f"Std {label}": sd_val,
                f"Sen's Slope ({label}/yr)": sen_slope,
                f"Trend Δ{label}": trend_change,
                "Mann–Kendall p-value": p_value,
                "Seasonal Amplitude": seasonal_amp,
                "Peak Month": peak_month,
                "Residual RMS": resid_rms,
            }
        )

    return StatsResult(stats)


def compute_veg_metrics(
    timeseries_csv: str | IO[bytes] | pd.DataFrame,
    *,
    aoi_id: str | None = None,
) -> dict[str, float | str | None]:
    """Compute vegetation metrics in canonical field names."""

    logger.info("Loading %s for vegetation metrics", timeseries_csv)
    if isinstance(timeseries_csv, pd.DataFrame):
        df = timeseries_csv.copy()
    else:
        df = pd.read_csv(timeseries_csv, parse_dates=["date"])

    stats_df = compute_summary_stats(df).to_dataframe()
    if stats_df.empty:
        logger.warning("No rows produced for vegetation metrics")
        stats_df = pd.DataFrame(
            [
                {
                    "Mean NDVI": np.nan,
                    "Sen's Slope (NDVI/yr)": np.nan,
                    "Trend ΔNDVI": np.nan,
                    "Mann–Kendall p-value": np.nan,
                }
            ]
        )

    row = stats_df.iloc[0]
    metrics: dict[str, float | str | None] = {
        "aoi_id": aoi_id,
        "ndvi_mean": float(row.get("Mean NDVI", np.nan)),
        "ndvi_slope": float(row.get("Sen's Slope (NDVI/yr)", np.nan)),
        "ndvi_delta": float(row.get("Trend ΔNDVI", np.nan)),
        "ndvi_p_value": float(row.get("Mann–Kendall p-value", np.nan)),
    }

    msavi = df[(df["var"] == "msavi") & (df["stat"] == "raw")]
    if not msavi.empty:
        metrics["msavi_mean"] = float(msavi["value"].mean())

    return metrics
