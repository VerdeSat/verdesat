# verdesat/analytics/stats.py

import pandas as pd
from pandas import Timestamp
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
from scipy.stats import theilslopes, kendalltau


def compute_summary_stats(
    timeseries_csv: str,
    trend_csv: Optional[str] = None,
    decomp_dir: Optional[str] = None,
    period: Optional[int] = 1,
) -> List[Dict]:
    """
    Build per‐site summary stats for your report.
    """
    # 1) Load and pivot
    df = pd.read_csv(timeseries_csv, parse_dates=["date"])
    stats = []
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
        mean_ndvi = grp["mean_ndvi"].mean()
        median_ndvi = grp["mean_ndvi"].median()
        min_ndvi, max_ndvi = grp["mean_ndvi"].min(), grp["mean_ndvi"].max()
        sd_ndvi = grp["mean_ndvi"].std()

        seasonal_amp = np.nan
        resid_rms = np.nan
        peak_month = None
        if decomp_dir:
            decomp_path = Path(decomp_dir) / f"{pid}_decomposition.csv"
            if decomp_path.exists():
                ddf = pd.read_csv(decomp_path, parse_dates=["date"]).set_index("date")
                if period is not None and len(ddf) >= 2 * period:
                    seasonal = ddf["seasonal"]
                    resid = ddf["resid"]
                    seasonal_amp = seasonal.max() - seasonal.min()
                    resid_rms = np.sqrt((resid**2).mean())
                    # peak seasonal month
                    peak_month = None
                    if not seasonal.empty:
                        idx = seasonal.idxmax()
                        # idx should be a pandas Timestamp; guard before formatting
                        if isinstance(idx, Timestamp):
                            peak_month = idx.strftime("%Y-%m")
                        else:
                            peak_month = str(idx)

        # trend via Sen's slope on decomposed trend component
        sen_slope = np.nan
        p_value = np.nan
        trend_change = np.nan
        if (
            decomp_dir
            and decomp_path.exists()
            and period is not None
            and len(ddf) >= 2 * period
        ):
            # use ddf from above
            trend_series = ddf["trend"].dropna()
            if not trend_series.empty:
                # time in years since start of trend_series
                t = (trend_series.index - trend_series.index[0]).days / 365.25
                sen_slope, _, _, _ = theilslopes(trend_series.values, t)
                _, p_value = kendalltau(t, trend_series.values)
                trend_change = trend_series.iloc[-1] - trend_series.iloc[0]

        stats.append(
            {
                "Site ID": pid,
                "Start Date": start.strftime("%Y-%m"),
                "End Date": end.strftime("%Y-%m"),
                "Num Periods": n,
                "% Gapfilled": pct_filled,
                "Mean NDVI": mean_ndvi,
                "Median NDVI": median_ndvi,
                "Min NDVI": min_ndvi,
                "Max NDVI": max_ndvi,
                "Std NDVI": sd_ndvi,
                "Sen's Slope (NDVI/yr)": sen_slope,
                "Trend ΔNDVI": trend_change,
                "Mann–Kendall p-value": p_value,
                "Seasonal Amplitude": seasonal_amp,
                "Peak Month": peak_month,
                "Residual RMS": resid_rms,
            }
        )

    return stats
