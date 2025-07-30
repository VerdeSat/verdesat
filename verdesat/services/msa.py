from __future__ import annotations

"""Service for retrieving mean MSA values for AOIs."""

from typing import Optional
import logging
import sys
from pandas import DataFrame
from shapely.geometry.base import BaseGeometry
from shapely.geometry import mapping

from verdesat.core.storage import LocalFS, StorageAdapter
from verdesat.services.base import BaseService
from verdesat.core.logger import Logger
from verdesat.geo.aoi import AOI
from verdesat.services.raster_reader import (
    EgressBudget,
    _BudgetDataset,
    open_dataset,
)

try:  # pragma: no cover - optional dependency
    import rasterio
    import rasterio.mask
    import rasterio.warp
except ImportError:  # pragma: no cover - optional
    rasterio = None


class MSAService(BaseService):
    """Fetch mean Total MSA values from the Globio dataset."""

    # Cloudflare R2 endpoint (scheme-less; GDAL prepends the bucket)
    R2_ENDPOINT = "534d0d2f2b8c813de733c916315d3277.r2.cloudflarestorage.com"

    # ``s3://`` URI so that rasterio uses GDAL's ``/vsis3`` driver. Query
    # parameters configure unsigned access. Endpoint is set by environment.
    DEFAULT_DATASET_URI = "s3://verdesat-data/msa/GlobioMSA_2015_cog.tif"

    def __init__(
        self,
        *,
        storage: StorageAdapter | None = None,
        logger=None,
        budget_bytes: int = 50_000_000,
        dataset_uri: str | None = None,
    ) -> None:
        super().__init__(logger)
        self.storage = storage or LocalFS()
        self.budget_bytes = int(budget_bytes)
        self.dataset_uri = dataset_uri or self.DEFAULT_DATASET_URI

    def mean_msa(self, aoi: BaseGeometry, dataset_uri: Optional[str] = None) -> float:
        """Return mean MSA value of *aoi* from dataset."""
        uri = dataset_uri or self.dataset_uri
        budget = EgressBudget(self.budget_bytes)
        with open_dataset(uri, self.storage, endpoint=self.R2_ENDPOINT) as src:
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


def compute_msa_means(
    geojson: str,
    *,
    dataset_uri: str | None = None,
    budget_bytes: int = 50_000_000,
    logger: logging.Logger | None = None,
    storage: StorageAdapter | None = None,
    output: str | None = None,
) -> DataFrame:
    """Compute mean MSA values for features in ``geojson``.

    Parameters
    ----------
    geojson:
        Path to an AOI GeoJSON file with an ``id`` property.
    dataset_uri:
        Optional URI of the Globio MSA raster. Defaults to
        :data:`MSAService.DEFAULT_DATASET_URI`.
    budget_bytes:
        Maximum bytes allowed to be read from the dataset.
    logger:
        Optional :class:`logging.Logger` for progress messages.
    storage:
        Storage backend used to open the dataset.
    output:
        Optional CSV output path.
    """

    import pandas as pd  # imported lazily for optional dependency

    log = logger or Logger.get_logger(__name__)
    log.info("Loading AOIs from %s", geojson)
    aois = AOI.from_geojson(geojson, id_col="id")

    svc = MSAService(
        storage=storage or LocalFS(),
        logger=log,
        budget_bytes=budget_bytes,
    )

    records = []
    for aoi in aois:
        val = svc.mean_msa(aoi.geometry, dataset_uri=dataset_uri)
        records.append({"id": aoi.static_props.get("id"), "mean_msa": val})

    df = pd.DataFrame.from_records(records)
    if output:
        log.info("Writing results to %s", output)
        df.to_csv(output, index=False)
    return df
