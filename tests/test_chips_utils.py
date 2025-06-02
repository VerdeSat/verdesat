# tests/test_chips_utils.py

import pytest

import ee
from ee import Reducer

from verdesat.visualization.chips import ChipExporter
from verdesat.analytics.engine import AnalyticsEngine
from verdesat.ingestion.eemanager import EarthEngineManager

import tempfile
import os

from unittest.mock import MagicMock


# --------------------------------------------------------------------------------
# 1) Test build_viz_params
# --------------------------------------------------------------------------------


def test_build_viz_params_png_defaults():
    bands = ["red", "green", "blue"]
    min_val = 0.0
    max_val = 0.4
    scale = 30
    palette = None
    gamma = None
    fmt = "png"
    tmpdir = tempfile.mkdtemp()
    exporter = ChipExporter(EarthEngineManager(), out_dir=tmpdir, fmt=fmt)
    params = exporter._build_viz_params(bands, min_val, max_val, scale, palette, gamma)

    assert params["bands"] == bands
    assert params["min"] == min_val
    assert params["max"] == max_val
    # 'scale' is replaced by 'dimensions'
    assert "scale" not in params
    assert params["dimensions"] == 512
    assert "palette" not in params
    assert "gamma" not in params
    os.rmdir(tmpdir)


def test_build_viz_params_png_with_palette_and_gamma():
    bands = ["NDVI"]
    min_val = -1.0
    max_val = 1.0
    scale = 10
    palette = ["blue", "white", "green"]
    gamma = 0.8
    fmt = "png"
    tmpdir = tempfile.mkdtemp()
    exporter = ChipExporter(EarthEngineManager(), out_dir=tmpdir, fmt=fmt)
    params = exporter._build_viz_params(bands, min_val, max_val, scale, palette, gamma)

    assert params["bands"] == bands
    assert params["min"] == min_val
    assert params["max"] == max_val
    assert params["dimensions"] == 512
    # Since gamma is provided, palette must be dropped
    assert "palette" not in params
    assert params["gamma"] == [gamma] * len(bands)
    os.rmdir(tmpdir)


def test_build_viz_params_geotiff():
    bands = ["NDVI"]
    min_val = 0.0
    max_val = 1.0
    scale = 20
    palette = ["white", "green"]
    gamma = None
    fmt = "geotiff"
    tmpdir = tempfile.mkdtemp()
    exporter = ChipExporter(EarthEngineManager(), out_dir=tmpdir, fmt=fmt)
    params = exporter._build_viz_params(bands, min_val, max_val, scale, palette, gamma)

    assert params["bands"] == bands
    assert params["min"] == min_val
    assert params["max"] == max_val
    assert params["scale"] == scale
    assert params["format"] == "GEOTIFF"
    # No PNG-only keys for GeoTIFF
    assert "dimensions" not in params
    assert "palette" not in params
    os.rmdir(tmpdir)


# --------------------------------------------------------------------------------
# 4) Test AnalyticsEngine.build_composites
# --------------------------------------------------------------------------------


def test_build_composites_with_dummy_collection(monkeypatch):
    """
    With all of ee.Date, ee.List.sequence, and ee.ImageCollection.fromImages stubbed out above,
    AnalyticsEngine.build_composites(...) should now return a DummyBuiltCollection of size 3.
    """
    from verdesat.analytics.engine import AnalyticsEngine

    # Our dummy “AOI” is just an empty FeatureCollection
    fc = {"type": "FeatureCollection", "features": []}

    ae = AnalyticsEngine()
    composites = ae.build_composites(
        base_ic=ee.ImageCollection(
            "dummy"
        ),  # (in our stubs, _get_raw_collection is never called)
        period="M",
        reducer=Reducer.mean(),
        start="2020-01-01",
        end="2020-03-01",
        bands=["red", "green", "blue"],
        scale=30,
    )

    # Because we forced ee.List.sequence(0, end−start) to be [0,1,2],
    # the “fromImages” call will wrap that list into a DummyBuiltCollection of length 3.
    num = composites.size().getInfo()
    assert int(num) == 3


# --------------------------------------------------------------------------------
# 5) Test percentile stretch via EarthEngineManager.safe_get_info
# --------------------------------------------------------------------------------


def test_safe_get_info_retries(monkeypatch):
    """
    Verify that safe_get_info retries on generic EEException and returns
    the underlying dict when successful.
    """

    eem = EarthEngineManager()

    class FakeObj:
        def __init__(self, to_return, fail_times):
            self._to_return = to_return
            self._fail_times = fail_times
            self._count = 0

        def getInfo(self):
            self._count += 1
            if self._count <= self._fail_times:
                raise ee.EEException("TRANSIENT_ERROR")
            return self._to_return

    fake = FakeObj({"key": 123}, fail_times=2)

    # This should retry twice, then succeed
    result = eem.safe_get_info(fake, max_retries=3)
    assert result == {"key": 123}

    # If it fails too many times, it should re-raise
    fake_fail = FakeObj(None, fail_times=3)
    with pytest.raises(ee.EEException):
        eem.safe_get_info(fake_fail, max_retries=2)
