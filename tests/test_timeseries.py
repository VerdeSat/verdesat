import pandas as pd
from verdesat.analytics.timeseries import TimeSeries


def test_fill_gaps_and_to_csv(tmp_path):
    df = pd.DataFrame(
        {
            "id": [1, 1, 1, 2, 2],
            "date": [
                "2020-01-01",
                "2020-02-01",
                "2020-03-01",
                "2020-01-01",
                "2020-02-01",
            ],
            "mean_ndvi": [0.1, None, 0.3, 0.2, None],
        }
    )
    ts = TimeSeries.from_dataframe(df, index="ndvi")
    filled = ts.fill_gaps()
    # no NaNs after filling
    assert not filled.df["mean_ndvi"].isna().any()
    # gapfilled column marks the missing rows
    assert filled.df["gapfilled"].sum() == 2

    out = tmp_path / "out.csv"
    filled.to_csv(str(out))
    loaded = pd.read_csv(out)
    assert len(loaded) == len(filled.df)


def test_decompose():
    dates = pd.date_range("2020-01-01", periods=24, freq="ME")
    values = pd.Series(range(24)) + pd.Series([1] * 24)
    df = pd.DataFrame({"id": 1, "date": dates, "mean_ndvi": values})
    ts = TimeSeries.from_dataframe(df, index="ndvi")
    res = ts.decompose(period=12)
    assert 1 in res
    assert res[1].trend is not None
