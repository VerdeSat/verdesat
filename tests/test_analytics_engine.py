import pandas as pd
from verdesat.analytics.engine import AnalyticsEngine
from verdesat.analytics.timeseries import TimeSeries


def test_compute_trend():
    dates = pd.date_range("2020-01-01", periods=3, freq="ME")
    df = pd.DataFrame({"id": [1, 1, 1], "date": dates, "mean_ndvi": [0.1, 0.2, 0.3]})
    ts = TimeSeries.from_dataframe(df, index="ndvi")
    trend_df = AnalyticsEngine.compute_trend(ts)
    assert not trend_df.empty
    assert list(trend_df.columns) == ["id", "date", "trend"]
