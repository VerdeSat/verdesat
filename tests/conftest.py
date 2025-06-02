# pylint: disable=missing-module-docstring,missing-function-docstring,invalid-name,unused-argument,redefined-outer-name
import zipfile
import json

from unittest.mock import MagicMock

import pytest
from shapely.geometry import Polygon
import geopandas as gpd
import ee
from verdesat.geo.aoi import AOI
from verdesat.ingestion.sensorspec import SensorSpec


@pytest.fixture
def tmp_export_dir(tmp_path):
    """Temp directory where chips will be written."""
    d = tmp_path / "chips"
    d.mkdir()
    return d


@pytest.fixture
def dummy_feat():
    """Very small square polygon with id=1 (used by exporter)."""
    return {
        "type": "Feature",
        "properties": {"id": 1},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[0, 0], [0, 0.001], [0.001, 0.001], [0.001, 0], [0, 0]]],
        },
    }


@pytest.fixture
def dummy_img():
    # Dummy ee.Image-like object
    class _DummyImg:
        def getInfo(self):
            return {"bands": [{"id": "red"}, {"id": "green"}]}

        def select(self, _bands):
            return self

        def getMapId(self, _params):
            return {"tile_fetcher": MagicMock()}

        def clip(self, _geom):
            return self

        # ChipExporter calls .clip(); return self so the chain continues

        def getThumbURL(self, _params):
            # ChipExporter uses this for PNG exports
            return "http://example.com/dummy.png"

        def getDownloadURL(self, _params):
            # ChipExporter uses this for GeoTIFF exports
            return "http://example.com/dummy.tif"

    # Give ee.Image a constructor that returns _DummyImg
    ee.Image = lambda *args, **kwargs: _DummyImg()
    return _DummyImg()


# pylint: disable=protected-access,missing-docstring,unused-argument


@pytest.fixture
def sample_shapefile(tmp_path):
    """Create a simple shapefile with one square polygon."""
    gdf = gpd.GeoDataFrame(
        {"id": [1], "geometry": [Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])]},
        crs="EPSG:4326",
    )
    shp_dir = tmp_path / "test_shapefile"
    shp_dir.mkdir()
    gdf.to_file(shp_dir / "test.shp")
    return shp_dir


@pytest.fixture
def sample_kml(tmp_path):
    """Create a minimal KML file."""
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Placemark>
    <name>Sample</name>
    <Polygon>
      <outerBoundaryIs>
        <LinearRing>
          <coordinates>
            0,0,0 0,1,0 1,1,0 1,0,0 0,0,0
          </coordinates>
        </LinearRing>
      </outerBoundaryIs>
    </Polygon>
  </Placemark>
</kml>"""
    kml_path = tmp_path / "sample.kml"
    kml_path.write_text(kml_content)
    return tmp_path


@pytest.fixture
def sample_kmz(tmp_path, sample_kml):
    """Create a KMZ file containing the KML."""
    kml_path = sample_kml / "sample.kml"
    kmz_path = tmp_path / "sample.kmz"
    with zipfile.ZipFile(kmz_path, "w") as zf:
        zf.write(kml_path, arcname="doc.kml")
    return tmp_path


@pytest.fixture
def invalid_geojson(tmp_path):
    """Create a GeoJSON file with an invalid geometry."""
    bad_geom = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 1], [1, 0]]],  # Not closed
                },
                "properties": {"id": 1},
            }
        ],
    }
    geojson_path = tmp_path / "bad.geojson"
    geojson_path.write_text(json.dumps(bad_geom))
    return tmp_path


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


@pytest.fixture
def dummy_aoi():
    """
    Create a dummy AOI with a simple square Polygon and an 'id' in static_props.
    """
    geom = Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])
    return AOI(geometry=geom, static_props={"id": 1})


@pytest.fixture
def dummy_sensor(monkeypatch):
    """
    Create a fake SensorSpec that simply returns the input image when applying cloud_mask.
    """

    class DummySensor:
        """Dummy sensor spec for testing cloud_mask invocation."""

        def __init__(self):
            self.collection_id = "dummy/collection"

        @staticmethod  # noqa: D401
        def compute_index(img, index):  # pylint: disable=unused-argument
            # Return a dummy image that has a 'reduceRegions' method in get_image_collection
            return img

        @staticmethod
        def cloud_mask(img):
            """Apply a no-op cloud mask."""
            return img  # No-op mask

    # Override SensorSpec.from_collection_id to return DummySensor
    monkeypatch.setattr(SensorSpec, "from_collection_id", lambda cid: DummySensor())
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
