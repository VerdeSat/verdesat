# verd esat/analytics/preprocessing.py
from typing import Literal
import pandas as pd


def interpolate_gaps(
    df: pd.DataFrame,
    date_col: str = "date",
    value_col: str = "mean_ndvi",
    method: Literal["linear", "time"] = "time",
) -> pd.DataFrame:
    """
    Take a uniform‐frequency time-series and fill any NaNs via interpolation.
    Assumes `df` has already been resampled to the desired frequency.
    """
    df = df.copy()
    filled = []
    for pid, grp in df.groupby("id"):
        # set date as index and sort
        grp = grp.set_index(pd.to_datetime(grp[date_col])).sort_index()
        # Drop the original date column to avoid duplicates when resetting index
        grp = grp.drop(columns=[date_col])
        # interpolate and fill
        grp[value_col] = grp[value_col].interpolate(method=method).ffill().bfill()
        # restore id column and date index
        grp = grp.reset_index().rename(columns={"index": date_col})
        grp["id"] = pid
        filled.append(grp)
    return pd.concat(filled, ignore_index=True)
