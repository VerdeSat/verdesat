"""
Module `analytics.timeseries` provides the TimeSeries class, which wraps
a pandas DataFrame of spectral index time series and supports aggregation.
"""

from dataclasses import dataclass
from typing import Dict, Literal
from verdesat.core.config import ConfigManager

import pandas as pd
from statsmodels.tsa.seasonal import DecomposeResult, seasonal_decompose


@dataclass
class TimeSeries:
    """Pandas DataFrame wrapper for a single variable time series."""

    df: pd.DataFrame
    index: str

    @classmethod
    def from_dataframe(
        cls, df: pd.DataFrame, index: str = ConfigManager.DEFAULT_INDEX
    ) -> "TimeSeries":
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

    def fill_gaps(self, method: Literal["linear", "time"] = "time") -> "TimeSeries":
        """Interpolate missing values per polygon ID."""

        value_col = f"mean_{self.index}"
        filled_parts = []
        for pid, grp in self.df.groupby("id"):
            grp = grp.copy()
            grp = grp.sort_values("date")
            grp = grp.set_index("date")
            original_missing = grp[value_col].isna()
            grp[value_col] = grp[value_col].interpolate(method=method).ffill().bfill()
            grp["gapfilled"] = original_missing
            grp = grp.reset_index()
            grp["id"] = pid
            filled_parts.append(grp)

        filled_df = pd.concat(filled_parts, ignore_index=True)
        return TimeSeries(filled_df, self.index)

    def decompose(
        self,
        period: int = 12,
        model: Literal["additive", "multiplicative"] = "additive",
    ) -> Dict[str, DecomposeResult]:
        """Perform seasonal decomposition for each polygon."""

        value_col = f"mean_{self.index}"
        df_pivot = self.df.pivot(index="date", columns="id", values=value_col)
        results = {}
        for pid in df_pivot.columns:
            series = df_pivot[pid].dropna()
            if len(series) < period * 2:
                continue
            res = seasonal_decompose(series, model=model, period=period)
            results[pid] = res

        return results

    def to_csv(self, path: str) -> None:
        """Write the underlying DataFrame to CSV."""

        self.df.to_csv(path, index=False)
