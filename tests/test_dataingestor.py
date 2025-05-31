"""
Tests for DataIngestor time‑series download helper.
"""

# pylint: disable=W0621,W0613,C0103,missing-class-docstring,missing-function-docstring,line-too-long

import pytest
import pandas as pd

from shapely.geometry import Polygon

from verdesat.ingestion.dataingestor import DataIngestor
from verdesat.geo.aoi import AOI


@pytest.fixture
def dummy_aoi():
    """
    Create a dummy AOI with a simple square Polygon and an 'id' in static_props.
    """
    geom = Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])
    return AOI(geometry=geom, static_props={"id": 1})


@pytest.fixture
def dummy_sensor():
    """
    Dummy sensor with minimal attributes and a pass‑through compute_index.
    """

    class DummySensor:
        def __init__(self):
            self.collection_id = "dummy/collection"

        @staticmethod  # noqa: D401
        def compute_index(img, index):  # pylint: disable=unused-argument
            # Return a dummy image that has a 'reduceRegions' method in get_image_collection
            return img

    return DummySensor()


@pytest.fixture
def _dummy_ee_manager(monkeypatch):
    """
    Monkeypatch ee_manager.get_image_collection to return a Fake FeatureCollection.
    whose getInfo() produces a known feature list.
    """

    # Create a fake FeatureCollection class
    class FakeFC:
        """Stub of an Earth Engine FeatureCollection for testing."""

        def __init__(self, features):
            self._features = features

        def map(self, func):  # pylint: disable=unused-argument
            return self

        def flatten(self):
            return self

        def getInfo(self):  # pylint: disable=invalid-name
            # Simulate EarthEngine getInfo output: list of features with properties
            return {
                "features": [
                    {"properties": {"id": 1, "date": "2020-01-01", "mean": 0.5}}
                ]
            }

    # Monkeypatch the ee_manager used in DataIngestor
    monkeypatch.setattr(
        "verdesat.ingestion.dataingestor.ee_manager.get_image_collection",
        lambda *args, **kwargs: FakeFC([None]),
    )
    return FakeFC


def test_download_timeseries_no_aggregation(dummy_aoi, dummy_sensor, _dummy_ee_manager):
    """
    Test that DataIngestor.download_timeseries returns a DataFrame with correct columns
    for one daily chunk, without aggregation (freq=None).
    """
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
    dummy_aoi, dummy_sensor, _dummy_ee_manager
):
    """
    Test that DataIngestor.download_timeseries with freq='M' returns a DataFrame
    resampled to monthly (here, single month so no change).
    """
    di = DataIngestor(sensor=dummy_sensor)
    df_agg = di.download_timeseries(
        dummy_aoi,
        start_date="2020-01-01",
        end_date="2020-01-31",
        scale=30,
        index="ndvi",
        chunk_freq="M",
        freq="M",
    )
    # With only a single value, monthly aggregation still yields one row
    assert isinstance(df_agg, pd.DataFrame)
    assert list(df_agg.columns) == ["id", "date", "mean_ndvi"]
    # Date should be the month‐start or aggregated index (since only one point).
    assert pd.to_datetime(df_agg.iloc[0]["date"]).month == 1
