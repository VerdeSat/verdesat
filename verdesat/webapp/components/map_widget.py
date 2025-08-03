"""Utilities for rendering project maps in the dashboard."""

from typing import Mapping
from pathlib import Path
import base64
import io
import json

import folium
import numpy as np
import rasterio
from PIL import Image
from folium import FeatureGroup
from folium.raster_layers import ImageOverlay, TileLayer
from streamlit_folium import st_folium
import streamlit as st

from verdesat.webapp.services.r2 import signed_url

# Helper imports
import logging
logger = logging.getLogger(__name__)


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
    alpha = (~data.mask).astype("uint8") * 255

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
    )


def display_map(aoi_gdf, rasters: Mapping[str, Mapping[str, str]]) -> None:
    """Render Folium map with AOI boundaries and VI layers."""

    # Preserve view between Streamlit reruns
    centre_dict = st.session_state.get("map_center")
    zoom = st.session_state.get("map_zoom", 13)

    if isinstance(centre_dict, dict):
        centre = [centre_dict["lat"], centre_dict["lng"]]
    elif isinstance(centre_dict, list) and len(centre_dict) == 2:
        # legacy list format – make sure order is [lat, lon]
        lat, lon = centre_dict
        if abs(lat) > 90:     # looks like it’s swapped
            lat, lon = lon, lat
        centre = [lat, lon]
        # upgrade to dict for future runs
        st.session_state["map_center"] = {"lat": lat, "lng": lon}
    else:
        centre = None  # first run

    if centre is None:
        # First time for this session – centre on full extent
        bounds = aoi_gdf.total_bounds  # [minx, miny, maxx, maxy]
        centre = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
        zoom = 15  # will be overridden by fit_bounds below
        st.session_state["map_first_init"] = True
    else:
        st.session_state["map_first_init"] = False

    m = folium.Map(location=centre, zoom_start=zoom, tiles="CartoDB positron")

    folium.GeoJson(
        json.loads(aoi_gdf.to_json()),
        name="AOI Boundaries",
        style_function=lambda *_: {"color": "#159466", "weight": 2, "fill": False},
    ).add_to(m)

    # Fit to full bounds only on the very first render after a new project
    first_init = st.session_state.pop("map_first_init", False)
    if first_init:
        bounds_arr = aoi_gdf.total_bounds.reshape(2, 2)
        m.fit_bounds(bounds_arr.tolist())
        # Persist the centre immediately so the next rerun has a valid view
        st.session_state["map_center"] = {"lat": centre[0], "lng": centre[1]}
        # Skip saving centre/zoom on the same run; wait for the next user action.
        st.session_state["_skip_next_map_state"] = True

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

    state = st_folium(m, width="100%", height=500, key="main_map")
    if st.session_state.pop("_skip_next_map_state", False):
        logger.debug("Skipping first map state save after fit_bounds()")
    else:
        # Persist centre & zoom so the next rerun opens at the same view
        if state and state.get("center"):
            st.session_state["map_center"] = {
                "lat": state["center"]["lat"],
                "lng": state["center"]["lng"],
            }
        if state and "zoom" in state:
            st.session_state["map_zoom"] = int(state["zoom"])
