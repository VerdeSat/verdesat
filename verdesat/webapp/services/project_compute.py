from __future__ import annotations

"""Project-level computation of metrics for the web application."""

from datetime import date
import hashlib
import json
import logging
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Tuple, Protocol, cast

import geopandas as gpd
import pandas as pd
import streamlit as st
from shapely.geometry import mapping

from verdesat.biodiv.bscore import BScoreCalculator
from verdesat.biodiv.metrics import MetricEngine
from verdesat.services.msa import MSAService
from verdesat.project.project import Project
from verdesat.geo.aoi import AOI
from verdesat.core.config import ConfigManager
from verdesat.core.logger import Logger
from verdesat.core.storage import StorageAdapter

from .compute import _load_cache, _persist_cache, _ndvi_stats, _msavi_stats


class ChipService(Protocol):
    """Protocol for services providing chip downloads."""

    def download_chips(
        self, aoi: AOI, year: int, storage: StorageAdapter
    ) -> Dict[str, str]:
        """Return mapping of index name to raster path."""


class ProjectComputeService:
    """Compute metrics and vegetation indices for an entire project."""

    def __init__(
        self,
        msa_service: MSAService,
        bscore_calc: BScoreCalculator,
        storage: StorageAdapter,
        chip_service: ChipService,
        config: ConfigManager,
        logger: logging.Logger | None = None,
    ) -> None:
        self.msa_service = msa_service
        self.bscore_calc = bscore_calc
        self.storage = storage
        self.chip_service = chip_service
        self.config = config
        self.logger = logger or Logger.get_logger(__name__)

    # ------------------------------------------------------------------
    @staticmethod
    def _hash_project(project: Project) -> str:
        """Return SHA256 hash of a project's AOI GeoJSON."""

        features = [
            {
                "type": "Feature",
                "geometry": mapping(aoi.geometry),
                "properties": aoi.static_props,
            }
            for aoi in project.aois
        ]
        geojson = json.dumps(
            {"type": "FeatureCollection", "features": features}, sort_keys=True
        )
        return hashlib.sha256(geojson.encode("utf-8")).hexdigest()

    def _project_hash(self, project: Project) -> str:
        return self._hash_project(project)

    # ------------------------------------------------------------------
    @st.cache_data(
        show_spinner=False,
        hash_funcs={
            Project: _hash_project,
            MSAService: lambda _svc: 0,
            BScoreCalculator: lambda _svc: 0,
            StorageAdapter: lambda _svc: 0,
            ChipService: lambda _svc: 0,
            ConfigManager: lambda _svc: 0,
            Logger: lambda _svc: 0,
        },
    )
    def compute(
        _self, project: Project, start: date, end: date
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Compute biodiversity metrics and vegetation indices for *project*.

        Results are cached both in-memory via Streamlit and persisted via
        :func:`_persist_cache` to avoid recomputation.
        """

        cache_key = f"project_{_self._project_hash(project)}_{start}_{end}"
        cached = _load_cache(_self.storage, cache_key)
        if cached is not None:
            _self.logger.info("project metrics cache hit")
            try:
                (
                    metrics_df,
                    ndvi_df,
                    msavi_df,
                    cached_ndvi_paths,
                    cached_msavi_paths,
                    cached_metrics_by_id,
                ) = cast(
                    tuple[
                        pd.DataFrame,
                        pd.DataFrame,
                        pd.DataFrame,
                        Dict[str, str],
                        Dict[str, str],
                        Dict[str, dict[str, float | str]],
                    ],
                    cached,
                )
            except ValueError:
                _self.logger.warning("legacy cache format detected; recomputing")
            else:
                required = {"ndvi_mean", "msavi_mean"}
                if required.issubset(metrics_df.columns):
                    project.attach_rasters(cached_ndvi_paths, cached_msavi_paths)
                    project.attach_metrics(cached_metrics_by_id)
                    return metrics_df, ndvi_df, msavi_df
                _self.logger.warning("cache missing VI stats; recomputing")

        id_col = _self.config.get("id_col", "id")
        ndvi_paths: Dict[str, str] = {}
        msavi_paths: Dict[str, str] = {}
        metrics_records: list[dict[str, float | str]] = []
        ndvi_frames: list[pd.DataFrame] = []
        msavi_frames: list[pd.DataFrame] = []
        metrics_by_id: Dict[str, dict[str, float | str]] = {}

        engine = MetricEngine(storage=_self.storage)

        for aoi in project.aois:
            aoi_id = str(aoi.static_props.get(id_col))

            existing = project.rasters.get(aoi_id, {})
            ndvi_path = existing.get("ndvi")
            msavi_path = existing.get("msavi")
            if not ndvi_path or not msavi_path:
                chip_paths = _self.chip_service.download_chips(
                    aoi, year=end.year, storage=_self.storage
                )
                ndvi_path = ndvi_path or chip_paths.get("ndvi", "")
                msavi_path = msavi_path or chip_paths.get("msavi", "")
            ndvi_paths[aoi_id] = ndvi_path or ""
            msavi_paths[aoi_id] = msavi_path or ""

            metrics = engine.run_all(aoi, end.year)
            metrics.msa = _self.msa_service.mean_msa(aoi.geometry)
            bscore = _self.bscore_calc.score(metrics)

            with tempfile.TemporaryDirectory() as tmpdir:
                gdf = gpd.GeoDataFrame(
                    [{id_col: aoi_id, "geometry": aoi.geometry}], crs="EPSG:4326"
                )
                aoi_path = Path(tmpdir) / "aoi.geojson"
                gdf.to_file(aoi_path, driver="GeoJSON")

                with ThreadPoolExecutor() as ex:
                    ndvi_future = ex.submit(
                        _ndvi_stats, str(aoi_path), start.year, end.year
                    )
                    msavi_future = ex.submit(
                        _msavi_stats, str(aoi_path), start.year, end.year
                    )
                    ndvi_stats, ndvi_df_single = ndvi_future.result()
                    msavi_stats, msavi_df_single = msavi_future.result()

            record: dict[str, float | str] = {
                "id": aoi_id,
                "intactness": metrics.intactness,
                "shannon": metrics.shannon,
                "fragmentation": metrics.fragmentation.normalised_density,
                "msa": metrics.msa,
                "bscore": bscore,
            }
            record.update(ndvi_stats)
            record.update(msavi_stats)
            metrics_records.append(record)
            metrics_by_id[aoi_id] = record

            ndvi_df_single = ndvi_df_single.copy()
            ndvi_df_single["id"] = aoi_id
            ndvi_frames.append(ndvi_df_single)

            msavi_df_single = msavi_df_single.copy()
            msavi_df_single["id"] = aoi_id
            msavi_frames.append(msavi_df_single)

        metrics_df = pd.DataFrame.from_records(metrics_records)
        ndvi_df = pd.concat(ndvi_frames, ignore_index=True)
        msavi_df = pd.concat(msavi_frames, ignore_index=True)

        project.attach_rasters(ndvi_paths, msavi_paths)
        project.attach_metrics(metrics_by_id)

        cache_value = (
            metrics_df,
            ndvi_df,
            msavi_df,
            ndvi_paths,
            msavi_paths,
            metrics_by_id,
        )
        _persist_cache(_self.storage, cache_key, cache_value)
        return metrics_df, ndvi_df, msavi_df
