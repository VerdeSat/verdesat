"""Utilities for rendering project maps in the dashboard."""

from typing import Mapping
from pathlib import Path
import base64
import io

import folium
import numpy as np
import rasterio
from PIL import Image
from folium import FeatureGroup
from folium.raster_layers import ImageOverlay, TileLayer
from streamlit_folium import st_folium

from verdesat.webapp.services.r2 import signed_url


def _cog_to_tile_url(cog_key: str) -> str:
    """
    Build a Titiler tile URL for a *private* COG in R2 using a presigned URL.

    Use the public Titiler endpoint with explicit WebMercatorQuad TMS to avoid
    blank tiles on some instances.
    """
    import urllib.parse

    presigned = signed_url(cog_key)
    encoded = urllib.parse.quote_plus(presigned)

    return (
        "https://titiler.xyz/cog/tiles/WebMercatorQuad/{z}/{x}/{y}.png"
        f"?url={encoded}&rescale=0,1"
    )


def _local_overlay(path: str) -> ImageOverlay:
    """Return a semi-transparent overlay for a local raster ``path``."""

    with rasterio.open(path) as src:
        data = src.read(1, masked=True)
        bounds = [
            [src.bounds.bottom, src.bounds.left],
            [src.bounds.top, src.bounds.right],
        ]

    arr = np.clip(data.filled(0), 0, 1)
    img = Image.fromarray((arr * 255).astype("uint8"))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return ImageOverlay(
        image=f"data:image/png;base64,{b64}",
        bounds=bounds,
        opacity=0.7,
        interactive=False,
        cross_origin=False,
    )


def display_map(aoi_gdf, rasters: Mapping[str, Mapping[str, str]]) -> None:
    """Render Folium map with AOI boundaries and VI layers."""

    centroid = aoi_gdf.unary_union.centroid
    m = folium.Map(
        location=[centroid.y, centroid.x], zoom_start=15, tiles="CartoDB positron"
    )

    folium.GeoJson(
        aoi_gdf,
        name="AOI Boundaries",
        style_function=lambda _: {"color": "#159466"},
    ).add_to(m)

    ndvi_group = FeatureGroup(name="NDVI 2024")
    msavi_group = FeatureGroup(name="MSAVI 2024")

    for layers in rasters.values():
        ndvi_key = layers.get("ndvi")
        if ndvi_key:
            if Path(ndvi_key).exists():
                _local_overlay(ndvi_key).add_to(ndvi_group)
            else:
                TileLayer(
                    tiles=_cog_to_tile_url(ndvi_key),
                    overlay=True,
                    attr="Sentinel-2",
                    control=False,
                ).add_to(ndvi_group)
        msavi_key = layers.get("msavi")
        if msavi_key:
            if Path(msavi_key).exists():
                _local_overlay(msavi_key).add_to(msavi_group)
            else:
                TileLayer(
                    tiles=_cog_to_tile_url(msavi_key),
                    overlay=True,
                    attr="Sentinel-2",
                    control=False,
                ).add_to(msavi_group)

    ndvi_group.add_to(m)
    msavi_group.add_to(m)
    folium.LayerControl(position="topright", collapsed=False).add_to(m)

    st_folium(m, width="100%", height=500)
