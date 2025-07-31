"""
Module `ingestion.eemanager` provides the EarthEngineManager class to
encapsulate Google Earth Engine initialization, retries, and image collection retrieval.
"""

import os
import json
import time
from typing import Optional, Any

from verdesat.core.logger import Logger
from google.oauth2.credentials import Credentials

import ee
from ee import EEException
from .sensorspec import SensorSpec


class EarthEngineManager:
    """
    Manages interaction with Google Earth Engine: initialization, retries, and collection retrieval.
    """

    def __init__(
        self,
        credential_path: Optional[str] = None,
        project: Optional[str] = None,
        logger=None,
    ):
        self.credential_path = credential_path
        # Allow non-interactive auth using a refresh token passed via env.
        self.token_env = os.getenv("EARTHENGINE_TOKEN")
        self.project = project or os.getenv("VERDESAT_EE_PROJECT")
        self.logger = logger or Logger.get_logger(__name__)

    def initialize(self) -> None:
        """
        Authenticate & initialize Earth Engine.
        If a service‑account JSON path is given, use it; otherwise prompt.
        """
        project = self.project
        try:
            if self.credential_path:
                # type: ignore[arg-type]
                sa_credentials: Any = ee.ServiceAccountCredentials(
                    None, self.credential_path  # type: ignore[arg-type]
                )
                ee.Initialize(sa_credentials, project=project)
            elif self.token_env:
                creds_data = None
                if os.path.exists(self.token_env):
                    with open(self.token_env, "r", encoding="utf-8") as fh:
                        creds_data = json.load(fh)
                else:
                    try:
                        creds_data = json.loads(self.token_env)
                    except json.JSONDecodeError:
                        pass
                if creds_data and "refresh_token" in creds_data:
                    token_credentials: Any = Credentials(
                        None,
                        refresh_token=creds_data.get("refresh_token"),
                        token_uri=creds_data.get("token_uri", ee.oauth.TOKEN_URI),
                        client_id=creds_data.get("client_id", ee.oauth.CLIENT_ID),
                        client_secret=creds_data.get(
                            "client_secret", ee.oauth.CLIENT_SECRET
                        ),
                        scopes=creds_data.get("scopes", ee.oauth.SCOPES),
                        quota_project_id=creds_data.get("project"),
                    )
                    ee.Initialize(token_credentials, project=project)
                else:
                    ee.Initialize(project=project)
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
                    self.logger.error(
                        "Earth Engine permission denied. Re-authenticating..."
                    )
                    ee.Authenticate()  # opens browser/window once
                    self.initialize()  # re-init via our wrapper with credentials/project
                    # only retry once after auth
                    if attempt == 1:
                        continue
                # Transient error? retry with backoff
                if attempt < max_retries:
                    backoff = 2 ** (attempt - 1)
                    self.logger.warning(
                        "Transient EE error (attempt %d/%d): %s – retrying in %ds",
                        attempt,
                        max_retries,
                        msg,
                        backoff,
                    )
                    time.sleep(backoff)
                    continue
                # Give up
                self.logger.error(
                    "Failed to getInfo() after %d attempts: %s", attempt, msg
                )
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
        Return an EE ImageCollection filtered by date and region, with optional cloud masking.
        """
        coll = (
            ee.ImageCollection(collection_id)
            .filterDate(start_date, end_date)
            .filterBounds(region)
        )
        if mask_clouds:
            # Use SensorSpec to apply correct cloud mask for this collection
            sensor = SensorSpec.from_collection_id(collection_id)
            coll = coll.map(sensor.cloud_mask)
        return coll


# Convenience singleton
ee_manager = EarthEngineManager()
