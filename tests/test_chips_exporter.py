# pylint: disable=protected-access,missing-docstring,unused-argument
from __future__ import annotations

from unittest.mock import MagicMock
import types
from types import SimpleNamespace

from verdesat.visualization.chips import ChipExporter


# -------------------------------------------------------------------
# 1) PNG-export path (getThumbURL -> PNG file written)
# -------------------------------------------------------------------
def test_export_one_thumbnail_png(tmp_export_dir, dummy_img, dummy_feat, monkeypatch):
    # ---- stub requests.get so we never hit the network -----------------
    class _FakeResp:
        status_code = 200
        content = b"PNGDATA"

        def raise_for_status(self):
            return None

    # Patch the `requests` module used inside ChipExporter
    monkeypatch.setattr(
        "verdesat.visualization.chips.requests",
        types.SimpleNamespace(get=lambda *_a, **_k: _FakeResp()),
        raising=False,
    )

    # Construct dummy AOI
    dummy_aoi = MagicMock()
    dummy_aoi.static_props = {"id": 1}
    dummy_geom = MagicMock()
    dummy_geom.bounds.return_value = MagicMock()
    dummy_aoi.buffered_ee_geometry.return_value = dummy_geom

    exporter = ChipExporter(
        ee_manager=MagicMock(), out_dir=str(tmp_export_dir), fmt="png"
    )

    exporter.ee_manager.safe_get_info.return_value = {
        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]
    }

    dest = exporter.export_one(
        img=dummy_img,
        aoi=dummy_aoi,
        date_str="2024-01-01",
        com_type="RGB",
        bands=["red"],
        palette=None,
        scale=30,
        buffer_m=0,
        gamma=None,
        min_val=0,
        max_val=1,
    )

    out_path = tmp_export_dir / "RGB_1_2024-01-01.png"
    assert dest == str(out_path)
    assert out_path.exists()
    assert out_path.read_bytes() == b"PNGDATA"


# -------------------------------------------------------------------
# 2) GeoTIFF export path + COG conversion triggered
# -------------------------------------------------------------------
def test_export_one_thumbnail_geotiff_cog(
    tmp_export_dir, dummy_img, dummy_feat, monkeypatch
):
    # ---- stub requests -------------------------------------------------
    class _FakeResp:
        status_code = 200
        content = b"TIFFDATA"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        "verdesat.visualization.chips.requests",
        types.SimpleNamespace(get=lambda *_a, **_k: _FakeResp()),
        raising=False,
    )

    # ---- stub rasterio so we do not need the library nor actual COG conversion ----
    fake_rasterio = MagicMock()
    ctx = fake_rasterio.open.return_value.__enter__.return_value
    ctx.read.return_value = b""
    ctx.profile = {}
    ctx.write = MagicMock()
    ctx.build_overviews = MagicMock()
    ctx.update_tags = MagicMock()

    # Patch inside the module under test, not just globals()
    monkeypatch.setattr(
        "verdesat.services.raster_utils.rasterio", fake_rasterio, raising=False
    )
    monkeypatch.setattr(
        "verdesat.services.raster_utils.Resampling",
        SimpleNamespace(nearest="nearest"),
        raising=False,
    )

    # Construct dummy AOI
    dummy_aoi = MagicMock()
    dummy_aoi.static_props = {"id": 1}
    dummy_geom = MagicMock()
    dummy_geom.bounds.return_value = MagicMock()
    dummy_aoi.buffered_ee_geometry.return_value = dummy_geom

    exporter = ChipExporter(
        ee_manager=MagicMock(), out_dir=str(tmp_export_dir), fmt="geotiff"
    )

    exporter.ee_manager.safe_get_info.return_value = {
        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]
    }

    dest = exporter.export_one(
        img=dummy_img,
        aoi=dummy_aoi,
        date_str="2024-01-01",
        com_type="NDVI",
        bands=["NDVI"],
        palette=None,
        scale=30,
        buffer_m=0,
        gamma=None,
        min_val=0,
        max_val=1,
    )

    out_path = tmp_export_dir / "NDVI_1_2024-01-01.tif"
    assert dest == str(out_path)
    assert out_path.exists()
    assert fake_rasterio.open.called


# -------------------------------------------------------------------
# 3) Palette + gamma exclusion logic
# -------------------------------------------------------------------
def test_palette_dropped_when_gamma(tmp_export_dir, monkeypatch):
    exporter = ChipExporter(
        ee_manager=MagicMock(), out_dir=str(tmp_export_dir), fmt="png"
    )

    params = exporter._build_viz_params(
        bands=["NDVI"],
        min_val=-1,
        max_val=1,
        scale=10,
        palette=["red", "green"],
        gamma=0.7,
    )
    # palette should *not* be present when gamma supplied
    assert "palette" not in params and params["gamma"] == [0.7]
