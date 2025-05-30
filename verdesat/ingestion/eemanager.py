"""
Module `ingestion.eemanager` provides the EarthEngineManager class to
encapsulate Google Earth Engine initialization, retries, and image collection retrieval.
"""

import os
import time
import logging

import ee
from ee import EEException
from typing import Optional

from .mask import mask_fmask_bits

logger = logging.getLogger(__name__)


class EarthEngineManager:
    """
    Manages interaction with Google Earth Engine: initialization, retries, and collection retrieval.
    """

    def __init__(
        self, credential_path: Optional[str] = None, project: Optional[str] = None
    ):
        self.credential_path = credential_path
        self.project = project or os.getenv("VERDESAT_EE_PROJECT")

    def initialize(self) -> None:
        """
        Authenticate & initialize Earth Engine.
        If a service‑account JSON path is given, use it; otherwise prompt.
        """
        project = self.project
        try:
            if self.credential_path:
                # type: ignore[arg-type]
                creds = ee.ServiceAccountCredentials(None, self.credential_path)  # type: ignore[arg-type]
                ee.Initialize(creds, project=project)
            else:
                ee.Initialize(project=project)
        except EEException:
            ee.Authenticate()
            ee.Initialize(project=project)

    def safe_get_info(self, obj, max_retries: int = 3):
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
                    self.initialize()  # re-init via our wrapper with credentials/project
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
        self,
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


# Convenience singleton
ee_manager = EarthEngineManager()
