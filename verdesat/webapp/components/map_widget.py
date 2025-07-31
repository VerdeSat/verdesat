from typing import Sequence
import folium
from folium.raster_layers import TileLayer
from streamlit_folium import st_folium
from verdesat.webapp.services.r2 import signed_url

DEMO_CENTER = (16.79162, -92.53845)
# adjust to AOI centroid


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


def display_map(
    aoi_gdf,
    ndvi_keys: Sequence[tuple[str, str]],
    msavi_keys: Sequence[tuple[str, str]],
    layer_state,
):
    """Render Folium map inside Streamlit, return updated layer_state dict."""
    m = folium.Map(location=DEMO_CENTER, zoom_start=15, tiles="CartoDB positron")

    # AOI vector
    folium.GeoJson(
        aoi_gdf, name="AOI", style_function=lambda _: {"color": "#159466"}
    ).add_to(m)

    # NDVI raster layers
    for label, key in ndvi_keys:
        ndvi_layer = TileLayer(
            tiles=_cog_to_tile_url(key),
            name=label,
            overlay=True,
            attr="Sentinel-2",
        )
        if layer_state.get("ndvi", True):
            ndvi_layer.add_to(m)

    # MSAVI raster layers
    for label, key in msavi_keys:
        msavi_layer = TileLayer(
            tiles=_cog_to_tile_url(key),
            name=label,
            overlay=True,
            attr="Sentinel-2",
        )
        if layer_state.get("msavi", True):
            msavi_layer.add_to(m)

    folium.LayerControl(position="topright", collapsed=False).add_to(m)

    # Render in Streamlit
    out = st_folium(
        m, width="100%", height=500, returned_objects=["last_active_drawing"]
    )
    return layer_state
