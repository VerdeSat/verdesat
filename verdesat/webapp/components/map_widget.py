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

    The map is initialised once per AOI/raster combination and then reused on
    subsequent reruns so user panning and zooming do not trigger a full map
    reload. A new map is constructed only when the underlying layers change.
    """

    layers_key = hashlib.sha256(
        (aoi_gdf.to_json() + json.dumps(rasters, sort_keys=True)).encode("utf-8")
    ).hexdigest()

    cached_map = st.session_state.get("map_obj")

    if st.session_state.get("map_layers_key") != layers_key or not isinstance(
        cached_map, folium.Map
    ):
        bounds_arr = aoi_gdf.total_bounds.reshape(2, 2)
        centre = [
            (bounds_arr[0][1] + bounds_arr[1][1]) / 2,
            (bounds_arr[0][0] + bounds_arr[1][0]) / 2,
        ]
        m = folium.Map(location=centre, zoom_start=13, tiles="CartoDB positron")

        folium.GeoJson(
            json.loads(aoi_gdf.to_json()),
            name="AOI Boundaries",
            style_function=lambda *_: {"color": "#159466", "weight": 2, "fill": False},
        ).add_to(m)

        ndvi_layer_added = False
        msavi_layer_added = False

        for layers in rasters.values():
            ndvi_key = layers.get("ndvi")
            if ndvi_key and not ndvi_layer_added:
                name = "NDVI 2024"
                ndvi_path = _resolve_cog_path(ndvi_key)
                if ndvi_path:
                    _local_overlay(str(ndvi_path), name=name).add_to(m)
                else:
                    TileLayer(
                        tiles=_cog_to_tile_url(ndvi_key),
                        overlay=True,
                        attr="Sentinel-2",
                        name=name,
                    ).add_to(m)
                ndvi_layer_added = True
            msavi_key = layers.get("msavi")
            if msavi_key and not msavi_layer_added:
                name = "MSAVI 2024"
                msavi_path = _resolve_cog_path(msavi_key)
                if msavi_path:
                    _local_overlay(str(msavi_path), name=name).add_to(m)
                else:
                    TileLayer(
                        tiles=_cog_to_tile_url(msavi_key),
                        overlay=True,
                        attr="Sentinel-2",
                        name=name,
                    ).add_to(m)
                msavi_layer_added = True
            if ndvi_layer_added and msavi_layer_added:
                break

        if ndvi_layer_added or msavi_layer_added:
            folium.LayerControl(position="topright", collapsed=False).add_to(m)

        m.fit_bounds(bounds_arr.tolist())

        st.session_state["map_obj"] = m
        st.session_state["map_layers_key"] = layers_key

    state = st_folium(
        st.session_state["map_obj"], width="100%", height=500, key="main_map"
    )
    if state and state.get("center"):
        m = st.session_state["map_obj"]
        m.location = [state["center"]["lat"], state["center"]["lng"]]
        if "zoom" in state:
            m.options["zoom"] = state["zoom"]
