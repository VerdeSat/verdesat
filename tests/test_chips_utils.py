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


@pytest.fixture(autouse=True)
def mock_ee(monkeypatch):
    """
    Monkeypatch ee.Initialize, ee.Date, ee.List.sequence, and ee.ImageCollection.fromImages
    so that build_composites can run without needing actual Earth Engine access.
    """
    # Stub ee.Initialize
    monkeypatch.setattr(ee, "Initialize", lambda *args, **kwargs: None)
    monkeypatch.setattr(ee, "ServiceAccountCredentials", lambda a, b: MagicMock())

    # Stub Reducer.mean() so tests can call it without EE initialization
    from ee import Reducer as _Reducer  # the module-level Reducer imported in tests

    monkeypatch.setattr(_Reducer, "mean", staticmethod(lambda: MagicMock()))

    # Stub ee.ImageCollection(...) constructor (used elsewhere)
    class DummyConstructorCollection:
        def __init__(self, cid):
            self.mapped_with = None

        def filterDate(self, s, e):
            return self

        def filterBounds(self, region):
            return self

        def map(self, func):
            self.mapped_with = func
            return self

    # Use DummyImageCollection for ee.ImageCollection
    class DummyImageCollection:
        def __init__(self, cid=None):
            self.mapped_with = None

        def filterDate(self, s, e):
            return self

        def filterBounds(self, region):
            return self

        def map(self, func):
            self.mapped_with = func
            return self

        def select(self, *args, **kwargs):
            """Stub for ImageCollection.select that returns self for chaining."""
            return self

        def reduce(self, reducer):
            """Stub for ImageCollection.reduce that returns self for chaining."""
            return self

        def rename(self, *args, **kwargs):
            """Stub for ImageCollection.rename that returns self for chaining."""
            return self

        def set(self, *args, **kwargs):
            """Stub for Image.set that returns self for chaining."""
            return self

        @staticmethod
        def fromImages(imgs):
            class DummyBuiltCollection:
                def __init__(self, images):
                    self._images = images

                def size(self):
                    class DummyNumberInner:
                        def __init__(self, n):
                            self.n = n

                        def getInfo(self_inner):
                            return self_inner.n

                    return DummyNumberInner(len(self._images))

                def toList(self, count):
                    return self._images

            return DummyBuiltCollection(imgs)

    monkeypatch.setattr(ee, "ImageCollection", DummyImageCollection)

    # Stub ee.Number with a minimal chainable dummy that supports .getInfo(), .floor(), .add(), and .subtract()
    class DummyNumber:
        """Minimal stub mimicking ee.Number used in AnalyticsEngine tests."""

        def __init__(self, value):
            self._value = value

        # emulating .getInfo() behaviour
        def getInfo(self):
            return self._value

        # chainable no‑ops for .floor() and .add()
        def floor(self):  # pylint: disable=invalid-name
            return self

        def add(self, _other):  # pylint: disable=invalid-name
            return self

        def subtract(self, _other):  # pylint: disable=invalid-name
            """
            Return a new DummyNumber for expressions like ee.Number(...).subtract(...).
            In tests we do not care about the actual arithmetic value, only that
            the call chain does not break, so we return `self`.
            """
            return self

    # Patch ee.Number to return our DummyNumber
    monkeypatch.setattr(ee, "Number", DummyNumber)

    # Stub ee.Date so that .get("year"), .get("month"), .millis(), .advance(), .difference() all return DummyNumbers
    class DummyDate:
        def __init__(self, date_str):
            self._date_str = date_str

        def get(self, key):
            # Return a DummyNumber for year/month/day if needed
            # (For our test, we’ll never inspect the actual number, so just pick a constant.)
            return ee.Number(1)

        @classmethod
        def fromYMD(cls, year, month, day):
            # Return another DummyDate (year/month not actually used)
            return DummyDate(f"{year}-{month}-{day}")

        def advance(self, offset, unit):
            # Return a new DummyDate (doesn’t really matter what string)
            return DummyDate("advanced")

        def difference(self, other, unit):
            # Return a DummyNumber (e.g. 3 periods)
            return ee.Number(3)

        def floor(self):
            return self

        def add(self, x):
            # return a DummyNumber or DummyDate as needed
            return ee.Number(3)

        def millis(self):
            # Return a DummyNumber for timestamp
            return ee.Number(0)

    monkeypatch.setattr(ee, "Date", DummyDate)

    # Stub ee.List.sequence so that .map(fn) directly applies fn to a Python list [0,1,2]
    class DummyList(list):
        def map(self, fn):
            # Return a plain Python list of whatever fn(item) returns
            return [fn(item) for item in self]

    monkeypatch.setattr(
        ee.List, "sequence", staticmethod(lambda start, end: DummyList([0, 1, 2]))
    )

    # Stub ee.ImageCollection.fromImages to simply wrap our Python list in a DummyCollection
    class DummyBuiltCollection:
        def __init__(self, images):
            self._images = images

        def size(self):
            # Return a dummy with getInfo() that returns length
            class DummyNumberInner:
                def __init__(self, n):
                    self.n = n

                def getInfo(self_inner):
                    return self_inner.n

            return DummyNumberInner(len(self._images))

        def toList(self, count):
            # Return the Python list itself (so .map(...) can iterate)
            return self._images

    monkeypatch.setattr(
        ee.ImageCollection,
        "fromImages",
        staticmethod(lambda imgs: DummyBuiltCollection(imgs)),
    )

    yield


# --------------------------------------------------------------------------------
# 3) Test build_viz_params
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
