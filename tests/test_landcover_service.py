from pathlib import Path
from unittest.mock import MagicMock

from verdesat.services.landcover import LandcoverService
from verdesat.core.logger import Logger


def _dummy_image(url: str):
    class Img:
        def remap(self, *_a):
            return self

        def clip(self, _g):
            return self

        def getDownloadURL(self, _p):
            return url

    return Img()


def _setup(monkeypatch, svc, calls, stub_bytes):
    monkeypatch.setattr(
        svc,
        "_esri_image",
        lambda year: (calls.setdefault("esri", year), _dummy_image("http://x"))[1],
    )
    monkeypatch.setattr(
        svc,
        "_worldcover_image",
        lambda: (calls.setdefault("wc", True), _dummy_image("http://x"))[1],
    )

    class Resp:
        def __init__(self, data: bytes):
            self.content = data

        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        "verdesat.services.landcover.requests.get",
        lambda url, timeout: Resp(stub_bytes),
    )
    monkeypatch.setattr("verdesat.services.landcover.ee.List", list)


def test_download_selects_esri(monkeypatch, tmp_path, dummy_aoi):
    calls: dict = {}
    svc = LandcoverService(logger=Logger.get_logger("test"))
    stub = Path("tests/fixtures/stub_lc.tif").read_bytes()
    _setup(monkeypatch, svc, calls, stub)
    monkeypatch.setattr(dummy_aoi, "buffered_ee_geometry", lambda x: MagicMock())

    out = svc.download(dummy_aoi, 2018, str(tmp_path))
    assert calls.get("esri") == 2018
    assert Path(out).read_bytes() == stub


def test_download_fallback_worldcover(monkeypatch, tmp_path, dummy_aoi):
    calls: dict = {}
    svc = LandcoverService(logger=Logger.get_logger("test"))
    stub = Path("tests/fixtures/stub_lc.tif").read_bytes()
    _setup(monkeypatch, svc, calls, stub)
    monkeypatch.setattr(dummy_aoi, "buffered_ee_geometry", lambda x: MagicMock())

    out = svc.download(dummy_aoi, 2015, str(tmp_path))
    assert calls.get("wc") is True
    assert Path(out).read_bytes() == stub
