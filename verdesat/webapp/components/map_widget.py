from typing import Mapping
import folium
from folium import FeatureGroup
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


def display_map(aoi_gdf, rasters: Mapping[str, Mapping[str, str]]) -> None:
    """Render Folium map with AOI boundaries and VI layers."""

    m = folium.Map(location=DEMO_CENTER, zoom_start=15, tiles="CartoDB positron")

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
            TileLayer(
                tiles=_cog_to_tile_url(ndvi_key),
                overlay=True,
                attr="Sentinel-2",
                control=False,
            ).add_to(ndvi_group)
        msavi_key = layers.get("msavi")
        if msavi_key:
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
