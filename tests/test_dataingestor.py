"""
Tests for DataIngestor time‑series download helper.
"""

# pylint: disable=W0621,W0613,C0103,missing-class-docstring,missing-function-docstring,line-too-long


import pandas as pd

from verdesat.ingestion.dataingestor import DataIngestor


def test_download_timeseries_no_aggregation(
    dummy_aoi, dummy_sensor, _dummy_ee_manager, monkeypatch
):
    """
    Test that DataIngestor.download_timeseries returns a DataFrame with correct columns
    for one daily chunk, without aggregation (freq=None).
    """
    # Stub out chunked retrieval to return a known DataFrame
    monkeypatch.setattr(
        DataIngestor,
        "_chunked_timeseries",
        lambda self, aoi, start_date, end_date, scale, index, chunk_freq: pd.DataFrame(
            [{"id": 1, "date": "2020-01-01", f"mean_{index}": 0.5}]
        ),
    )
    di = DataIngestor(sensor=dummy_sensor)
    df = di.download_timeseries(
        dummy_aoi,
        start_date="2020-01-01",
        end_date="2020-01-01",
        scale=30,
        index="ndvi",
        chunk_freq="D",
        freq=None,
    )

    # Expect a DataFrame with one row, columns ['id','date','mean_ndvi']
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["id", "date", "mean_ndvi"]
    assert df.iloc[0]["id"] == 1
    assert pd.to_datetime(df.iloc[0]["date"]) == pd.to_datetime("2020-01-01")
    assert df.iloc[0]["mean_ndvi"] == 0.5


def test_download_timeseries_with_aggregation(
    dummy_aoi, dummy_sensor, _dummy_ee_manager, monkeypatch
):
    """
    Test that DataIngestor.download_timeseries with freq='M' returns a DataFrame
    resampled to monthly (here, single month so no change).
    """
    # Stub out chunked retrieval to return a known daily DataFrame over January 2020
    raw_data = [
        {"id": 1, "date": f"2020-01-{day:02d}", "mean_ndvi": 0.5}
        for day in range(1, 32)
    ]
    monkeypatch.setattr(
        DataIngestor,
        "_chunked_timeseries",
        lambda self, aoi, start_date, end_date, scale, index, chunk_freq: pd.DataFrame(
            raw_data
        ),
    )
    di = DataIngestor(sensor=dummy_sensor)
    df_agg = di.download_timeseries(
        dummy_aoi,
        start_date="2020-01-01",
        end_date="2020-01-31",
        scale=30,
        index="ndvi",
        chunk_freq="ME",
        freq="ME",
    )
    # With only a single value, monthly aggregation still yields one row
    assert isinstance(df_agg, pd.DataFrame)
    assert list(df_agg.columns) == ["id", "date", "mean_ndvi"]
    # Date should be the month‐start or aggregated index (since only one point).
    assert pd.to_datetime(df_agg.iloc[0]["date"]).month == 1
