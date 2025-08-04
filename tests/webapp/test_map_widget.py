import numpy as np
import geopandas as gpd
import rasterio
from shapely.geometry import Polygon
from rasterio.transform import from_origin

from verdesat.webapp.components import map_widget


def test_local_overlay(tmp_path):
    path = tmp_path / "test.tif"
    data = np.array([[0.1, 0.2], [0.3, 0.4]], dtype="float32")
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=2,
        width=2,
        count=1,
        dtype="float32",
        transform=from_origin(0, 2, 1, 1),
        crs="EPSG:4326",
    ) as dst:
        dst.write(data, 1)

    overlay = map_widget._local_overlay(str(path))
    assert overlay.url.startswith("data:image/png;base64,")
    assert overlay.bounds == [[0.0, 0.0], [2.0, 2.0]]


def test_resolve_cog_path_relative():
    rel = "resources/NDVI_1_2024-01-01.tif"
    resolved = map_widget._resolve_cog_path(rel)
    assert resolved is not None
    assert resolved.exists()


def test_display_map_three_layers(monkeypatch, tmp_path):
    poly = Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])
    gdf = gpd.GeoDataFrame({"id": [1], "geometry": [poly]}, crs="EPSG:4326")

    data = np.array([[0.1, 0.2], [0.3, 0.4]], dtype="float32")
    ndvi_path = tmp_path / "ndvi.tif"
    msavi_path = tmp_path / "msavi.tif"
    for path in (ndvi_path, msavi_path):
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=2,
            width=2,
            count=1,
            dtype="float32",
            transform=from_origin(0, 2, 1, 1),
            crs="EPSG:4326",
        ) as dst:
            dst.write(data, 1)

    rasters = {
        "1": {"ndvi": str(ndvi_path), "msavi": str(msavi_path)},
        "2": {"ndvi": str(ndvi_path), "msavi": str(msavi_path)},
    }

    class DummySt:
        def __init__(self):
            self.session_state = {}

    dummy_st = DummySt()
    monkeypatch.setattr(map_widget, "st", dummy_st)
    monkeypatch.setattr(map_widget, "st_folium", lambda *a, **k: {})

    map_widget.display_map(gdf, rasters)
    m = dummy_st.session_state["map_obj"]
    expected = {"AOI Boundaries", "NDVI 2024", "MSAVI 2024"}
    layer_names = [
        child.layer_name
        for child in m._children.values()
        if getattr(child, "layer_name", None) in expected
    ]
    assert len(layer_names) == 3
    for name in expected:
        assert layer_names.count(name) == 1
