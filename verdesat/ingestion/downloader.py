import ee
from ee import EEException
from typing import Optional


def initialize(credential_path: Optional[str] = None) -> None:
    """
    Authenticate & initialize Earth Engine.
    If a service‑account JSON path is given, use it; otherwise prompt.
    """
    try:
        if credential_path:
            creds = ee.ServiceAccountCredentials(None, credential_path)
            ee.Initialize(creds)
        else:
            ee.Initialize()
    except EEException:
        ee.Authenticate()
        ee.Initialize()


def get_image_collection(
    collection_id: str, start_date: str, end_date: str, region: ee.FeatureCollection
) -> ee.ImageCollection:
    """
    Return an ImageCollection filtered by date and bounds.
    """
    return (
        ee.ImageCollection(collection_id)
        .filterDate(start_date, end_date)
        .filterBounds(region)
    )
