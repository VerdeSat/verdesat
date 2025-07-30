

"""
verdesat.webapp.services.r2
---------------------------

Helper for generating **presigned URLs** to private Cloudflare‑R2 objects,
so they can be consumed by Titiler (or any HTTP client) without exposing
your secret key in the browser.

Environment variables expected
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
R2_ENDPOINT   – e.g. https://534d0d2f2b8c813de733c916315d3277.r2.cloudflarestorage.com
R2_BUCKET     – default: 'verdesat-data'
R2_KEY        – Cloudflare R2 access key ID
R2_SECRET     – Cloudflare R2 secret

Usage
~~~~~
```python
from verdesat.webapp.services.r2 import signed_url
url = signed_url("resources/NDVI_1_2024-01-01.tif")
```
"""

from __future__ import annotations

import os
from functools import lru_cache

import boto3
from botocore.config import Config


@lru_cache(maxsize=1)
def _client():
    """Return a cached boto3 S3 client configured for Cloudflare R2."""
    return boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT"],
        aws_access_key_id=os.environ["R2_KEY"],
        aws_secret_access_key=os.environ["R2_SECRET"],
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
    bucket = os.getenv("R2_BUCKET", "verdesat-data")
    return _client().generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires,
    )