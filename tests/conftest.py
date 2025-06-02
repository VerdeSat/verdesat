# pylint: disable=missing-module-docstring,missing-function-docstring,invalid-name,unused-argument,redefined-outer-name
import zipfile
import json

from unittest.mock import MagicMock

import pytest
from shapely.geometry import Polygon
import geopandas as gpd
import ee


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
