# pylint: disable=protected-access,missing-docstring,unused-argument
from __future__ import annotations

import io
import os
from unittest.mock import MagicMock
import types

import pytest
import ee

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

    monkeypatch.setitem(
        globals(), "requests", types.SimpleNamespace(get=lambda *_a, **_k: _FakeResp())
    )

    exporter = ChipExporter(
        ee_manager=MagicMock(), out_dir=str(tmp_export_dir), fmt="png"
    )

    params = {"bands": ["red"], "min": 0, "max": 1, "dimensions": 512}
    exporter.export_one(
        dummy_img,
        dummy_feat,
        "2024-01-01",
        ["red"],
        params,
        str(tmp_export_dir),
        "RGB",
        "png",
    )

    out_path = tmp_export_dir / "RGB_1_2024-01-01.png"
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

    monkeypatch.setitem(
        globals(), "requests", types.SimpleNamespace(get=lambda *_a, **_k: _FakeResp())
    )

    # ---- stub rasterio so we do not need the library nor actual COG conversion ----
    fake_rasterio = MagicMock()
    fake_rasterio.open.return_value.__enter__.return_value.read.return_value = b""
    monkeypatch.setitem(globals(), "rasterio", fake_rasterio)

    exporter = ChipExporter(
        ee_manager=MagicMock(), out_dir=str(tmp_export_dir), fmt="geotiff"
    )

    exporter.export_one_thumbnail(
        dummy_img,
        dummy_feat,
        "2024-01-01",
        ["NDVI"],
        {"bands": ["NDVI"], "min": 0, "max": 1, "scale": 30, "format": "GEOTIFF"},
        str(tmp_export_dir),
        "NDVI",
        "geotiff",
    )

    out_path = tmp_export_dir / "NDVI_1_2024-01-01.tiff"
    assert out_path.exists()  # file written
    assert fake_rasterio.open.called  # COG conversion attempted


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


# -------------------------------------------------------------------
# 4) safe_get_info percentile helper path (uses EE stubs already)
# -------------------------------------------------------------------
def test_percentile_stretch_logic(monkeypatch):
    from verdesat.visualization.chips import _calc_percentile_stretch

    # Dummy image returns whatever .reduceRegion asks for
    dummy_img = MagicMock()
    dummy_img.reduceRegion.return_value = MagicMock()

    # EarthEngineManager.safe_get_info stub to return desired percentiles
    from verdesat.ingestion.eemanager import EarthEngineManager

    monkeypatch.setattr(
        EarthEngineManager,
        "safe_get_info",
        lambda self, obj, max_retries=3: {
            "NDVI_p2": -0.1,
            "NDVI_p98": 0.8,
        },
        raising=False,
    )

    lo, hi = _calc_percentile_stretch(
        dummy_img,
        features=[{"geometry": {"type": "Polygon", "coordinates": []}}],
        bands=["NDVI"],
        scale=10,
        low=2,
        high=98,
    )
    assert lo == -0.1 and hi == 0.8
