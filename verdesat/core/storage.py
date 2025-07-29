from __future__ import annotations

"""Storage adapter abstractions."""

import os
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlparse


class StorageAdapter(ABC):
    """Abstract interface for persisting binary data."""

    @abstractmethod
    def join(self, *parts: str) -> str:
        """Join path components into a destination URI."""

    @abstractmethod
    def write_bytes(self, uri: str, data: bytes) -> str:
        """Write bytes to the destination and return the URI."""

    @abstractmethod
    def open_raster(self, uri: str, **kwargs):
        """Open *uri* for reading with rasterio."""


class LocalFS(StorageAdapter):
    """Store files on the local filesystem."""

    def join(self, *parts: str) -> str:  # pragma: no cover - trivial
        return os.path.join(*parts)

    def write_bytes(self, uri: str, data: bytes) -> str:
        os.makedirs(os.path.dirname(uri), exist_ok=True)
        with open(uri, "wb") as fh:
            fh.write(data)
        return uri

    def open_raster(self, uri: str, **kwargs):
        """Open a local raster file using rasterio."""
        try:
            import rasterio
        except ImportError as exc:  # pragma: no cover - optional
            raise ImportError("rasterio is required for open_raster") from exc
        return rasterio.open(uri, **kwargs)


class S3Bucket(StorageAdapter):
    """Store files in an S3 bucket using boto3."""

    def __init__(self, bucket: str, client: Any | None = None) -> None:
        try:
            import boto3  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional
            raise ImportError("boto3 is required for S3Bucket") from exc

        self.bucket = bucket
        self.client = client or boto3.client("s3")

    def join(self, *parts: str) -> str:  # pragma: no cover - trivial
        key = "/".join(p.strip("/") for p in parts)
        return f"s3://{self.bucket}/{key}"

    def write_bytes(self, uri: str, data: bytes) -> str:
        parsed = urlparse(uri)
        key = parsed.path.lstrip("/")
        self.client.put_object(Bucket=parsed.netloc or self.bucket, Key=key, Body=data)
        return uri

    def open_raster(self, uri: str, **kwargs):
        """Open an S3 object for reading via rasterio."""
        try:
            import rasterio
        except ImportError as exc:  # pragma: no cover - optional
            raise ImportError("rasterio is required for open_raster") from exc

        parsed = urlparse(uri)
        bucket = parsed.netloc or self.bucket
        key = parsed.path.lstrip("/")
        path = f"/vsis3/{bucket}/{key}"
        return rasterio.open(path, **kwargs)
