import os
import ee
from ee import EEException
from typing import Optional


def initialize(
    credential_path: Optional[str] = None, project: Optional[str] = None
) -> None:
    """
    Authenticate & initialize Earth Engine.
    If a service‑account JSON path is given, use it; otherwise prompt.
    """
    # Allow project override via env var
    project = project or os.getenv("VERDESAT_EE_PROJECT")
    try:
        if credential_path:
            creds = ee.ServiceAccountCredentials(None, credential_path)
            ee.Initialize(creds, project=project)
        else:
            ee.Initialize(project=project)
    except EEException:
        ee.Authenticate()
        ee.Initialize(project=project)


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
