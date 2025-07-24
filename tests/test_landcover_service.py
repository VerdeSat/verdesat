from unittest.mock import MagicMock
from types import SimpleNamespace

import pytest

from verdesat.services.landcover import LandcoverService


def test_dataset_choice_esri(monkeypatch, dummy_aoi):
    called = {}

    class DummyImg:
        def remap(self, keys, vals):
            called["keys"] = keys
            called["vals"] = vals
            return self

        def rename(self, *a, **k):
            return self

        def clip(self, *a, **k):
            return self

    def fake_image(img_id):
        called["id"] = img_id
        return DummyImg()

    monkeypatch.setattr("verdesat.services.landcover.ee.Image", fake_image)
    monkeypatch.setattr("verdesat.geo.aoi.AOI.ee_geometry", lambda self: "geom")

    mgr = MagicMock()
    svc = LandcoverService(ee_manager_instance=mgr)
    svc.get_image(dummy_aoi, 2019)

    assert LandcoverService.ESRI_COLLECTION in called["id"]
    assert mgr.initialize.called


def test_dataset_fallback(monkeypatch, dummy_aoi):
    called = {}

    class DummyImg:
        def remap(self, keys, vals):
            called["keys"] = keys
            called["vals"] = vals
            return self

        def rename(self, *a, **k):
            return self

        def clip(self, *a, **k):
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


def test_download_writes_file(tmp_path, monkeypatch, dummy_aoi):
    class DummyImg:
        def remap(self, *a, **k):
            return self

        def rename(self, *a, **k):
            return self

        def clip(self, *a, **k):
            return self

        def getDownloadURL(self, _p):
            return "http://example.com/lc.tif"

    monkeypatch.setattr(
        "verdesat.services.landcover.ee.Image", lambda *_a, **_k: DummyImg()
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
