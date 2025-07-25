import numpy as np
from shapely.geometry import box
from types import SimpleNamespace
from unittest.mock import MagicMock

from verdesat.services.raster_utils import convert_to_cog
from verdesat.core.storage import LocalFS


def test_convert_to_cog_multiband(monkeypatch, tmp_path):
    # setup fake rasterio
    fake_rasterio = SimpleNamespace()
    ctx = MagicMock()
    fake_rasterio.open = MagicMock(
        return_value=MagicMock(
            __enter__=MagicMock(return_value=ctx), __exit__=MagicMock()
        )
    )
    ctx.profile = {"count": 3}
    ctx.crs = SimpleNamespace(to_string=lambda: "EPSG:4326")
    ctx.write = MagicMock()
    ctx.write_mask = MagicMock()
    ctx.build_overviews = MagicMock()
    ctx.update_tags = MagicMock()

    arr = np.ma.MaskedArray(
        data=np.ones((3, 2, 2), dtype=np.uint8),
        mask=np.zeros((3, 2, 2), dtype=bool),
    )
    fake_rasterio.mask = SimpleNamespace(mask=lambda *_a, **_k: (arr, "affine"))
    fake_rasterio.warp = SimpleNamespace(transform_geom=lambda *_a, **_k: {})

    monkeypatch.setattr(
        "verdesat.services.raster_utils.rasterio", fake_rasterio, raising=False
    )
    monkeypatch.setattr(
        "verdesat.services.raster_utils.Resampling",
        SimpleNamespace(nearest="nearest"),
        raising=False,
    )

    out = tmp_path / "test.tif"
    out.write_bytes(b"data")

    convert_to_cog(str(out), LocalFS(), geometry=box(0, 0, 1, 1))

    # ensure all bands written
    written = ctx.write.call_args[0][0]
    assert written.shape[0] == 3
    ctx.write_mask.assert_called()
