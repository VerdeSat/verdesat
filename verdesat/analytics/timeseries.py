import ee
import pandas as pd
from typing import Literal
from verdesat.ingestion.downloader import initialize, get_image_collection
from verdesat.ingestion.mask import mask_fmask_bits
from verdesat.ingestion.indices import compute_ndvi
import logging


def chunked_timeseries(
    geojson: dict,
    collection_id: str,
    start_date: str,
    end_date: str,
    scale: int = 30,
    freq: str = "M",
) -> pd.DataFrame:
    """
    Retrieve NDVI time series in chunks to avoid GEE element limits.
    Splits the date range by the given freq ('D','M','Q','Y') and
    concatenates results from daily_timeseries.
    """
    # Build list of chunk boundaries
    dates = pd.date_range(start=start_date, end=end_date, freq=freq)
    bounds = zip(
        [start_date] + list(dates.strftime("%Y-%m-%d")),
        list(dates.strftime("%Y-%m-%d")) + [end_date],
    )
    dfs = []
    for s, e in bounds:
        try:
            df_chunk = daily_timeseries(geojson, collection_id, s, e, scale)
            dfs.append(df_chunk)
        except Exception as err:
            logging.warning(f"Chunk {s}–{e} failed: {err}")
    if not dfs:
        raise RuntimeError("All chunks failed for time series retrieval")
    return pd.concat(dfs, ignore_index=True)


def daily_timeseries(
    geojson: dict, collection_id: str, start_date: str, end_date: str, scale: int = 30
) -> pd.DataFrame:
    """
    Returns a DataFrame of (id, date, mean_ndvi) for each image in the date range.
    """
    initialize()
    region = ee.FeatureCollection(geojson)
    coll = get_image_collection(collection_id, start_date, end_date, region)

    def _reduce(img):
        m = mask_fmask_bits(img)
        ndvi = compute_ndvi(m)
        stats = ndvi.reduceRegions(region, ee.Reducer.mean(), scale=scale)
        date = ee.Date(img.get("system:time_start")).format("YYYY-MM-dd")
        return stats.map(lambda f: f.set("date", date))

    features = coll.map(_reduce).flatten().getInfo().get("features", [])
    rows = [
        {
            "id": feat["properties"].get("id"),
            "date": feat["properties"].get("date"),
            "mean_ndvi": feat["properties"].get("mean"),
        }
        for feat in features
    ]
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


def aggregate_timeseries(
    df: pd.DataFrame, freq: Literal["D", "M", "Y"]
) -> pd.DataFrame:
    """
    Aggregate the daily DataFrame to the given frequency:
      'D' = daily (no-op), 'M' = monthly mean, 'Y' = yearly mean.
    Returns a DataFrame with MultiIndex [id, date].
    """
    df = df.set_index(["id", "date"])
    grouped = (
        df["mean_ndvi"].groupby(level=0).resample(freq, level=1).mean().reset_index()
    )
    return grouped
