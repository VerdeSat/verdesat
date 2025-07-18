"""
Tests for EarthEngineManager: initialization and get_image_collection behavior.
"""

# pylint: disable=W0621,W0613

from unittest.mock import MagicMock

from verdesat.ingestion.eemanager import EarthEngineManager, ee_manager


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
