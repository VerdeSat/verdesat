"""
Tests for SensorSpec and index registry loading, and compute_index expression generation.
"""

# pylint: disable=W0621,W0613

import json
import importlib
import pytest

from verdesat.ingestion.indices import INDEX_REGISTRY
from verdesat.ingestion.sensorspec import SensorSpec

import verdesat.ingestion.sensorspec as ss_mod
import verdesat.ingestion.indices as idx_mod


@pytest.fixture
def temp_index_and_sensor_specs(tmp_path, monkeypatch):
    """Fixture to create temporary index and sensor spec JSON files and monkeypatch paths."""
    # 1. Create a minimal index_formulas.json
    index_data = {
        "ndvi": {
            "expr": "(NIR - RED) / (NIR + RED)",
            "bands": ["NIR", "RED"],
            "params": {},
        },
        "evi": {
            "expr": ("2.5 * ((NIR - RED) / " "(NIR + 6 * RED - 7.5 * BLUE + 1))"),
            "bands": [
                "NIR",
                "RED",
                "BLUE",
            ],
            "params": {},
        },
    }
    idx_file = tmp_path / "index_formulas.json"
    idx_file.write_text(json.dumps(index_data), encoding="utf-8")

    # 2. Create a minimal sensor_specs.json
    sensor_data = {
        "HLSL30": {
            "bands": {
                "NIR": "B5",
                "RED": "B4",
                "BLUE": "B2",
                "GREEN": "B3",
            },
            "collection_id": "NASA/HLS/HLSL30/v002",
            "cloud_mask": {"type": "fmask"},
        }
    }
    spec_file = tmp_path / "sensor_specs.json"
    spec_file.write_text(json.dumps(sensor_data), encoding="utf-8")

    # 3. Monkeypatch the resource file locations inside SensorSpec and indices modules
    monkeypatch.setenv("VERDESAT_INDEX_FORMULAS", str(idx_file))
    monkeypatch.setenv("VERDESAT_SENSOR_SPECS", str(spec_file))

    # Force a reload of SensorSpec so it picks up the monkeypatched paths
    importlib.reload(ss_mod)
    importlib.reload(idx_mod)

    yield

    # Cleanup: reload back if necessary (not strictly needed for pytest teardown)
    importlib.reload(ss_mod)
    importlib.reload(idx_mod)


# pylint: disable=W0613
def test_load_sensor_spec_and_index_registry(temp_index_and_sensor_specs):
    """Test that registry keys and sensor spec load correctly, and invalid index raises."""
    # Check registry keys
    assert "ndvi" in INDEX_REGISTRY
    assert "evi" in INDEX_REGISTRY

    # Load the sensor spec by collection id
    spec = SensorSpec.from_collection_id("NASA/HLS/HLSL30/v002")
    assert spec.collection_id == "NASA/HLS/HLSL30/v002"
    # Ensure band mapping loaded
    assert spec.bands["nir"] == "B5"
    assert spec.bands["red"] == "B4"

    # Test compute_index with invalid index name raises ValueError
    class DummyImage:
        """Dummy image class to simulate select method for testing."""

        def select(self, *args):
            """Return the first band argument as a placeholder."""
            return args[0]

    fake_img = DummyImage()
    with pytest.raises(ValueError):
        spec.compute_index(fake_img, "invalid_index")


# pylint: disable=W0613
def test_compute_index_expression(temp_index_and_sensor_specs, monkeypatch):
    """Test that compute_index builds correct expression and band mapping."""
    # Monkeypatch ee.Image.expression to record the expression and mapping
    recorded = {}

    class FakeImage:
        """Fake image class to simulate chainable select and expression methods."""

        def __init__(self):
            pass

        def select(self, *bands):
            """Return the FakeImage instance itself for chaining."""
            return self

        def expression(self, expr_str, band_mapping):
            """Record the expression call and return self."""
            recorded["expr"] = expr_str
            recorded["bands"] = band_mapping
            return self

        def rename(self, name):
            """Simulate ee.Image.rename."""
            return self

    fake_img = FakeImage()
    spec = SensorSpec.from_collection_id("NASA/HLS/HLSL30/v002")

    # Compute NDVI: should build mapping with keys "NIR" and "RED"
    out_img = spec.compute_index(fake_img, "ndvi")
    assert out_img is fake_img
    assert "(NIR - RED) / (NIR + RED)" in recorded["expr"]
    # Since select() returns fake_img, both aliases map to the same FakeImage
    assert recorded["bands"]["NIR"] is fake_img
    assert recorded["bands"]["RED"] is fake_img
