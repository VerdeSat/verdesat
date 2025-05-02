import os
import logging
from typing import Literal, Optional, Union, Any
from ee import ImageCollection
import ee
import math
from verdesat.ingestion.downloader import initialize, get_image_collection
from verdesat.ingestion.indices import compute_index

logger = logging.getLogger(__name__)


def compute_buffer(
    features: list[dict], buffer: int, buffer_percent: Optional[float]
) -> float:
    if buffer_percent is None:
        return buffer
    coords = []
    for feat in features:
        geom = feat.get("geometry", {})
        coords_list = geom.get("coordinates", [])
        # Handle Polygon or MultiPolygon
        rings = coords_list[0] if geom.get("type") == "MultiPolygon" else coords_list
        if rings and isinstance(rings[0], list):
            for x, y in rings[0]:
                coords.append((x, y))
    if not coords:
        return buffer
    xs, ys = zip(*coords)
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    mean_lat = (min_y + max_y) / 2.0
    # Approximate degrees to meters
    height_m = (max_y - min_y) * 111320.0
    width_m = (max_x - min_x) * 111320.0 * math.cos(math.radians(mean_lat))
    extent_max = max(abs(width_m), abs(height_m))
    return extent_max * (buffer_percent / 100.0)


def make_feature_geometry(feat: dict, buffer_m: float) -> ee.Geometry:
    geom_json = feat.get("geometry")
    geom = ee.Geometry(geom_json)
    if buffer_m > 0:
        geom = geom.buffer(buffer_m)
    return geom


def calc_percentile_stretch(
    img: ee.Image,
    features: list[dict],
    bands: list[str],
    scale: int,
    low: float,
    high: float,
) -> tuple[Union[float, list[float]], Union[float, list[float]]]:
    region = ee.FeatureCollection(
        {"type": "FeatureCollection", "features": features}
    ).geometry()
    reducer = ee.Reducer.percentile([low, high])
    stats = img.reduceRegion(
        reducer=reducer,
        geometry=region,
        scale=scale,
        bestEffort=True,
        maxPixels=1e12,
    ).getInfo()
    mins, maxs = [], []
    for band in bands:
        key_low = f"{band}_p{int(low)}"
        key_high = f"{band}_p{int(high)}"
        mins.append(stats.get(key_low, low))
        maxs.append(stats.get(key_high, high))
    min_val = mins if len(mins) > 1 else mins[0]
    max_val = maxs if len(maxs) > 1 else maxs[0]
    return min_val, max_val


def build_viz_params(
    bands: list[str],
    min_val,
    max_val,
    scale: int,
    dims: int,
    palette: Optional[list[str]],
    gamma: Optional[float],
    fmt: str,
) -> dict:
    params = {
        "bands": bands,
        "min": min_val,
        "max": max_val,
        "scale": scale,
    }
    if gamma is not None:
        params["gamma"] = [gamma] * len(bands)
    if fmt.lower() == "png":
        params.pop("scale", None)
        params["dimensions"] = dims
        if palette:
            params["palette"] = palette
    else:
        params["format"] = fmt
    return params


def export_one_thumbnail(
    img: ee.Image,
    feat: dict,
    date: str,
    bands: list[str],
    params: dict,
    out_dir: str,
    com_type: str,
    fmt: str,
):
    import requests

    props = feat.get("properties", {})
    pid = props.get("id") or props.get("system:index")
    geom_json = feat.get("geometry")
    url = (
        img.getThumbURL(params) if fmt.lower() == "png" else img.getDownloadURL(params)
    )
    ext = "png" if fmt.lower() == "png" else "tiff"
    path = os.path.join(out_dir, f"{com_type}_{pid}_{date}.{ext}")

    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        with open(path, "wb") as f:
            f.write(resp.content)
        logger.info("    ✔ Wrote %s file: %s", fmt, path)
    except Exception as e:
        logger.error(
            "Failed to export %s for polygon %s on %s: %s",
            fmt,
            pid,
            date,
            e,
            exc_info=True,
        )


def convert_to_cog(path: str):
    import rasterio
    from rasterio.enums import Resampling

    try:
        with rasterio.open(path) as src:
            profile = src.profile
            data = src.read()

        profile.update(
            driver="GTiff",
            compress="deflate",
            tiled=True,
            blockxsize=512,
            blockysize=512,
        )

        with rasterio.open(path, "w", **profile) as dst:
            dst.write(data)
            dst.build_overviews([2, 4, 8, 16], Resampling.nearest)
            dst.update_tags(OVR_RESAMPLING="NEAREST")

        logger.info("    ✔ Converted to COG: %s", path)
    except Exception as cog_err:
        logger.warning("    ⚠ COG conversion failed for %s: %s", path, cog_err)


def get_composite(
    feature_collection: dict,
    collection_id: str,
    start_date: str,
    end_date: str,
    reducer: ee.Reducer,
    bands: list[str],
    scale: int,
    period: Literal["M", "Y"],
    base_coll: Optional[ImageCollection] = None,
    project: Optional[str] = None,
) -> ImageCollection:
    """
    Build a monthly or yearly composite of the given bands, reducer (mean),
    filtered to the AOI feature_collection.
    """
    # 1) initialize EE with project (using our existing init)
    initialize(project=project)

    # DEBUG: inspect first raw image bands
    # first = (
    #     base_coll
    #     or get_image_collection(collection_id, start_date, end_date, feature_collection)
    # ).first()
    # logger.info("▶ get_composite: first image bands: %s", first.bandNames().getInfo())

    # Align start_date to period boundary
    start_dt = ee.Date(start_date)
    if period == "M":
        # First day of start month
        start_dt = ee.Date.fromYMD(start_dt.get("year"), start_dt.get("month"), 1)
    elif period == "Y":
        # First day of start year
        start_dt = ee.Date.fromYMD(start_dt.get("year"), 1, 1)
    # Use start_dt instead of start_date below

    # 2) load your AOI as an ee.FeatureCollection
    aoi = ee.FeatureCollection(feature_collection)

    # 3) build or use provided image collection
    # Use provided base_coll if available, otherwise fetch via downloader
    if base_coll is not None:
        coll = base_coll
    else:
        coll = get_image_collection(collection_id, start_date, end_date, aoi)
    # If NDVI, compute NDVI band and preserve time metadata
    if "NDVI" in bands:
        coll = coll.map(
            lambda img: (
                compute_index(img, index="ndvi")
                .rename("NDVI")
                .copyProperties(img, ["system:time_start"])
            )
        )
        # DEBUG: inspect bands post NDVI map
        # example = coll.first()
        # logger.info(
        #     "▶ get_composite (post-NDVI map): example bands: %s",
        #     example.bandNames().getInfo(),
        # )

    # 4) define the period‐mapper
    def make_periodic_image(offset):
        offset = ee.Number(offset)
        if period == "M":
            start = start_dt.advance(offset, "month")
            end = start.advance(1, "month")
        else:  # "Y"
            start = start_dt.advance(offset, "year")
            end = start.advance(1, "year")
        monthly = coll.filterDate(start, end)
        # perform reduction and rename bands to original
        reduced = monthly.select(bands).reduce(reducer)
        composite = reduced.rename(bands)
        return composite.set("system:time_start", start.millis())

    # 5) count months/years
    start = start_dt
    end = ee.Date(end_date)
    if period == "M":
        count = end.difference(start, "month").floor().add(1)
    else:
        count = end.difference(start, "year").floor().add(1)

    # 6) map over offsets
    offsets = ee.List.sequence(0, count.subtract(1))
    composites = ee.ImageCollection.fromImages(offsets.map(make_periodic_image))

    # DEBUG: number of composites
    total = ee.List.sequence(0, count.subtract(1)).size().getInfo()
    logger.info("▶ get_composite: total composites to generate: %d", total)

    return composites


def export_composites_to_png(
    composites: ee.ImageCollection,
    feature_collection: dict,
    out_dir: str,
    bands: list[str],
    palette: Optional[list[str]] = None,
    scale: Optional[int] = 30,
    min_val: Optional[Union[float, list[Any]]] = None,
    max_val: Optional[Union[float, list[Any]]] = None,
    buffer: int = 0,
    buffer_percent: Optional[float] = None,
    gamma: Optional[float] = None,
    percentile_low: Optional[float] = None,
    percentile_high: Optional[float] = None,
    fmt: str = "png",
) -> None:
    """
    Export each composite image for each polygon as PNG or GeoTIFF files.

    Args:
        composites: An EE ImageCollection of composites with band(s) to export.
        feature_collection: GeoJSON dict of polygon features.
        out_dir: Directory in which to save output files.
        bands: List of band names to include (e.g. ['B4','B3','B2'] or ['NDVI']).
        palette: Optional color palette for PNG thumbnails.
        scale: The pixel resolution in meters.
        min_val: Optional minimum value for visualization stretch.
        max_val: Optional maximum value for visualization stretch.
        buffer: Optional buffer (in meters) to apply to geometries.
        fmt: Output format, either 'png' or 'GeoTIFF'.

    Raises:
        ValueError: If `feature_collection` has no features or `composites` is empty.
    """
    import requests

    # Default thumbnail dimensions for PNG exports
    thumb_dimensions = 512

    com_type = "NDVI" if "NDVI" in bands else "RGB"

    os.makedirs(out_dir, exist_ok=True)
    features = feature_collection.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("No polygon features found in the provided GeoJSON.")

    # buffer_m = compute_buffer(features, buffer, buffer_percent)

    count = composites.size().getInfo()
    if not isinstance(count, int) or count <= 0:
        raise ValueError("No composites to export (empty collection).")

    # Determine stretch defaults (unless overridden)
    if min_val is None or max_val is None:
        if bands == ["NDVI"]:
            default_min, default_max = 0.0, 1.0
        else:
            default_min, default_max = 0.0, 0.4
        min_val = min_val if min_val is not None else default_min
        max_val = max_val if max_val is not None else default_max

    img_list = composites.toList(count)
    for i in range(count):
        img = ee.Image(img_list.get(i))
        logger.info("  • Composite #%d, bands: %s", i, img.bandNames().getInfo())
        date = ee.Date(img.get("system:time_start")).format("YYYY-MM-dd").getInfo()
        logger.info("    – date=%s", date)
        if img.bandNames().size().getInfo() == 0:
            continue

        min_val_i, max_val_i = min_val, max_val
        if percentile_low is not None and percentile_high is not None:
            min_val_i, max_val_i = calc_percentile_stretch(
                img, features, bands, scale, percentile_low, percentile_high
            )

        for feat in features:
            # compute buffer for this feature only
            local_buffer_m = compute_buffer([feat], buffer, buffer_percent)
            geom = make_feature_geometry(feat, local_buffer_m)
            clip = img.clip(geom)
            params = build_viz_params(
                bands,
                min_val_i,
                max_val_i,
                scale,
                thumb_dimensions,
                palette,
                gamma,
                fmt,
            )
            # Compute bounding box of buffered geometry for thumbnail region
            bounds = geom.bounds()
            bounds_info = bounds.getInfo()
            # Extract the corner coordinates ring
            coords = bounds_info.get("coordinates", [[]])[0]
            xs = [pt[0] for pt in coords]
            ys = [pt[1] for pt in coords]
            region_bbox = [min(xs), min(ys), max(xs), max(ys)]
            params["region"] = region_bbox

            export_one_thumbnail(
                clip, feat, date, bands, params, out_dir, com_type, fmt
            )

            if fmt.lower() != "png":
                # Convert to Cloud-Optimized GeoTIFF (COG)
                props = feat.get("properties", {})
                pid = props.get("id") or props.get("system:index")
                ext = "tiff"
                path = os.path.join(out_dir, f"{com_type}_{pid}_{date}.{ext}")
                convert_to_cog(path)
