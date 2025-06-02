import geopandas as gpd
import pytest
from shapely.geometry import Polygon
import zipfile
import json

import io
import os
import types
from unittest.mock import MagicMock

import pytest
import ee

from verdesat.ingestion.eemanager import EarthEngineManager


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
def dummy_img(monkeypatch):
    """
    A bare-minimum ee.Image stub that exposes getThumbURL/getDownloadURL and
    chainable select()/reduce()/rename()/set() so that AnalyticsEngine and
    ChipExporter don’t choke.
    """

    class _DummyImg:
        # constructor arg not used, but keeps interface parity
        def __init__(self, _id="dummy"):
            pass

        # ↓ Export-URL helpers (ChipExporter uses one or the other)
        def getThumbURL(self, _params):
            return "http://example.com/dummy.png"

        def getDownloadURL(self, _params):
            return "http://example.com/dummy.tif"

        # ↓ The following make AnalyticsEngine happy
        def select(self, *_a, **_kw):
            return self

        def reduce(self, _reducer):
            return self

        def rename(self, *_a):
            return self

        def set(self, *_a, **_kw):
            return self

    # Give ee.Image a constructor that returns _DummyImg
    monkeypatch.setattr(ee, "Image", _DummyImg, raising=False)
    return _DummyImg()


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
