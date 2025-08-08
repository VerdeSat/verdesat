from unittest.mock import MagicMock
from types import SimpleNamespace
import numpy as np

import ee

import pytest

from verdesat.services.landcover import LandcoverService
from verdesat.core.storage import LocalFS


def test_dataset_choice_esri(monkeypatch, dummy_aoi):
    called = {}

    class DummyCollection:
        def __init__(self, cid):
            called["cid"] = cid

        def filterDate(self, start, end):
            called["start"] = start
            called["end"] = end
            return self

        def mosaic(self):
            return self

        def remap(self, keys, vals):
            called["keys"] = keys
            called["vals"] = vals
            return self

        def unmask(self, val):
            called["unmask"] = val
            return self

        def rename(self, *_a, **_k):
            return self

        def clip(self, *_a, **_k):
            return self

    monkeypatch.setattr(
        "verdesat.services.landcover.ee.ImageCollection",
        lambda cid: DummyCollection(cid),
    )
    dummy_geom = SimpleNamespace()
    monkeypatch.setattr(
        "verdesat.geo.aoi.AOI.ee_geometry",
        lambda self: dummy_geom,
    )

    mgr = MagicMock()
    svc = LandcoverService(ee_manager_instance=mgr)
    svc.get_image(dummy_aoi, 2019)

    assert called["cid"] == LandcoverService.ESRI_COLLECTION
    assert list(called["keys"]) == list(LandcoverService.ESRI_CLASS_MAP_6.keys())
    assert list(called["vals"]) == list(LandcoverService.ESRI_CLASS_MAP_6.values())
    assert called["unmask"] == 0
    assert mgr.initialize.called


def test_dataset_fallback(monkeypatch, dummy_aoi):
    called = {}

    class DummyImg:
        def remap(self, keys, vals):
            called["keys"] = keys
            called["vals"] = vals
            return self

        def unmask(self, val):
            called["unmask"] = val
            return self

        def rename(self, *_a, **_k):
            return self

        def clip(self, *_a, **_k):
            return self

    def fake_image(img_id):
        called["id"] = img_id
        return DummyImg()

    monkeypatch.setattr("verdesat.services.landcover.ee.Image", fake_image)
    dummy_geom = SimpleNamespace()
    monkeypatch.setattr("verdesat.geo.aoi.AOI.ee_geometry", lambda self: dummy_geom)

    svc = LandcoverService(ee_manager_instance=MagicMock())
    svc.get_image(dummy_aoi, LandcoverService.LATEST_ESRI_YEAR + 2)

    assert called["id"] == LandcoverService.WORLD_COVER
    assert called["keys"] == list(LandcoverService.WORLD_COVER_CLASS_MAP_6.keys())
    assert called["vals"] == list(LandcoverService.WORLD_COVER_CLASS_MAP_6.values())
    assert called["unmask"] == 0


def test_download_writes_file(tmp_path, monkeypatch, dummy_aoi):
    captured = {}

    class DummyImg:
        def remap(self, *a, **k):
            return self

        def unmask(self, _val):
            return self

        def rename(self, *a, **k):
            return self

        def clip(self, *a, **k):
            return self

        def getDownloadURL(self, params):
            captured["region"] = params.get("region")
            return "http://example.com/lc.tif"

    def fake_get_image(self, *_a, **_k):
        self.ee_manager.initialize()
        return DummyImg()

    monkeypatch.setattr(
        "verdesat.services.landcover.LandcoverService.get_image",
        fake_get_image,
    )
    dummy_geom = SimpleNamespace()
    monkeypatch.setattr("verdesat.geo.aoi.AOI.ee_geometry", lambda self: dummy_geom)

    class FakeResp:
        content = b"DATA"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        "verdesat.services.landcover.requests",
        SimpleNamespace(get=lambda *_a, **_k: FakeResp()),
        raising=False,
    )

    fake_rasterio = SimpleNamespace()
    ctx = MagicMock()
    fake_rasterio.open = MagicMock(
        return_value=MagicMock(
            __enter__=MagicMock(return_value=ctx), __exit__=MagicMock()
        )
    )
    ctx.profile = {}
    ctx.crs = SimpleNamespace(to_string=lambda: "EPSG:3857")
    ctx.write = MagicMock()
    ctx.write_mask = MagicMock()
    ctx.build_overviews = MagicMock()
    ctx.update_tags = MagicMock()

    def fake_mask(ds, shapes, *a, **k):
        captured["shapes"] = shapes
        return np.ma.MaskedArray(data=[[[1]]], mask=[[[False]]]), "affine"

    fake_rasterio.mask = SimpleNamespace(mask=fake_mask)
    fake_rasterio.warp = SimpleNamespace(
        transform_geom=lambda *_a, **_k: {"geom": True}
    )
    monkeypatch.setattr(
        "verdesat.services.raster_utils.rasterio", fake_rasterio, raising=False
    )
    monkeypatch.setattr(
        "verdesat.services.raster_utils.Resampling",
        SimpleNamespace(nearest="nearest"),
        raising=False,
    )

    class SpyLocalFS(LocalFS):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[tuple[str, bytes]] = []

        def write_bytes(self, uri: str, data: bytes) -> str:  # type: ignore[override]
            self.calls.append((uri, data))
            return super().write_bytes(uri, data)

    mgr = MagicMock()
    storage = SpyLocalFS()
    svc = LandcoverService(ee_manager_instance=mgr, storage=storage)
    svc.download(dummy_aoi, 2021, str(tmp_path))

    out = tmp_path / "LANDCOVER_1_2021.tif"
    assert storage.calls and storage.calls[0][0] == str(out)
    assert storage.calls[0][1] == b"DATA"
    assert out.exists() and out.read_bytes() == b"DATA"
    assert mgr.initialize.called
    assert captured["region"] is dummy_geom
    assert captured["shapes"][0] == {"geom": True}


def test_download_fallback_on_missing_asset(tmp_path, monkeypatch, dummy_aoi):
    years = []

    class ImgMissing:
        def remap(self, *a, **k):
            return self

        def unmask(self, _val):
            return self

        def rename(self, *a, **k):
            return self

        def clip(self, *a, **k):
            return self

        def getDownloadURL(self, _p):
            raise ee.ee_exception.EEException("not found")

    class ImgGood(ImgMissing):
        def getDownloadURL(self, _p):
            return "http://example.com/lc.tif"

    imgs = [ImgMissing(), ImgGood()]

    def fake_get_image(self, _aoi, year):
        years.append(year)
        return imgs.pop(0)

    monkeypatch.setattr(
        "verdesat.services.landcover.LandcoverService.get_image", fake_get_image
    )
    dummy_geom = SimpleNamespace()
    monkeypatch.setattr("verdesat.geo.aoi.AOI.ee_geometry", lambda self: dummy_geom)

    class FakeResp:
        content = b"X"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        "verdesat.services.landcover.requests",
        SimpleNamespace(get=lambda *_a, **_k: FakeResp()),
        raising=False,
    )

    fake_rasterio = SimpleNamespace()
    ctx = MagicMock()
    fake_rasterio.open = MagicMock(
        return_value=MagicMock(
            __enter__=MagicMock(return_value=ctx), __exit__=MagicMock()
        )
    )
    ctx.profile = {}
    ctx.crs = SimpleNamespace(to_string=lambda: "EPSG:3857")
    ctx.write_mask = MagicMock()
    ctx.build_overviews = MagicMock()
    ctx.update_tags = MagicMock()
    captured = {}

    def fake_mask(ds, shapes, *a, **k):
        captured["shapes"] = shapes
        return np.ma.MaskedArray(data=[[[1]]], mask=[[[False]]]), "affine"

    fake_rasterio.mask = SimpleNamespace(mask=fake_mask)
    fake_rasterio.warp = SimpleNamespace(
        transform_geom=lambda *_a, **_k: {"geom": True}
    )
    monkeypatch.setattr(
        "verdesat.services.raster_utils.rasterio", fake_rasterio, raising=False
    )
    monkeypatch.setattr(
        "verdesat.services.raster_utils.Resampling",
        SimpleNamespace(nearest="nearest"),
        raising=False,
    )

    class SpyLocalFS(LocalFS):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[tuple[str, bytes]] = []

        def write_bytes(self, uri: str, data: bytes) -> str:  # type: ignore[override]
            self.calls.append((uri, data))
            return super().write_bytes(uri, data)

    mgr2 = MagicMock()
    storage = SpyLocalFS()
    svc = LandcoverService(ee_manager_instance=mgr2, storage=storage)
    svc.download(dummy_aoi, LandcoverService.LATEST_ESRI_YEAR, str(tmp_path))

    out = tmp_path / f"LANDCOVER_1_{LandcoverService.LATEST_ESRI_YEAR}.tif"
    assert storage.calls and storage.calls[0][0] == str(out)
    assert years[0] == LandcoverService.LATEST_ESRI_YEAR
    assert years[1] > LandcoverService.LATEST_ESRI_YEAR
    assert out.exists() and out.read_bytes() == b"X"
    assert captured["shapes"][0] == {"geom": True}


def test_download_sanitizes_aoi_id(tmp_path, monkeypatch):
    dummy_img = MagicMock()
    dummy_img.getDownloadURL.return_value = "http://example.com/lc.tif"

    monkeypatch.setattr(
        LandcoverService, "get_image", lambda self, *_a, **_k: dummy_img
    )

    class FakeResp:
        content = b"X"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        "verdesat.services.landcover.requests",
        SimpleNamespace(get=lambda *_a, **_k: FakeResp()),
        raising=False,
    )
    monkeypatch.setattr(
        "verdesat.services.landcover.convert_to_cog",
        lambda *_a, **_k: None,
    )

    dummy_aoi = MagicMock()
    dummy_aoi.static_props = {"id": "../evil"}
    dummy_aoi.ee_geometry.return_value = MagicMock()
    dummy_aoi.geometry = MagicMock()

    svc = LandcoverService(ee_manager_instance=MagicMock(), storage=LocalFS())
    dest = svc.download(dummy_aoi, 2020, str(tmp_path))

    out = tmp_path / "LANDCOVER_evil_2020.tif"
    assert dest == str(out)
    assert out.exists()
