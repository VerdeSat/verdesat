"""Project-level computation of metrics for the web application."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
import hashlib
import hmac
import json
import logging
import os
import tempfile
import io
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Tuple, Protocol, Callable, cast

import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping

try:  # pragma: no cover - optional dependency
    import redis  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    redis = None

from verdesat.analytics.stats import compute_summary_stats
from verdesat.analytics.timeseries import TimeSeries
from verdesat.services.timeseries import download_timeseries
from verdesat.biodiv.bscore import BScoreCalculator
from verdesat.biodiv.metrics import MetricEngine
from verdesat.services.msa import MSAService
from verdesat.project.project import Project
from verdesat.geo.aoi import AOI
from verdesat.core.config import ConfigManager
from verdesat.core.logger import Logger
from verdesat.core.storage import StorageAdapter

CONFIG = ConfigManager(
    str(Path(__file__).resolve().parents[2] / "resources" / "webapp.toml")
)
REDIS_URL = CONFIG.get("cache", {}).get("redis_url")
CACHE_SECRET = CONFIG.get("cache", {}).get("secret", "default-secret").encode("utf-8")
logger = Logger.get_logger(__name__)


def _cache_path(storage: StorageAdapter, key: str) -> str:
    """Return path used for persisted caches."""

    return storage.join("cache", f"{key}.json")


def _df_to_bytes(df: pd.DataFrame) -> io.BytesIO:
    """Return ``df`` as CSV in a buffer."""

    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf


@contextmanager
def _suppress_timeseries_logging() -> Iterator[None]:
    """Silence timeseries logs to avoid Streamlit context errors."""

    ts_logger = logging.getLogger("verdesat.services.timeseries")
    prev = ts_logger.level
    ts_logger.setLevel(logging.ERROR)
    try:
        yield
    finally:
        ts_logger.setLevel(prev)


CacheValue = tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, str],
    dict[str, str],
    dict[str, dict[str, float | str]],
]


def _serialize_cache(value: CacheValue) -> str:
    """Return a JSON string representation of *value*."""

    metrics_json = value[0].to_json(orient="split")
    ndvi_json = value[1].to_json(orient="split")
    msavi_json = value[2].to_json(orient="split")
    payload = {
        "metrics_df": metrics_json,
        "ndvi_df": ndvi_json,
        "msavi_df": msavi_json,
        "ndvi_paths": value[3],
        "msavi_paths": value[4],
        "metrics_by_id": value[5],
    }
    return json.dumps(payload, sort_keys=True)


def _deserialize_cache(data: str) -> CacheValue:
    """Deserialize cache *data* into the original value."""

    obj = json.loads(data)
    metrics_df = pd.read_json(io.StringIO(obj["metrics_df"]), orient="split")
    ndvi_df = pd.read_json(io.StringIO(obj["ndvi_df"]), orient="split")
    msavi_df = pd.read_json(io.StringIO(obj["msavi_df"]), orient="split")
    ndvi_paths = obj["ndvi_paths"]
    msavi_paths = obj["msavi_paths"]
    metrics_by_id = obj["metrics_by_id"]
    return metrics_df, ndvi_df, msavi_df, ndvi_paths, msavi_paths, metrics_by_id


def _persist_cache(storage: StorageAdapter, key: str, value: CacheValue) -> None:
    """Persist ``value`` under ``key`` using Redis or storage."""

    data = _serialize_cache(value).encode("utf-8")
    sig = hmac.new(CACHE_SECRET, data, hashlib.sha256).hexdigest()
    payload = json.dumps(
        {"data": data.decode("utf-8"), "sig": sig}, sort_keys=True
    ).encode("utf-8")
    url = REDIS_URL
    if redis and url:
        try:  # pragma: no cover - network failure
            redis.Redis.from_url(url).set(key, payload)
            logger.debug("stored cache %s in Redis", key)
            return
        except Exception:
            logger.exception("failed to persist %s in Redis", key)
    try:  # pragma: no cover - storage failure
        storage.write_bytes(_cache_path(storage, key), payload)
        logger.debug("stored cache %s at %s", key, _cache_path(storage, key))
    except Exception:
        logger.exception("failed to persist %s to storage", key)


def _load_cache(storage: StorageAdapter, key: str) -> object | None:
    """Return persisted cache for ``key`` if available."""

    def _decode(data: bytes) -> CacheValue | None:
        try:
            obj = json.loads(data.decode("utf-8"))
            payload = obj["data"]
            sig = obj["sig"]
        except Exception:
            logger.warning("invalid cache format for %s", key)
            return None
        expected = hmac.new(
            CACHE_SECRET, payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            logger.warning("cache signature mismatch for %s", key)
            return None
        return _deserialize_cache(payload)

    url = REDIS_URL
    if redis and url:
        try:  # pragma: no cover - network failure
            data = redis.Redis.from_url(url).get(key)
            if data:
                logger.debug("loaded cache %s from Redis", key)
                decoded = _decode(data)
                if decoded is not None:
                    return decoded
        except Exception:
            logger.exception("failed to load cache %s from Redis", key)
    path = _cache_path(storage, key)
    if os.path.exists(path):
        try:  # pragma: no cover - I/O failure
            with open(path, "rb") as fh:
                logger.debug("loaded cache %s from %s", key, path)
                decoded = _decode(fh.read())
                if decoded is not None:
                    return decoded
        except Exception:
            logger.exception("failed to load cache %s from %s", key, path)
    logger.debug("cache miss for %s", key)
    return None


def _stats_row_to_dict(row: pd.Series, index: str) -> dict[str, float | str]:
    """Return the required statistics for a vegetation *index*."""

    label = index.upper()
    stats: dict[str, float | str] = {
        f"{index}_mean": float(row[f"Mean {label}"]),
        f"{index}_median": float(row[f"Median {label}"]),
        f"{index}_min": float(row[f"Min {label}"]),
        f"{index}_max": float(row[f"Max {label}"]),
        f"{index}_std": float(row[f"Std {label}"]),
    }
    if index == "ndvi":
        stats.update(
            {
                f"{index}_slope": float(row[f"Sen's Slope ({label}/yr)"]),
                f"{index}_delta": float(row[f"Trend Δ{label}"]),
                f"{index}_p_value": float(row["Mann–Kendall p-value"]),
                f"{index}_peak": (
                    row["Peak Month"] if pd.notna(row["Peak Month"]) else ""
                ),
                "valid_obs_pct": 100.0 - float(row["% Gapfilled"]),
            }
        )
    return stats


def _ndvi_stats(
    aoi_path: str, start_year: int, end_year: int
) -> tuple[dict[str, float | str], pd.DataFrame]:
    """Return NDVI stats and decomposition for ``aoi_path``."""

    with _suppress_timeseries_logging():
        ts_df = download_timeseries(
            geojson=aoi_path,
            collection="COPERNICUS/S2_SR_HARMONIZED",
            start=f"{start_year}-01-01",
            end=f"{end_year}-12-31",
            index="ndvi",
            chunk_freq="YE",
            agg="ME",
        )
    ts = TimeSeries.from_dataframe(ts_df, index="ndvi").fill_gaps()
    decomp = ts.decompose(period=12)
    pid_raw = ts.df["id"].iloc[0]
    pid = int(pid_raw)
    res = decomp.get(str(pid_raw))
    if res is None:
        res = cast(dict[Any, Any], decomp).get(pid)
    if res is not None:
        decomp_df = pd.DataFrame(
            {
                "date": res.observed.index,
                "observed": res.observed.values,
                "trend": res.trend.values,
                "seasonal": res.seasonal.values,
                "resid": res.resid.values,
            }
        )
        decomp_bytes = _df_to_bytes(decomp_df)
        decomp_dir: dict[int, io.BytesIO] | None = {pid: decomp_bytes}
    else:
        decomp_df = pd.DataFrame(
            {
                "date": ts.df["date"],
                "observed": ts.df["mean_ndvi"],
                "trend": float("nan"),
                "seasonal": float("nan"),
            }
        )
        decomp_dir = None

    ts_bytes = _df_to_bytes(ts.df)
    stats_df = compute_summary_stats(
        ts_bytes,
        decomp_dir=decomp_dir,
        value_col="mean_ndvi",
        period=12,
    ).to_dataframe()
    row = stats_df.iloc[0]
    stats = _stats_row_to_dict(row, "ndvi")
    return stats, decomp_df[["date", "observed", "trend", "seasonal"]]


def _msavi_stats(
    aoi_path: str, start_year: int, end_year: int
) -> tuple[dict[str, float | str], pd.DataFrame]:
    """Return MSAVI stats and monthly time series for ``aoi_path``."""

    with _suppress_timeseries_logging():
        ts_df = download_timeseries(
            geojson=aoi_path,
            collection="COPERNICUS/S2_SR_HARMONIZED",
            start=f"{start_year}-01-01",
            end=f"{end_year}-12-31",
            index="msavi",
            chunk_freq="YE",
            agg="ME",
        )
    ts = TimeSeries.from_dataframe(ts_df, index="msavi").fill_gaps()
    ts_bytes = _df_to_bytes(ts.df)
    stats_df = compute_summary_stats(ts_bytes, value_col="mean_msavi").to_dataframe()
    row = stats_df.iloc[0]
    stats = _stats_row_to_dict(row, "msavi")
    return stats, ts.df


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
    def compute(
        _self,
        project: Project,
        start: date,
        end: date,
        progress: Callable[[float], None] | None = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Compute biodiversity metrics and vegetation indices for *project*.

        Results are persisted via :func:`_persist_cache` to avoid
        recomputation.
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
                required = {
                    "ndvi_mean",
                    "ndvi_median",
                    "ndvi_min",
                    "ndvi_max",
                    "ndvi_std",
                    "ndvi_slope",
                    "ndvi_delta",
                    "ndvi_p_value",
                    "ndvi_peak",
                    "valid_obs_pct",
                    "msavi_mean",
                    "msavi_median",
                    "msavi_min",
                    "msavi_max",
                    "msavi_std",
                }
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

        total = len(project.aois)
        if progress:
            progress(0.0)
        for idx, aoi in enumerate(project.aois, start=1):
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

            if progress:
                progress(idx / total)

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
