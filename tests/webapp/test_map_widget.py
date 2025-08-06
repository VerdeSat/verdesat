import numpy as np
import geopandas as gpd
import rasterio
import streamlit as st
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


def test_display_map_persists_view(monkeypatch):
    gdf = gpd.GeoDataFrame(
        {"geometry": [Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])]},
        crs="EPSG:4326",
    )

    # First call: store returned state
    def fake_st_folium(_m, **_kwargs):
        return {"center": [0.2, 0.3], "zoom": 5}

    monkeypatch.setattr(map_widget, "st_folium", fake_st_folium)
    st.session_state.clear()
    map_widget.display_map(gdf, {})
    assert st.session_state["map_center"] == [0.2, 0.3]
    assert st.session_state["map_zoom"] == 5

    # Subsequent call should reuse stored zoom
    recorded: dict[str, float | None] = {}

    def fake_st_folium2(m, **_kwargs):
        recorded["zoom_used"] = m.options.get("zoom")
        return {"center": [0.4, 0.5], "zoom": 7}

    monkeypatch.setattr(map_widget, "st_folium", fake_st_folium2)
    map_widget.display_map(gdf, {})
    assert recorded["zoom_used"] == 5
    assert st.session_state["map_center"] == [0.4, 0.5]
    assert st.session_state["map_zoom"] == 7
