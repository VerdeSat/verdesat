"""Tests for EarthEngineIngestor time‑series download helper."""

# pylint: disable=W0621,W0613,C0103,missing-class-docstring,missing-function-docstring,line-too-long


import pandas as pd

from verdesat.ingestion.earthengine_ingestor import EarthEngineIngestor
from verdesat.visualization._chips_config import ChipsConfig


def test_download_timeseries_no_aggregation(
    dummy_aoi, dummy_sensor, _dummy_ee_manager, monkeypatch
):
    """
    Test that EarthEngineIngestor.download_timeseries returns a DataFrame with correct columns
    for one daily chunk, without aggregation (freq=None).
    """
    # Stub out chunked retrieval to return a known DataFrame
    monkeypatch.setattr(
        EarthEngineIngestor,
        "_chunked_timeseries",
        lambda self, aoi, s, e, scale, index, value_col, chunk_freq: pd.DataFrame(
            [{"id": 1, "date": "2020-01-01", f"{value_col or 'mean_'+index}": 0.5}]
        ),
    )
    di = EarthEngineIngestor(sensor=dummy_sensor)
    df = di.download_timeseries(
        dummy_aoi,
        start_date="2020-01-01",
        end_date="2020-01-01",
        scale=30,
        index="ndvi",
        chunk_freq="D",
        value_col="mean_ndvi",
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
    Test that EarthEngineIngestor.download_timeseries with freq='M' returns a DataFrame
    resampled to monthly (here, single month so no change).
    """
    # Stub out chunked retrieval to return a known daily DataFrame over January 2020
    raw_data = [
        {"id": 1, "date": f"2020-01-{day:02d}", "mean_ndvi": 0.5}
        for day in range(1, 32)
    ]
    monkeypatch.setattr(
        EarthEngineIngestor,
        "_chunked_timeseries",
        lambda self, aoi, s, e, scale, index, value_col, chunk_freq: pd.DataFrame(
            raw_data
        ),
    )
    di = EarthEngineIngestor(sensor=dummy_sensor)
    df_agg = di.download_timeseries(
        dummy_aoi,
        start_date="2020-01-01",
        end_date="2020-01-31",
        scale=30,
        index="ndvi",
        chunk_freq="ME",
        value_col="mean_ndvi",
        freq="ME",
    )
    # With only a single value, monthly aggregation still yields one row
    assert isinstance(df_agg, pd.DataFrame)
    assert list(df_agg.columns) == ["id", "date", "mean_ndvi"]
    # Date should be the month‐start or aggregated index (since only one point).
    assert pd.to_datetime(df_agg.iloc[0]["date"]).month == 1


def test_download_chips_delegation(dummy_aoi, dummy_sensor, monkeypatch, tmp_path):
    """EarthEngineIngestor.download_chips should delegate to ChipService."""

    calls = {}

    class FakeService:
        def __init__(self, ee_manager, sensor_spec, logger=None):
            calls["init"] = (ee_manager, sensor_spec)

        def run(self, aois, config):
            calls["run"] = (aois, config)

    monkeypatch.setattr(
        "verdesat.ingestion.earthengine_ingestor.ChipService", FakeService
    )

    di = EarthEngineIngestor(sensor=dummy_sensor)

    cfg = ChipsConfig(
        collection_id="dummy/collection",
        start="2024-01-01",
        end="2024-12-31",
        period="year",
        chip_type="ndvi",
        scale=30,
        buffer=0,
        buffer_percent=None,
        min_val=None,
        max_val=None,
        gamma=None,
        percentile_low=None,
        percentile_high=None,
        palette=None,
        fmt="png",
        out_dir=str(tmp_path),
        mask_clouds=True,
    )

    di.download_chips([dummy_aoi], cfg)

    assert "init" in calls and "run" in calls
    assert calls["run"][0] == [dummy_aoi]
    assert calls["run"][1] is cfg
