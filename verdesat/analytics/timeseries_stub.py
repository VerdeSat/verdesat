import pandas as pd


class TimeSeries:
    """
    Holds a time-indexed DataFrame for one variable (e.g., NDVI).
    """

    def __init__(self, variable: str, units: str, freq: str, df: pd.DataFrame):
        self.variable = variable
        self.units = units
        self.freq = freq
        self.df = df

    def fill_gaps(self, method="linear"):
        """Fill missing values in the time series."""
        pass

    def seasonal_decompose(self, period=None):
        """Decompose time series into trend/seasonal/residual."""
        pass

    def to_csv(self, path):
        self.df.to_csv(path)
