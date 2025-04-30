import os
from typing import Literal, Optional
import ee
from verdesat.ingestion.downloader import initialize


def get_composite(
    feature_collection: dict,
    collection_id: str,
    start_date: str,
    end_date: str,
    reducer: ee.Reducer,
    bands: list[str],
    scale: int,
    period: Literal["M", "Y"],
    base_coll: Optional[ee.ImageCollection] = None,
    project: Optional[str] = None,
) -> ee.ImageCollection:
    """
    Build a monthly or yearly composite of the given bands, reducer (mean),
    filtered to the AOI feature_collection.
    """
    # 1) initialize EE with project (using our existing init)
    initialize(project=project)

    # Align start_date to period boundary
    start_dt = ee.Date(start_date)
    if period == 'M':
        # First day of start month
        start_dt = ee.Date.fromYMD(start_dt.get('year'), start_dt.get('month'), 1)
    elif period == 'Y':
        # First day of start year
        start_dt = ee.Date.fromYMD(start_dt.get('year'), 1, 1)
    # Use start_dt instead of start_date below

    # 2) load your AOI as an ee.FeatureCollection
    aoi = ee.FeatureCollection(feature_collection)

    # 3) build or use provided image collection
    if base_coll is not None:
        coll = base_coll
    else:
        coll = (
            ee.ImageCollection(collection_id)
            .filterDate(start_date, end_date)
            .filterBounds(aoi)
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
    return composites


def export_composites_to_png(
    composites: ee.ImageCollection,
    feature_collection: dict,
    out_dir: str,
    bands: list[str],
    palette: Optional[list[str]] = None,
    scale: Optional[int] = None,
    fmt: str = "png",
):
    """
    For each image in the composite collection, clip to each polygon
    and export a PNG per polygon–date.
    """
    os.makedirs(out_dir, exist_ok=True)
    # Load GeoJSON features client-side
    features = feature_collection.get("features")
    if not isinstance(features, list):
        raise ValueError("GeoJSON missing features list")

    # Determine stretch for visualization
    if bands == ["NDVI"]:
        min_val, max_val = 0.0, 1.0
    else:
        min_val, max_val = 0, 3000

    count = composites.size().getInfo()
    if count is None or not isinstance(count, int) or count <= 0:
        raise ValueError("Failed to compute a valid size of the composites collection.")
    img_list = composites.toList(ee.Number(count))
    for i in range(count):
        img = ee.Image(img_list.get(i))
        if img.bandNames().size().getInfo() == 0:
            continue
        date = ee.Date(img.get("system:time_start")).format("YYYY-MM-dd").getInfo()
        for feat in features:
            # extract polygon ID
            props = feat.get("properties", {})
            pid = props.get("id") or props.get("system:index")
            geom = ee.Geometry(feat.get("geometry"))
            clip = img.clip(geom)
            if fmt.lower() == "png":
                url = clip.getThumbURL(
                    {
                        "bands": bands,
                        "min": min_val,
                        "max": max_val,
                        "palette": palette or [],
                        "region": geom,
                        "scale": scale,
                    }
                )
                path = os.path.join(out_dir, f"{pid}_{date}.png")
            else:
                url = clip.getDownloadURL(
                    {
                        "bands": bands,
                        "min": min_val,
                        "max": max_val,
                        "region": geom,
                        "scale": scale,
                        "format": fmt,
                    }
                )
                path = os.path.join(out_dir, f"{pid}_{date}.tif")

            import requests

            resp = requests.get(url)
            with open(path, "wb") as f:
                f.write(resp.content)
