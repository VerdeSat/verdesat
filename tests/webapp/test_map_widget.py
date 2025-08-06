import numpy as np
import rasterio
from rasterio.transform import from_origin

from unittest.mock import patch

import geopandas as gpd
from shapely.geometry import Polygon

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


def test_display_map_persists_state():
    map_widget.st.session_state.clear()
    gdf = gpd.GeoDataFrame(
        {"geometry": [Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])]}, crs="EPSG:4326"
    )
    with patch("verdesat.webapp.components.map_widget.st_folium") as st_folium:
        st_folium.return_value = {"center": [0.5, 0.5], "zoom": 8}
        map_widget.display_map(gdf, {})
    assert map_widget.st.session_state["map_center"] == [0.5, 0.5]
    assert map_widget.st.session_state["map_zoom"] == 8
