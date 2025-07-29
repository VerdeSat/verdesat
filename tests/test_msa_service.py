import numpy as np
from shapely.geometry import Polygon
import pytest
import rasterio
from rasterio.transform import from_origin

from verdesat.geo.aoi import AOI
from verdesat.services.msa import MSAService, EgressBudget
from verdesat.core.storage import LocalFS


def create_raster(path: str) -> None:
    data = np.array([[0.2, 0.4], [0.6, 0.8]], dtype=np.float32)
    transform = from_origin(0, 2, 1, 1)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=2,
        width=2,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(data, 1)


def test_mean_msa(tmp_path):
    raster_path = tmp_path / "msa.tif"
    create_raster(raster_path)
    aoi = AOI(Polygon([(0, 0), (0, 2), (2, 2), (2, 0)]), {"id": 1})
    svc = MSAService(storage=LocalFS(), budget_bytes=1000)
    mean_val = svc.mean_msa(aoi.geometry, dataset_uri=str(raster_path))
    assert abs(mean_val - 0.5) < 1e-6


def test_budget_exceeded(tmp_path):
    raster_path = tmp_path / "msa.tif"
    create_raster(raster_path)
    aoi = AOI(Polygon([(0, 0), (0, 2), (2, 2), (2, 0)]), {"id": 1})
    svc = MSAService(storage=LocalFS(), budget_bytes=8)
    with pytest.raises(RuntimeError):
        svc.mean_msa(aoi.geometry, dataset_uri=str(raster_path))
