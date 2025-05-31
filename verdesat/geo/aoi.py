"""
Module `geo.aoi` defines the AOI (Area of Interest) class, which holds a single
geographic feature (Polygon/MultiPolygon), its static properties, and associated time series.
"""

import json
from typing import List, Union, Dict, Optional, Any
from shapely.geometry import shape, Polygon, MultiPolygon
import geopandas as gpd
from verdesat.analytics.timeseries import TimeSeries


class AOI:
    """
    Area of Interest (AOI): represents one field, forest, or custom polygon
    with static and dynamic properties.
    - geometry: shapely Polygon or MultiPolygon
    - static_props: dict (name, climate_zone, etc.)
    - timeseries: Dict[str, TimeSeries] (e.g. {"ndvi": TimeSeries, ...})
    """

    def __init__(
        self,
        geometry: Union[Polygon, MultiPolygon],
        static_props: Dict[str, Any],
        timeseries: Optional[Dict[str, TimeSeries]] = None,
    ):
        self.geometry = geometry
        self.static_props = static_props
        self.timeseries = timeseries or {}

    def add_timeseries(self, variable: str, ts: TimeSeries):
        """
        Attach a TimeSeries object to this AOI under the given variable name.
        """
        self.timeseries[variable] = ts

    @classmethod
    def from_file(cls, path: str, id_col: str = "id") -> List["AOI"]:
        """
        Load a vector file (GeoJSON, Shapefile, etc.) into AOI instances.
        Reads with GeoPandas, ensures id_col exists, then delegates to from_gdf.
        """
        gdf = gpd.read_file(path)
        return cls.from_gdf(gdf, id_col)

    @classmethod
    def from_geojson(cls, geojson: Union[str, dict], id_col: str = "id") -> List["AOI"]:
        """
        Parse a GeoJSON object (or path to a GeoJSON file) and return AOI instances.
        """
        if isinstance(geojson, str):
            with open(geojson, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = geojson
        features = data.get("features", [])
        gdf = gpd.GeoDataFrame(
            [
                {**feat.get("properties", {}), "geometry": shape(feat["geometry"])}
                for feat in features
            ],
            crs="EPSG:4326",
        )
        return cls.from_gdf(gdf, id_col)

    @classmethod
    def from_gdf(cls, gdf: gpd.GeoDataFrame, id_col: str = "id") -> List["AOI"]:
        """
        Build AOI instances from a GeoDataFrame.
        Ensures id_col exists and sequential, and converts rows to AOI objects.
        """
        if id_col not in gdf.columns:
            gdf[id_col] = gdf.index.astype(int) + 1
        aois: List[AOI] = []
        for _, row in gdf.iterrows():
            props: Dict = row.drop(labels="geometry").to_dict()
            aois.append(cls(row.geometry, props))
        return aois
