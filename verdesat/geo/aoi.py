from typing import Dict
from shapely.geometry import Polygon, MultiPolygon
from analytics.timeseries import TimeSeries

class AOI:
    """
    Area of Interest (AOI): represents one field, forest, or custom polygon with static and dynamic properties.
    - geometry: shapely Polygon or MultiPolygon
    - static_props: dict (name, climate_zone, etc.)
    - timeseries: Dict[str, TimeSeries] (e.g. {"ndvi": TimeSeries, ...})
    """
    def __init__(self, geometry: Polygon or MultiPolygon, static_props: dict, timeseries: Dict[str, TimeSeries] = None):
        self.geometry = geometry
        self.static_props = static_props
        self.timeseries = timeseries or {}

    def add_timeseries(self, variable: str, ts: TimeSeries):
        self.timeseries[variable] = ts