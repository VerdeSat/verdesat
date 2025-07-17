from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict

import pandas as pd


@dataclass
class TrendResult:
    """Linear trend values for each polygon."""

    df: pd.DataFrame

    def to_dataframe(self) -> pd.DataFrame:
        """Return the trend values as a DataFrame."""
        return self.df

    def to_csv(self, path: str) -> None:
        """Write the trend values to CSV."""
        self.df.to_csv(path, index=False)


@dataclass
class StatsResult:
    """Summary statistics computed for each polygon."""

    rows: List[Dict]

    def to_dataframe(self) -> pd.DataFrame:
        """Return the statistics as a DataFrame."""
        return pd.DataFrame(self.rows)

    def to_csv(self, path: str) -> None:
        """Write the summary statistics to CSV."""
        self.to_dataframe().to_csv(path, index=False)
