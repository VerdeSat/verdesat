"""
Tests for EarthEngineManager: initialization and get_image_collection behavior.
"""

# pylint: disable=W0621,W0613

from unittest.mock import MagicMock

import pytest
import ee
from verdesat.ingestion.eemanager import EarthEngineManager, ee_manager
from verdesat.ingestion.sensorspec import SensorSpec


@pytest.fixture(autouse=True)
def mock_ee(monkeypatch):
    """
    Monkeypatch ee.Initialize, ee.ServiceAccountCredentials, and ee.ImageCollection.
    This ensures EarthEngineManager.initialize() and get_image_collection() can run 
    without real GEE.
    """
    # Stub any credential calls
    monkeypatch.setattr(ee, "Initialize", lambda *args, **kwargs: None)
    monkeypatch.setattr(ee, "ServiceAccountCredentials", lambda a, b: MagicMock())

    # Provide a dummy ImageCollection that supports .filterDate, .filterBounds, .map
    class DummyCollection:
        """
        Dummy ImageCollection stub that tracks .map() calls.
        """

        def __init__(self):
            self.mapped_with = None

        # pylint: disable=C0103  # filterDate not snake_case
        def filterDate(self, s, e):
            """Stub for ImageCollection.filterDate."""
            return self

        def filterBounds(self, region):
            """Stub for ImageCollection.filterBounds."""
            return self

        def map(self, func):
            """Record that .map() was called with the given function."""
            self.mapped_with = func
            return self

    monkeypatch.setattr(ee, "ImageCollection", lambda cid: DummyCollection())
    yield


@pytest.fixture
def dummy_sensor(monkeypatch):
    """
    Create a fake SensorSpec that simply returns the input image when applying cloud_mask.
    """

    class DummySensor:
        """Dummy sensor spec for testing cloud_mask invocation."""

        def __init__(self):
            self.collection_id = "dummy/collection"

        @staticmethod
        def cloud_mask(img):
            """Apply a no-op cloud mask."""
            return img  # No-op mask

    # Override SensorSpec.from_collection_id to return DummySensor
    monkeypatch.setattr(SensorSpec, "from_collection_id", lambda cid: DummySensor())
    return DummySensor()


def test_initialize_does_not_raise():
    """Ensure initialize() calls ee.Initialize() without error."""
    ee_manager.project = None
    ee_manager.credential_path = None
    # Should not raise any exceptions
    ee_manager.initialize()


def test_get_image_collection_applies_cloud_mask(monkeypatch, dummy_sensor):
    """Verify get_image_collection applies or skips cloud_mask correctly."""
    fake_region = MagicMock()
    mgr = EarthEngineManager()
    # Call with mask_clouds=True
    coll = mgr.get_image_collection(
        "dummy/collection", "2020-01-01", "2020-01-02", fake_region, mask_clouds=True
    )
    # The returned collection should be a DummyCollection
    assert hasattr(coll, "mapped_with")
    # Because we monkeypatched, SensorSpec.from_collection_id returns DummySensor,
    # so mgr.get_image_collection should call coll.map(DummySensor.cloud_mask)
    assert coll.mapped_with == dummy_sensor.cloud_mask

    # Calling with mask_clouds=False returns an un‐mapped collection
    mgr2 = EarthEngineManager()
    coll2 = mgr2.get_image_collection(
        "dummy/collection", "2020-01-01", "2020-01-02", fake_region, mask_clouds=False
    )
    # Since no .map call, mapped_with remains None
    assert coll2.mapped_with is None
