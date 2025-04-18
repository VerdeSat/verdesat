import pandas as pd # type: ignore
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
