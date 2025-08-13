# verdesat/analytics/stats.py

import io
from pathlib import Path
from typing import IO, Mapping, Optional, cast

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
    trend_csv: Optional[str | IO[bytes] | pd.DataFrame] = None,
    decomp_dir: Optional[str | Mapping[int, IO[bytes] | pd.DataFrame]] = None,
    period: Optional[int] = 1,
    value_col: str = ConfigManager.VALUE_COL_TEMPLATE.format(
        index=ConfigManager.DEFAULT_INDEX
    ),
) -> StatsResult:
    """Build per-site summary stats and return them as a :class:`StatsResult`.

    ``timeseries_csv`` may be a path, file-like object or DataFrame. ``decomp_dir``
    accepts either a directory path or a mapping of site IDs to in-memory CSV
    buffers/DataFrames containing decomposition results.
    """
    # 1) Load and pivot
    if isinstance(timeseries_csv, pd.DataFrame):
        df = timeseries_csv.copy()
        if not pd.api.types.is_datetime64_any_dtype(df["date"]):
            df["date"] = pd.to_datetime(df["date"])
    else:
        df = pd.read_csv(timeseries_csv, parse_dates=["date"])

    stats: list[dict[str, float | int | str | None]] = []
    for pid, grp in df.groupby("id"):
        grp = grp.sort_values("date").set_index("date")
        n = len(grp)
        start, end = grp.index[0], grp.index[-1]

        # percentage of missing values that were filled
        if "gapfilled" in grp.columns:
            pct_filled = grp["gapfilled"].mean() * 100
        else:
            pct_filled = np.nan

        # time-series metrics
        mean_ndvi = grp[value_col].mean()
        median_ndvi = grp[value_col].median()
        min_ndvi, max_ndvi = grp[value_col].min(), grp[value_col].max()
        sd_ndvi = grp[value_col].std()

        seasonal_amp = np.nan
        resid_rms = np.nan
        peak_month: str | None = None
        ddf = None
        if decomp_dir:
            if isinstance(decomp_dir, Mapping):
                buf = decomp_dir.get(cast(int, pid))
                if isinstance(buf, pd.DataFrame):
                    ddf = buf.set_index("date")
                elif buf is not None:
                    if isinstance(buf, io.BytesIO):
                        buf.seek(0)
                    ddf = pd.read_csv(buf, parse_dates=["date"]).set_index("date")
            else:
                decomp_path = Path(decomp_dir) / f"{pid}_decomposition.csv"
                if decomp_path.exists():
                    ddf = pd.read_csv(decomp_path, parse_dates=["date"]).set_index(
                        "date"
                    )

        if ddf is not None and period is not None and len(ddf) >= 2 * period:
            seasonal = ddf["seasonal"]
            resid = ddf["resid"]
            seasonal_amp = seasonal.max() - seasonal.min()
            resid_rms = np.sqrt((resid**2).mean())
            if not seasonal.empty:
                idx = seasonal.idxmax()
                if isinstance(idx, Timestamp):
                    peak_month = idx.strftime("%Y-%m")
                else:
                    peak_month = str(idx)

        # trend via Sen's slope on decomposed trend component
        sen_slope = np.nan
        p_value = np.nan
        trend_change = np.nan
        if ddf is not None and period is not None and len(ddf) >= 2 * period:
            trend_series = ddf["trend"].dropna()
            if not trend_series.empty:
                t = (trend_series.index - trend_series.index[0]).days / 365.25
                sen_slope, _, _, _ = theilslopes(trend_series.values, t)
                _, p_value = kendalltau(t, trend_series.values)
                trend_change = trend_series.iloc[-1] - trend_series.iloc[0]

        label = value_col.replace("mean_", "").upper()
        stats.append(
            {
                "Site ID": int(cast(int, pid)),
                "Start Date": start.strftime("%Y-%m"),
                "End Date": end.strftime("%Y-%m"),
                "Num Periods": n,
                "% Gapfilled": pct_filled,
                f"Mean {label}": mean_ndvi,
                f"Median {label}": median_ndvi,
                f"Min {label}": min_ndvi,
                f"Max {label}": max_ndvi,
                f"Std {label}": sd_ndvi,
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
    decomp_dir: Optional[str | Mapping[int, IO[bytes] | pd.DataFrame]] = None,
    aoi_id: str | None = None,
) -> dict[str, float | str | None]:
    """Compute vegetation metrics in canonical field names.

    Parameters
    ----------
    timeseries_csv:
        Path or buffer to a pivoted time-series CSV with at least ``mean_ndvi``
        and ``id`` columns.
    decomp_dir:
        Optional directory containing decomposition outputs produced by
        ``stats decompose``. Enables trend statistics.
    aoi_id:
        AOI identifier to include in the resulting metrics row.
    """

    logger.info("Loading %s for vegetation metrics", timeseries_csv)
    if isinstance(timeseries_csv, pd.DataFrame):
        df = timeseries_csv.copy()
    else:
        df = pd.read_csv(timeseries_csv, parse_dates=["date"])

    stats_df = compute_summary_stats(df, decomp_dir=decomp_dir).to_dataframe()
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

    if "mean_msavi" in df.columns:
        metrics["msavi_mean"] = float(df["mean_msavi"].mean())

    return metrics
