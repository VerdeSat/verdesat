from __future__ import annotations

"""Shared helpers for reading remote raster data."""

from dataclasses import dataclass
import os
import sys
from typing import Optional

try:  # pragma: no cover - optional dependency
    import rasterio
except ImportError:  # pragma: no cover - optional
    rasterio = None

from verdesat.core.storage import StorageAdapter


@dataclass
class EgressBudget:
    """Simple byte counter to limit remote reads."""

    remaining: int

    def consume(self, amount: int) -> None:
        self.remaining -= amount
        if self.remaining < 0:
            raise RuntimeError("Egress budget exceeded")


class _BudgetDataset:
    """Wrap a rasterio dataset to track bytes read."""

    def __init__(self, dataset, budget: EgressBudget) -> None:
        self._ds = dataset
        self._budget = budget

    def read(self, *args, **kwargs):
        arr = self._ds.read(*args, **kwargs)
        self._budget.consume(arr.nbytes)
        return arr

    def __getattr__(self, name):  # pragma: no cover - passthrough
        return getattr(self._ds, name)


def open_dataset(
    uri: str,
    storage: StorageAdapter,
    *,
    endpoint: Optional[str] = None,
):
    """Open *uri* within a configured :class:`rasterio.Env`."""

    if rasterio is None:
        raise RuntimeError("rasterio not installed")

    env_opts = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "YES",
        "CPL_VSIL_CURL_USE_HEAD": "NO",
    }

    if uri.startswith("s3://") and endpoint:
        env_opts.update({"AWS_S3_ENDPOINT": endpoint, "AWS_REGION": "auto"})
        if not (os.getenv("R2_KEY") and os.getenv("R2_SECRET")):
            env_opts["AWS_NO_SIGN_REQUEST"] = "YES"

    env = rasterio.Env(**env_opts)
    env.__enter__()
    try:
        ds = storage.open_raster(uri)
    except Exception:
        env.__exit__(*sys.exc_info())
        raise

    class _Dataset:
        def __init__(self, dataset, env):
            self._ds = dataset
            self._env = env

        def close(self):
            try:
                self._ds.close()
            finally:
                self._env.__exit__(None, None, None)

        def __getattr__(self, name):  # pragma: no cover - passthrough
            return getattr(self._ds, name)

        def __enter__(self):  # pragma: no cover - simple wrapper
            return self

        def __exit__(self, exc_type, exc, tb):  # pragma: no cover - simple wrapper
            self.close()
            return False

    return _Dataset(ds, env)
