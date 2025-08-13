"""Computation of basic biodiversity metrics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Any

import numpy as np
import yaml

from verdesat.services.base import BaseService
from verdesat.services.landcover import LandcoverService
from verdesat.core.storage import StorageAdapter, LocalFS

try:
    import rasterio
except ImportError:  # pragma: no cover - optional dependency
    rasterio = None


@dataclass
class LandcoverResult:
    """In-memory landcover raster."""

    array: np.ndarray
    pixel_size: float = 10.0


@dataclass
class FragmentStats:
    """Edge density statistics."""

    edge_density: float
    frag_norm: float


@dataclass
class MetricsResult:
    """Container for all computed metrics."""

    intactness_pct: float
    shannon: float
    fragmentation: FragmentStats
    msa: float = 0.0


class MetricEngine(BaseService):
    """Compute biodiversity metrics from land-cover rasters."""

    NATURAL_CLASSES = {1, 2, 6}

    def __init__(
        self,
        *,
        storage: StorageAdapter | None = None,
        logger=None,
    ) -> None:
        super().__init__(logger)
        self.storage = storage or LocalFS()
        self.lc_service = LandcoverService(logger=self.logger, storage=self.storage)
        ranges_path = (
            Path(__file__).resolve().parent.parent / "resources" / "edge_ranges.yaml"
        )
        if ranges_path.exists():
            with open(ranges_path, "r", encoding="utf-8") as f:
                self.edge_ranges: Dict[str, Dict[str, Any]] = yaml.safe_load(f) or {}
        else:  # pragma: no cover - unlikely in tests
            self.edge_ranges = {}

    def _read_raster(self, path: str) -> LandcoverResult:
        if rasterio is None:
            raise RuntimeError("rasterio not installed")
        with rasterio.open(path) as src:
            arr = src.read(1).astype(np.int32)
            res = float(src.res[0]) if src.res else 10.0
        return LandcoverResult(arr, res)

    def calc_intactness_pct(self, result: LandcoverResult) -> float:
        """Return percentage of natural pixels (0-100)."""
        mask = np.isin(result.array, list(self.NATURAL_CLASSES))
        frac = float(mask.sum() / result.array.size)
        return frac * 100.0

    def calc_shannon(self, result: LandcoverResult) -> float:
        """Return Shannon diversity index for the raster."""
        vals = result.array.ravel()
        counts = np.bincount(vals)
        probs = counts[counts > 0] / vals.size
        return float(-np.sum(probs * np.log(probs)))

    def calc_fragmentation(
        self, result: LandcoverResult, biome_id: int
    ) -> FragmentStats:
        """Compute edge density and normalised value for *biome_id*."""
        arr = result.array
        edges = 0
        edges += int(np.count_nonzero(arr[:, 1:] != arr[:, :-1]))
        edges += int(np.count_nonzero(arr[1:, :] != arr[:-1, :]))
        edge_density = edges / arr.size
        rng = self.edge_ranges.get(str(biome_id), {"min": 0.0, "max": 1.0})
        min_val = float(rng.get("min", 0.0))
        max_val = float(rng.get("max", 1.0))
        if max_val - min_val > 0:
            norm = (edge_density - min_val) / (max_val - min_val)
        else:
            norm = edge_density
        norm = float(np.clip(norm, 0.0, 1.0))
        return FragmentStats(edge_density=float(edge_density), frag_norm=norm)

    def run_all(
        self, aoi, year: int, *, landcover_path: str | None = None
    ) -> MetricsResult:
        """Compute all metrics for *aoi* in *year*.

        If *landcover_path* is not provided the land‑cover raster is
        downloaded via :class:`LandcoverService`.
        """
        if landcover_path is None:
            with TemporaryDirectory() as tmpdir:
                path = self.lc_service.download(aoi, year, tmpdir)
                lc = self._read_raster(path)
        else:
            lc = self._read_raster(landcover_path)
        intact = self.calc_intactness_pct(lc)
        shannon = self.calc_shannon(lc)
        biome_id = int(aoi.static_props.get("biome_id", 0))
        frag = self.calc_fragmentation(lc, biome_id)
        return MetricsResult(
            intactness_pct=intact,
            shannon=shannon,
            fragmentation=frag,
            msa=0.0,
        )
