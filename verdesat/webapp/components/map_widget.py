"""Utilities for rendering project maps in the dashboard."""

from typing import Mapping
from pathlib import Path
import base64
import io
import json
import hashlib

import folium
import numpy as np
import rasterio
from PIL import Image
from folium import FeatureGroup
from folium.raster_layers import ImageOverlay, TileLayer
from streamlit_folium import st_folium
import streamlit as st

from verdesat.webapp.services.r2 import signed_url


def _resolve_cog_path(key: str) -> Path | None:
    """Return a filesystem path for *key* if it exists.

    Raster paths in configuration may be relative to the project repository
    rather than the current working directory. This helper tries the given
    path directly and falls back to resolving it relative to the package
    root. ``None`` is returned when the key does not correspond to a local
    file, allowing callers to treat it as a remote object.
    """

    path = Path(key)
    if path.exists():
        return path

    repo_path = Path(__file__).resolve().parents[2] / key
    if repo_path.exists():
        return repo_path
    return None


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


def _local_overlay(path: str, *, name: str | None = None) -> ImageOverlay:
    """Return a semi‑transparent overlay for a local COG.

    Pixels where the raster has NoData (masked) are fully transparent.
    Signal is mapped to green; low values fade to red/blue.
    """
    with rasterio.open(path) as src:
        data = src.read(1, masked=True)
        # Cast to built‑in float so Folium → Jinja → JSON doesn’t choke on numpy scalars
        bounds = [
            [float(src.bounds.bottom), float(src.bounds.left)],
            [float(src.bounds.top), float(src.bounds.right)],
        ]

    # Colour ramp for signal
    arr = np.clip(data.filled(0), 0, 1)  # 0‑1 float
    g = (arr * 255).astype("uint8")
    r = 255 - g
    b = 255 - g

    # Alpha channel – fully transparent where masked
    mask_arr = np.ma.getmaskarray(data)
    alpha = (~mask_arr).astype("uint8") * 255

    rgba = np.stack([r, g, b, alpha], axis=-1).astype("uint8")
    img = Image.fromarray(rgba, mode="RGBA")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return ImageOverlay(
        image=f"data:image/png;base64,{b64}",
        bounds=bounds,
        opacity=1,
        interactive=False,
        cross_origin=False,
        name=name,
    )


def display_map(aoi_gdf, rasters: Mapping[str, Mapping[str, str]]) -> None:
    """Render Folium map with AOI boundaries and VI layers.

    The map is rebuilt on every Streamlit rerun, but the user's pan/zoom state
    is preserved in ``st.session_state`` so interactions persist. When the AOI
    geometry or rasters change, stored state is cleared and the map recentres on
    the AOI.
    """

    layers_key = hashlib.sha256(
        (aoi_gdf.to_json() + json.dumps(rasters, sort_keys=True)).encode("utf-8")
    ).hexdigest()

    if st.session_state.get("map_layers_key") != layers_key:
        st.session_state["map_layers_key"] = layers_key
        st.session_state.pop("map_center", None)
        st.session_state.pop("map_zoom", None)

    bounds = aoi_gdf.total_bounds  # minx, miny, maxx, maxy
    bounds_latlon = [[bounds[1], bounds[0]], [bounds[3], bounds[2]]]
    centre = st.session_state.get("map_center") or [
        (bounds_latlon[0][0] + bounds_latlon[1][0]) / 2,
        (bounds_latlon[0][1] + bounds_latlon[1][1]) / 2,
    ]

    # Restore previous zoom level if available so reruns don't jump
    zoom = st.session_state.get("map_zoom")
    if zoom is not None:
        m = folium.Map(location=centre, tiles="CartoDB positron", zoom_start=zoom)
    else:
        m = folium.Map(location=centre, tiles="CartoDB positron")
    folium.GeoJson(
        aoi_gdf,
        name="AOI Boundaries",
        style_function=lambda *_: {
            "color": "#159466",
            "weight": 2,
            "fill": False,
        },
    ).add_to(m)

    ndvi_group = FeatureGroup(name="Last annual NDVI", show=True)
    msavi_group = FeatureGroup(name="Last annual MSAVI", show=True)
    ndvi_added = False
    msavi_added = False

    for layers in rasters.values():
        ndvi_key = layers.get("ndvi")
        if ndvi_key:
            ndvi_path = _resolve_cog_path(ndvi_key)
            if ndvi_path:
                _local_overlay(str(ndvi_path)).add_to(ndvi_group)
            else:
                TileLayer(
                    tiles=_cog_to_tile_url(ndvi_key),
                    overlay=True,
                    attr="Sentinel-2",
                    control=False,
                ).add_to(ndvi_group)
            ndvi_added = True

        msavi_key = layers.get("msavi")
        if msavi_key:
            msavi_path = _resolve_cog_path(msavi_key)
            if msavi_path:
                _local_overlay(str(msavi_path)).add_to(msavi_group)
            else:
                TileLayer(
                    tiles=_cog_to_tile_url(msavi_key),
                    overlay=True,
                    attr="Sentinel-2",
                    control=False,
                ).add_to(msavi_group)
            msavi_added = True

    if ndvi_added:
        ndvi_group.add_to(m)
    if msavi_added:
        msavi_group.add_to(m)

    folium.LayerControl(position="topright", collapsed=False).add_to(m)
    if "map_center" not in st.session_state:
        m.fit_bounds(bounds_latlon)

    placeholder = st.session_state.get("map_placeholder")
    if placeholder is None:
        placeholder = st.empty()
        st.session_state["map_placeholder"] = placeholder
    else:
        placeholder.empty()

    with placeholder:
        state = st_folium(m, width="100%", height=500, key="main_map")

    # Persist pan/zoom state for subsequent reruns
    if isinstance(state, dict):
        center = state.get("center")
        zoom_level = state.get("zoom")
        if center:
            st.session_state["map_center"] = center
        if zoom_level is not None:
            st.session_state["map_zoom"] = zoom_level
