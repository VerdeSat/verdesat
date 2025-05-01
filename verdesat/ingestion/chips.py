import os
import logging
from typing import Literal, Optional
from ee import ImageCollection
import ee
from verdesat.ingestion.downloader import initialize, get_image_collection
from verdesat.ingestion.indices import compute_index

logger = logging.getLogger(__name__)


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
    first = (
        base_coll
        or get_image_collection(collection_id, start_date, end_date, feature_collection)
    ).first()
    logger.info("▶ get_composite: first image bands: %s", first.bandNames().getInfo())

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
        example = coll.first()
        logger.info(
            "▶ get_composite (post-NDVI map): example bands: %s",
            example.bandNames().getInfo(),
        )

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
    scale: Optional[int] = None,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
    buffer: int = 0,
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

    # Determine stretch defaults (unless overridden)
    if min_val is None or max_val is None:
        if bands == ["NDVI"]:
            default_min, default_max = 0.0, 1.0
        else:
            default_min, default_max = 0.0, 0.4
        min_val = min_val if min_val is not None else default_min
        max_val = max_val if max_val is not None else default_max

    os.makedirs(out_dir, exist_ok=True)
    features = feature_collection.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("No polygon features found in the provided GeoJSON.")
    count = composites.size().getInfo()
    if not isinstance(count, int) or count <= 0:
        raise ValueError("No composites to export (empty collection).")

    img_list = composites.toList(count)
    for i in range(count):
        img = ee.Image(img_list.get(i))
        # DEBUG: composite bands and date
        logger.info("  • Composite #%d, bands: %s", i, img.bandNames().getInfo())
        date = ee.Date(img.get("system:time_start")).format("YYYY-MM-dd").getInfo()
        logger.info("    – date=%s", date)
        if img.bandNames().size().getInfo() == 0:
            continue
        date = ee.Date(img.get("system:time_start")).format("YYYY-MM-dd").getInfo()
        for feat in features:
            # extract polygon ID
            props = feat.get("properties", {})
            pid = props.get("id") or props.get("system:index")
            # Build EE geometry and apply buffer
            geom = ee.Geometry(feat.get("geometry"))
            if buffer > 0:
                geom = geom.buffer(buffer)
            clip = img.clip(geom)
            params = {
                "bands": bands,
                "min": min_val,
                "max": max_val,
                "region": geom,
                "scale": scale,
            }
            if fmt.lower() == "png":
                if palette:
                    params["palette"] = palette
                url = clip.getThumbURL(params)
                path = os.path.join(out_dir, f"{pid}_{date}.png")
            else:
                params["format"] = fmt
                url = clip.getDownloadURL(params)
                path = os.path.join(out_dir, f"{pid}_{date}.{fmt.lower()}")

            # DEBUG: print URL and response status
            # logger.info("    → URL: %s", url)
            try:
                resp = requests.get(url, timeout=60)
                resp.raise_for_status()
                with open(path, "wb") as f:
                    f.write(resp.content)
                logger.info("    ✔ Wrote %s file: %s", fmt, path)
                # If GeoTIFF, convert to Cloud-Optimized GeoTIFF (COG)
                if fmt.lower() != "png":
                    try:
                        import rasterio
                        from rasterio.enums import Resampling

                        # Read the newly written TIFF
                        with rasterio.open(path) as src:
                            profile = src.profile
                            data = src.read()

                        # Update profile for COG
                        profile.update(
                            driver="GTiff",
                            compress="deflate",
                            tiled=True,
                            blockxsize=512,
                            blockysize=512,
                        )

                        # Rewrite as COG with overviews
                        with rasterio.open(path, "w", **profile) as dst:
                            dst.write(data)
                            dst.build_overviews([2, 4, 8, 16], Resampling.nearest)
                            dst.update_tags(OVR_RESAMPLING="NEAREST")

                        logger.info("    ✔ Converted to COG: %s", path)
                    except Exception as cog_err:
                        logger.warning(
                            "    ⚠ COG conversion failed for %s: %s", path, cog_err
                        )
            except Exception as e:
                logger.error(
                    "Failed to export %s for polygon %s on %s: %s",
                    fmt,
                    pid,
                    date,
                    e,
                    exc_info=True,
                )
                continue
