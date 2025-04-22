import geopandas as gpd
import pytest
from shapely.geometry import Polygon
import zipfile
import json


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
