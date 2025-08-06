import numpy as np
import rasterio
from rasterio.transform import from_origin

from verdesat.webapp.components import map_widget
import streamlit as st


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


def _clear_state() -> None:
    for k in list(st.session_state.keys()):
        del st.session_state[k]


def test_display_map_uses_constant_key(monkeypatch):
    """Ensure map renders without triggering reruns."""
    from shapely.geometry import Polygon
    import geopandas as gpd

    gdf = gpd.GeoDataFrame(
        {"geometry": [Polygon([(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)])]},
        crs="EPSG:4326",
    )

    _clear_state()
    called_kwargs = {}

    def fake_st_folium(*args, **kwargs):
        called_kwargs.update(kwargs)
        return {"center": [0.5, 0.5], "zoom": 10}

    monkeypatch.setattr(map_widget, "st_folium", fake_st_folium)
    map_widget.display_map(gdf, {})

    assert called_kwargs["key"] == "main_map"
    assert called_kwargs["returned_objects"] == []
    assert st.session_state["main_map_center"] == [0.5, 0.5]
    assert st.session_state["main_map_zoom"] == 10


def test_display_map_saves_view(monkeypatch):
    from shapely.geometry import Polygon
    import geopandas as gpd

    gdf = gpd.GeoDataFrame(
        {"geometry": [Polygon([(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)])]},
        crs="EPSG:4326",
    )

    _clear_state()

    def fake_st_folium(*args, **kwargs):
        return {"center": [1.0, 2.0], "zoom": 7}

    monkeypatch.setattr(map_widget, "st_folium", fake_st_folium)
    map_widget.display_map(gdf, {})

    assert st.session_state["main_map_center"] == [1.0, 2.0]
    assert st.session_state["main_map_zoom"] == 7
