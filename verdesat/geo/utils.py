import math
from typing import Dict, Any, Optional


def buffer_geometry(
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
