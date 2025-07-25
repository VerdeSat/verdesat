from __future__ import annotations

"""Utility helpers for raster operations."""

from typing import Optional
import logging
from shapely.geometry.base import BaseGeometry
from shapely.geometry import mapping

try:
    import rasterio
    from rasterio.enums import Resampling
    import rasterio.mask
    import rasterio.warp
except ImportError:  # pragma: no cover - optional
    rasterio = None
    Resampling = None

from verdesat.core.storage import StorageAdapter, LocalFS


def convert_to_cog(
    path: str,
    storage: StorageAdapter,
    geometry: Optional[BaseGeometry] = None,
    logger: Optional[logging.Logger] = None,
) -> None:
    """Convert *path* GeoTIFF to Cloud Optimized GeoTIFF.

    If ``geometry`` is provided, clip the raster to that polygon. Conversion is
    skipped when rasterio is missing or when ``storage`` is not ``LocalFS``.
    """
    logger = logger or logging.getLogger(__name__)
    if not isinstance(storage, LocalFS):
        logger.warning("COG conversion skipped for non-local storage: %s", path)
        return

    if rasterio is None or Resampling is None:
        logger.warning("rasterio not installed; skipping COG conversion for %s", path)
        return

    try:
        with rasterio.open(path) as src:
            profile = src.profile
            if geometry is not None:
                geom_json = mapping(geometry)
                if src.crs and src.crs.to_string() != "EPSG:4326":
                    geom_json = rasterio.warp.transform_geom(
                        "EPSG:4326", src.crs.to_string(), geom_json
                    )
                arr, transform = rasterio.mask.mask(
                    src, [geom_json], crop=True, filled=False
                )
                profile.update(
                    nodata=0,
                    height=arr.shape[1],
                    width=arr.shape[2],
                    transform=transform,
                )
            else:
                arr = src.read()

        profile.update(
            driver="GTiff",
            compress="deflate",
            tiled=True,
            blockxsize=512,
            blockysize=512,
            count=arr.shape[0],
        )

        with rasterio.open(path, "w", **profile) as dst:
            data = arr.filled(0)
            dst.write(data)
            if geometry is not None:
                import numpy as np

                mask = (~np.all(arr.mask, axis=0)).astype("uint8") * 255
                dst.write_mask(mask)
            dst.build_overviews([2, 4, 8, 16], Resampling.nearest)
            dst.update_tags(OVR_RESAMPLING="NEAREST")
        logger.info("\u2714 Converted to COG: %s", path)
    except Exception as cog_err:  # pragma: no cover - optional broad catch
        logger.warning("\u26a0 COG conversion failed for %s: %s", path, cog_err)
