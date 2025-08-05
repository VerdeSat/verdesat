import numpy as np
import rasterio
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
