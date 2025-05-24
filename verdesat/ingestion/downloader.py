import os
import logging

logger = logging.getLogger(__name__)
import time
import ee
from verdesat.ingestion.mask import mask_fmask_bits
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


def safe_get_info(obj, max_retries=3):
    """
    Wrapper for obj.getInfo() that:
      - retries transient errors
      - on PERMISSION_DENIED, forces a re-auth + re-init and retries once
      - raises after max_retries
    """
    for attempt in range(1, max_retries + 1):
        try:
            return obj.getInfo()
        except EEException as e:
            msg = str(e)
            # Permission issue: ask user to re-auth
            if "PERMISSION_DENIED" in msg:
                logger.error("Earth Engine permission denied. Re-authenticating...")
                ee.Authenticate()  # opens browser/window once
                initialize()  # re-init via our wrapper with credentials/project
                # only retry once after auth
                if attempt == 1:
                    continue
            # Transient error? retry with backoff
            if attempt < max_retries:
                backoff = 2 ** (attempt - 1)
                logger.warning(
                    "Transient EE error (attempt %d/%d): %s – retrying in %ds",
                    attempt,
                    max_retries,
                    msg,
                    backoff,
                )
                time.sleep(backoff)
                continue
            # Give up
            logger.error("Failed to getInfo() after %d attempts: %s", attempt, msg)
            raise


def get_image_collection(
    collection_id: str,
    start_date: str,
    end_date: str,
    region: ee.FeatureCollection,
    mask_clouds: bool = True,
) -> ee.ImageCollection:
    """
    Return an ImageCollection filtered by date and bounds.
    """
    coll = (
        ee.ImageCollection(collection_id)
        .filterDate(start_date, end_date)
        .filterBounds(region)
    )
    if mask_clouds:
        coll = coll.map(mask_fmask_bits)
    return coll
