# tests/test_aoi.py
import pytest
import json
from shapely.geometry import Polygon, mapping
import ee

from verdesat.geo.aoi import AOI


@pytest.fixture(autouse=True)
def ee_initialize(monkeypatch):
    """
    If your AOI class calls ee.* at import‐time or inside ee_geometry(), you
    may want to stub out EE initialization so the tests don’t actually hit the
    cloud. For example:
    """

    class DummyGeometry:
        def __init__(self, coords):
            self._coords = coords

        def getInfo(self):
            # Pretend getInfo() returns mapping form
            return {"type": "Polygon", "coordinates": self._coords}

    # Monkey‐patch ee.Geometry so that AOI.ee_geometry() does not call real EE.
    monkeypatch.setattr(
        ee, "Geometry", lambda geojson: DummyGeometry(geojson["coordinates"])
    )

    yield
    # (Optional: tear down or cleanup if needed)


def test_from_geojson_and_ee_geometry(tmp_path):
    # Create a tiny GeoJSON dict with one square
    square_coords = [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]
    gj = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": 42, "name": "TestSquare"},
                "geometry": {"type": "Polygon", "coordinates": square_coords},
            }
        ],
    }

    aois = AOI.from_geojson(gj, id_col="id")
    assert len(aois) == 1

    aoi = aois[0]
    # Ensure static_props captured correctly
    assert aoi.static_props["id"] == 42
    assert aoi.static_props["name"] == "TestSquare"

    # Test ee_geometry() returns something that has getInfo()
    ee_geom = aoi.ee_geometry()
    info = ee_geom.getInfo()
    assert info["type"] == "Polygon"

    # Shapely’s mapping() may return tuples whereas our GeoJSON sample uses lists.
    # Convert both coordinate nests to plain lists before comparison.
    def _as_lists(obj):
        if isinstance(obj, tuple):
            return [_as_lists(o) for o in obj]
        if isinstance(obj, list):
            return [_as_lists(o) for o in obj]
        return obj

    assert _as_lists(info["coordinates"]) == _as_lists(square_coords)


def test_buffered_ee_geometry(monkeypatch):
    # Create a simple Shapely polygon
    poly = Polygon([(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)])
    aoi = AOI(poly, static_props={"id": 1})

    # Monkey‐patch ee.Geometry.mapping so that eo.buffer() returns a dummy buffer
    class DummyGeom:
        def __init__(self, coords):
            self._coords = coords

        def buffer(self, meters):
            # Indicate buffer was applied by appending the buffer distance
            coords_list = list(self._coords)  # ensure mutable list
            coords_list.append([meters, meters])
            return DummyGeom(coords_list)

        def getInfo(self):
            return {"coords": self._coords}

    monkeypatch.setattr(
        ee, "Geometry", lambda geojson: DummyGeom(geojson["coordinates"])
    )

    # No buffer (zero) → same as ee_geometry()
    geom_no_buffer = aoi.buffered_ee_geometry(0)
    info_nb = geom_no_buffer.getInfo()
    # The coords field matches original Shapely coordinates via mapping()
    assert info_nb["coords"] == mapping(poly)["coordinates"]

    # With a positive buffer
    geom_buf = aoi.buffered_ee_geometry(100)
    info_b = geom_buf.getInfo()
    # Our DummyGeom just appended [100,100] to coords
    assert info_b["coords"][-1] == [100, 100]


def test_from_file_and_from_gdf(tmp_path, monkeypatch):
    # Create a tiny GeoJSON file on disk
    gj = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": 5},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [0, 1], [1, 0], [0, 0]]],
                },
            }
        ],
    }
    fp = tmp_path / "test.geojson"
    fp.write_text(json.dumps(gj))

    # from_file should delegate to from_geojson internally
    aois = AOI.from_file(str(fp), id_col="id")
    assert len(aois) == 1
    assert aois[0].static_props["id"] == 5
