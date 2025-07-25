from unittest.mock import MagicMock
from types import SimpleNamespace

import ee

import pytest

from verdesat.services.landcover import LandcoverService


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
    monkeypatch.setattr("verdesat.geo.aoi.AOI.ee_geometry", lambda self: "geom")

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
    monkeypatch.setattr("verdesat.geo.aoi.AOI.ee_geometry", lambda self: "geom")

    svc = LandcoverService(ee_manager_instance=MagicMock())
    svc.get_image(dummy_aoi, LandcoverService.LATEST_ESRI_YEAR + 2)

    assert called["id"] == LandcoverService.WORLD_COVER
    assert called["keys"] == list(LandcoverService.WORLD_COVER_CLASS_MAP_6.keys())
    assert called["vals"] == list(LandcoverService.WORLD_COVER_CLASS_MAP_6.values())
    assert called["unmask"] == 0


def test_download_writes_file(tmp_path, monkeypatch, dummy_aoi):
    class DummyImg:
        def remap(self, *a, **k):
            return self

        def unmask(self, _val):
            return self

        def rename(self, *a, **k):
            return self

        def clip(self, *a, **k):
            return self

        def getDownloadURL(self, _p):
            return "http://example.com/lc.tif"

    def fake_get_image(self, *_a, **_k):
        self.ee_manager.initialize()
        return DummyImg()

    monkeypatch.setattr(
        "verdesat.services.landcover.LandcoverService.get_image",
        fake_get_image,
    )
    monkeypatch.setattr("verdesat.geo.aoi.AOI.ee_geometry", lambda self: "geom")

    class FakeResp:
        content = b"DATA"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        "verdesat.services.landcover.requests",
        SimpleNamespace(get=lambda *_a, **_k: FakeResp()),
        raising=False,
    )

    fake_rasterio = MagicMock()
    ctx = fake_rasterio.open.return_value.__enter__.return_value
    ctx.read.return_value = b""
    ctx.profile = {}
    ctx.write = MagicMock()
    ctx.build_overviews = MagicMock()
    ctx.update_tags = MagicMock()
    monkeypatch.setattr(
        "verdesat.services.landcover.rasterio", fake_rasterio, raising=False
    )
    monkeypatch.setattr(
        "verdesat.services.landcover.Resampling",
        SimpleNamespace(nearest="nearest"),
        raising=False,
    )

    mgr = MagicMock()
    svc = LandcoverService(ee_manager_instance=mgr)
    svc.download(dummy_aoi, 2021, str(tmp_path))

    out = tmp_path / "LANDCOVER_1_2021.tiff"
    assert out.exists() and out.read_bytes() == b"DATA"
    assert mgr.initialize.called


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
    monkeypatch.setattr("verdesat.geo.aoi.AOI.ee_geometry", lambda self: "geom")

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
        "verdesat.services.landcover.rasterio", MagicMock(), raising=False
    )
    monkeypatch.setattr(
        "verdesat.services.landcover.Resampling",
        SimpleNamespace(nearest="nearest"),
        raising=False,
    )

    svc = LandcoverService(ee_manager_instance=MagicMock())
    svc.download(dummy_aoi, LandcoverService.LATEST_ESRI_YEAR, str(tmp_path))

    assert years[0] == LandcoverService.LATEST_ESRI_YEAR
    assert years[1] > LandcoverService.LATEST_ESRI_YEAR
