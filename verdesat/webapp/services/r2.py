"""
verdesat.webapp.services.r2
---------------------------

Helper for generating **presigned URLs** to private Cloudflare‑R2 objects,
so they can be consumed by Titiler (or any HTTP client) without exposing
your secret key in the browser. Credentials are loaded from the
``r2`` section of ``webapp.toml``.

Usage
~~~~~
```python
from verdesat.webapp.services.r2 import signed_url
url = signed_url("resources/NDVI_1_2024-01-01.tif")
```
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import boto3
from botocore.config import Config

from verdesat.core.config import ConfigManager, ConfigValidationError
from verdesat.core.logger import Logger


CONFIG = ConfigManager(
    str(Path(__file__).resolve().parents[2] / "resources" / "webapp.toml")
)
_R2_CFG = CONFIG.get("r2", {})

logger = Logger.get_logger(__name__)


@lru_cache(maxsize=1)
def _client():
    """Return a cached boto3 S3 client configured for Cloudflare R2."""
    endpoint = _R2_CFG.get("endpoint")
    key = _R2_CFG.get("key")
    secret = _R2_CFG.get("secret")
    if not endpoint or not key or not secret:
        raise ConfigValidationError(
            "Missing R2 configuration: endpoint, key, and secret are required"
        )
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
        config=Config(signature_version="s3v4"),
    )


def signed_url(key: str, expires: int = 86_400) -> str:
    """
    Generate a presigned URL for *key* in the bucket defined by R2_BUCKET.

    Parameters
    ----------
    key : str
        Object key inside the bucket, e.g. 'resources/NDVI_1_2024-01-01.tif'
    expires : int
        Expiration in seconds (default: 1 day). Keep it long enough for a
        Streamlit session but short enough to avoid leak risk.

    Returns
    -------
    str
        HTTPS URL with signature & expiry.
    """
    bucket = _R2_CFG.get("bucket", "verdesat-data")
    logger.info("Generating signed URL for %s", key)
    try:
        return _client().generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires,
        )
    except Exception:
        logger.exception("Failed to generate signed URL for %s", key)
        raise


def upload_bytes(key: str, data: bytes, *, content_type: str = "text/csv") -> None:
    """Upload ``data`` to R2 under ``key``."""

    bucket = _R2_CFG.get("bucket", "verdesat-data")
    logger.info("Uploading %s to R2", key)
    try:
        _client().put_object(
            Bucket=bucket, Key=key, Body=data, ContentType=content_type
        )
    except Exception:
        logger.exception("Failed to upload %s", key)
        raise
