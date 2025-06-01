from typing import List
import ee
from ee import Reducer
from .timeseries import TimeSeries


class AnalyticsEngine:
    """
    Collection of static methods for common Earth Engine analytics operations,
    including building composites and computing spectral indices.
    """

    @staticmethod
    def compute_index(img: ee.Image, index: str) -> ee.Image:
        """
        Simply wrap into your existing index‐calculation logic. For example,
        if index=="ndvi", return the band:
            (NIR - RED) / (NIR + RED).
        If you already have a JSON‐driven registry, you can dynamically apply.
        For now, we assume only 'ndvi' is needed:
        """
        if index.lower() == "ndvi":
            return img.normalizedDifference(["nir", "red"]).rename("NDVI")
        else:
            raise ValueError(f"Unsupported index: {index}")

    @staticmethod
    def build_composites(
        base_ic: ee.ImageCollection,
        period: str,
        reducer: Reducer,
        start: str,
        end: str,
        bands: List[str],
        scale: int,
    ) -> ee.ImageCollection:
        """
        Build monthly ('M') or yearly ('Y') composites from base_ic, using the given reducer,
        filtered between start/end. Returns a new ee.ImageCollection of composites.

        This mirrors the old get_composite(...) logic, but does it in a reusable static method.
        """
        # Align the start date to the first of the month or year
        start_dt = ee.Date(start)
        if period == "M":
            start_dt = ee.Date.fromYMD(start_dt.get("year"), start_dt.get("month"), 1)
        else:  # "Y"
            start_dt = ee.Date.fromYMD(start_dt.get("year"), 1, 1)

        end_dt = ee.Date(end)

        def make_periodic_image(offset):
            offset = ee.Number(offset)
            if period == "M":
                window_start = start_dt.advance(offset, "month")
                window_end = window_start.advance(1, "month")
            else:
                window_start = start_dt.advance(offset, "year")
                window_end = window_start.advance(1, "year")

            truncated = base_ic.filterDate(window_start, window_end)
            reduced = truncated.select(bands).reduce(reducer)
            composite = reduced.rename(bands)
            return composite.set("system:time_start", window_start.millis())

        if period == "M":
            count = end_dt.difference(start_dt, "month").floor().add(1)
        else:
            count = end_dt.difference(start_dt, "year").floor().add(1)

        offsets = ee.List.sequence(0, count.subtract(1))
        composites = ee.ImageCollection.fromImages(offsets.map(make_periodic_image))
        return composites

    @staticmethod
    def compute_trend(ts: TimeSeries):
        pass
