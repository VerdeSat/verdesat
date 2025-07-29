from __future__ import annotations

"""Service for retrieving mean MSA values for AOIs."""

from dataclasses import dataclass
from typing import Optional
from shapely.geometry.base import BaseGeometry
from shapely.geometry import mapping

from verdesat.core.storage import LocalFS, StorageAdapter
from verdesat.services.base import BaseService

try:  # pragma: no cover - optional dependency
    import rasterio
    import rasterio.mask
    import rasterio.warp
except ImportError:  # pragma: no cover - optional
    rasterio = None


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


class MSAService(BaseService):
    """Fetch mean Total MSA values from the Globio dataset."""

    DATASET_KEY = "msa/GlobioMSA_2015_cog.tif"

    def __init__(
        self,
        *,
        storage: StorageAdapter | None = None,
        logger=None,
        budget_bytes: int = 50_000_000,
    ) -> None:
        super().__init__(logger)
        self.storage = storage or LocalFS()
        self.budget_bytes = int(budget_bytes)

    def _open_dataset(self, uri: str):
        if rasterio is None:
            raise RuntimeError("rasterio not installed")
        return self.storage.open_raster(uri)

    def mean_msa(self, aoi: BaseGeometry, dataset_uri: Optional[str] = None) -> float:
        """Return mean MSA value of *aoi* from dataset."""
        uri = dataset_uri or self.storage.join(self.DATASET_KEY)
        budget = EgressBudget(self.budget_bytes)
        with self._open_dataset(uri) as src:
            ds = _BudgetDataset(src, budget)
            geom = mapping(aoi)
            if src.crs and src.crs.to_string() != "EPSG:4326":
                geom = rasterio.warp.transform_geom(
                    "EPSG:4326", src.crs.to_string(), geom
                )
            arr, _ = rasterio.mask.mask(ds, [geom], crop=True)
            data = arr[0]
            if hasattr(data, "mask"):
                valid = ~data.mask
                if not valid.any():
                    return float("nan")
                return float(data.data[valid].mean())
            nodata = src.nodata
            if nodata is not None:
                valid = data != nodata
                if not valid.any():
                    return float("nan")
                return float(data[valid].mean())
            return float(data.mean())
