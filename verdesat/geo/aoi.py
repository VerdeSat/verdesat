"""
Module `geo.aoi` defines the AOI (Area of Interest) class, which holds a single
geographic feature (Polygon/MultiPolygon), its static properties, and associated time series.
"""

import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

import geopandas as gpd
import ee
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from verdesat.analytics.timeseries import TimeSeries


@dataclass
class AOI:
    """Area of Interest with static properties and optional time series."""

    geometry: Union[Polygon, MultiPolygon]
    static_props: Dict[str, Any]
    timeseries: Dict[str, TimeSeries] = field(default_factory=dict)

    def add_timeseries(self, variable: str, ts: TimeSeries):
        """Attach a TimeSeries object to this AOI under the given variable."""
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

    def ee_geometry(self) -> ee.Geometry:
        """
        Return an Earth Engine Geometry corresponding to this AOI’s Shapely geometry.
        """
        return ee.Geometry(mapping(self.geometry))

    def buffered_ee_geometry(self, buffer_m: float) -> ee.Geometry:
        """
        Return an Earth Engine Geometry buffered by buffer_m meters.
        If buffer_m <= 0, returns the unbuffered geometry.
        """
        geom = self.ee_geometry()
        if buffer_m and buffer_m > 0:
            return geom.buffer(buffer_m)
        return geom

    def buffer_geometry(
        self,
        feature: Dict[str, Any],
        buffer: int,
        buffer_percent: Optional[float],
    ) -> float:
        """
        Given one GeoJSON feature (as a dict), return a buffer distance in metres.

        If buffer_percent is provided, compute the max side of its bounding box,
        then multiply by (buffer_percent / 100). Otherwise, return the absolute `buffer`.
        """
        if buffer_percent is None:
            return float(buffer)

        geom = feature.get("geometry", {})
        coords_list = geom.get("coordinates", [])
        if not coords_list:
            return float(buffer)

        # Extract all leaf coords (Polygon or MultiPolygon):
        raw = coords_list[0] if geom.get("type") == "MultiPolygon" else coords_list
        flat = raw[0] if isinstance(raw[0][0], (list, tuple)) else raw

        if not isinstance(flat, list) or len(flat) == 0:
            return float(buffer)

        xs = [pt[0] for pt in flat]
        ys = [pt[1] for pt in flat]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        mean_lat = (min_y + max_y) / 2.0
        # Approximate 1° latitude = ~111,320 m
        height_m = (max_y - min_y) * 111_320.0
        width_m = (max_x - min_x) * 111_320.0 * math.cos(math.radians(mean_lat))
        extent_max = max(abs(width_m), abs(height_m))

        return extent_max * (buffer_percent / 100.0)
