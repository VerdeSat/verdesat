from typing import Literal
import pandas as pd  # type: ignore
from statsmodels.tsa.seasonal import seasonal_decompose  # type: ignore


def decompose_timeseries(
    df: pd.DataFrame, column: str = "ndvi", model: str = "additive", freq: int = 12
):
    """
    Perform seasonal decomposition.
    df must have a DatetimeIndex.
    Returns a DecomposeResult with trend, seasonal, resid.
    """
    result = seasonal_decompose(df[column], model=model, period=freq)
    return result


def decompose_each(
    df: pd.DataFrame,
    index_col: str = "mean_ndvi",
    freq: int = 12,
    model: Literal["additive", "multiplicative"] = "additive",
):
    results = {}
    # Each column in df is a polygon ID; perform decomposition per column
    for pid in df.columns:
        series = df[pid].dropna()
        if len(series) < freq * 2:
            continue
        res = seasonal_decompose(series, model=model, period=freq)
        results[pid] = res
    return results
