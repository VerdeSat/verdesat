"""
Module `analytics.timeseries` provides the TimeSeries class, which wraps
a pandas DataFrame of spectral index time series and supports aggregation.
"""

from typing import Literal

import pandas as pd


class TimeSeries:
    """
    Holds a time-indexed DataFrame for one variable (e.g., NDVI).
    """

    def __init__(self, df: pd.DataFrame, index: str):
        self.df = df
        self.index = index

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame, index: str = "ndvi") -> "TimeSeries":
        """
        Create a TimeSeries from a DataFrame with columns ['id', 'date', f'mean_{index}'].
        Ensures 'date' column is parsed as datetime.
        """
        df_copy = df.copy()
        df_copy["date"] = pd.to_datetime(df_copy["date"])
        return cls(df_copy, index)

    def aggregate(self, freq: Literal["D", "ME", "YE"]) -> "TimeSeries":
        """
        Aggregate the time series to the given frequency:
          'D' = daily (no-op), 'ME' = monthly mean, 'YE' = yearly mean.
        Returns a new TimeSeries.
        """
        col_name = f"mean_{self.index}"
        df_indexed = self.df.set_index(["id", "date"])
        aggregated = (
            df_indexed[col_name]
            .groupby(level=0)
            .resample(freq, level=1)
            .mean()
            .reset_index()
        )
        return TimeSeries(aggregated, self.index)
