from __future__ import annotations

"""Services for computing biodiversity metrics for the web app.

This module wraps the core service layer and exposes a :class:`ComputeService`
that reuses injected dependencies.  It provides helpers for demo AOIs as well
as user uploads.
"""

from pathlib import Path
import tempfile
import os
import pickle
import hashlib
import io
from concurrent.futures import ThreadPoolExecutor

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask as rio_mask
import streamlit as st
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    redis = None

from verdesat.analytics.stats import compute_summary_stats
from verdesat.analytics.timeseries import TimeSeries
from verdesat.services.timeseries import download_timeseries
from verdesat.webapp.services.r2 import signed_url

from verdesat.biodiv.bscore import BScoreCalculator
from verdesat.biodiv.metrics import FragmentStats, MetricEngine, MetricsResult
from verdesat.services.msa import MSAService
from verdesat.geo.aoi import AOI
from verdesat.core.storage import StorageAdapter
from verdesat.project.project import VerdeSatProject
from verdesat.core.config import ConfigManager
from verdesat.core.logger import Logger

CONFIG = ConfigManager(
    str(Path(__file__).resolve().parents[2] / "resources" / "webapp.toml")
)
REDIS_URL = CONFIG.get("cache", {}).get("redis_url")
CACHE_VERSION = "2"  # bump to invalidate incompatible cached results


def _read_remote_raster(key: str, geom: BaseGeometry | None = None) -> np.ndarray:
    """Return the first band of a COG stored on R2 as a float array.

    If ``geom`` is provided, only the window covering the geometry is read,
    reducing I/O and memory usage.
    """

    url = signed_url(key)
    try:
        with rasterio.open(url) as src:
            if geom is not None:
                arr, _ = rio_mask(src, [mapping(geom)], crop=True, nodata=np.nan)
                data = arr[0]
            else:
                arr = src.read(1, masked=True).astype(float)
                data = arr.filled(np.nan)
            return data
    except rasterio.errors.RasterioIOError as exc:
        logger.error("failed to fetch remote raster %s", key)
        raise FileNotFoundError(f"remote raster not found: {key}") from exc


def _df_to_bytes(df: pd.DataFrame) -> io.BytesIO:
    """Return ``df`` as a CSV encoded :class:`io.BytesIO`."""

    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf


def _hash_gdf(gdf: gpd.GeoDataFrame) -> str:
    """Return a stable hash for a GeoDataFrame."""

    return hashlib.sha256(gdf.to_json().encode("utf-8")).hexdigest()


def _cache_path(storage: StorageAdapter, key: str) -> str:
    """Return the path used for persisted caches."""

    return storage.join("cache", f"{key}.pkl")


logger = Logger.get_logger(__name__)


def _persist_cache(storage: StorageAdapter, key: str, value: object) -> None:
    """Persist ``value`` under ``key`` using Redis or the provided storage."""

    data = pickle.dumps(value)
    url = REDIS_URL
    if redis and url:
        try:  # pragma: no cover - network failure
            redis.Redis.from_url(url).set(key, data)
            logger.debug("stored cache %s in Redis", key)
            return
        except Exception:
            logger.exception("failed to persist %s in Redis", key)
    try:  # pragma: no cover - storage failure
        storage.write_bytes(_cache_path(storage, key), data)
        logger.debug("stored cache %s at %s", key, _cache_path(storage, key))
    except Exception:
        logger.exception("failed to persist %s to storage", key)


def _load_cache(storage: StorageAdapter, key: str) -> object | None:
    """Return persisted cache for ``key`` if available."""

    url = REDIS_URL
    if redis and url:
        try:  # pragma: no cover - network failure
            data = redis.Redis.from_url(url).get(key)
            if data:
                logger.debug("loaded cache %s from Redis", key)
                return pickle.loads(data)
        except Exception:
            logger.exception("failed to load cache %s from Redis", key)
    path = _cache_path(storage, key)
    if os.path.exists(path):
        try:  # pragma: no cover - I/O failure
            with open(path, "rb") as fh:
                logger.debug("loaded cache %s from %s", key, path)
                return pickle.loads(fh.read())
        except Exception:
            logger.exception("failed to load cache %s from %s", key, path)
    logger.debug("cache miss for %s", key)
    return None


class ComputeService:
    """Orchestrate metric computations for the web application."""

    def __init__(
        self, msa_service: MSAService, calc: BScoreCalculator, storage: StorageAdapter
    ) -> None:
        self.msa_service = msa_service
        self.calc = calc
        self.storage = storage

    # ------------------------------------------------------------------
    @st.cache_data(hash_funcs={gpd.GeoDataFrame: _hash_gdf})
    def load_demo_metrics(
        _self,
        aoi_id: int,
        gdf: gpd.GeoDataFrame,
        *,
        start_year: int,
        end_year: int,
    ) -> tuple[dict[str, float | str], pd.DataFrame, pd.DataFrame]:
        """Compute metrics and vegetation indices for a demo AOI."""

        self = _self
        logger.info(
            "compute demo metrics for AOI %s (%s-%s)", aoi_id, start_year, end_year
        )
        cache_key = f"demo_{CACHE_VERSION}_{aoi_id}_{start_year}_{end_year}"
        cached = _load_cache(self.storage, cache_key)
        if cached is not None:
            logger.info("demo metrics cache hit for AOI %s", aoi_id)
            return cached  # type: ignore[return-value]

        try:
            geom = gdf.loc[gdf["id"] == aoi_id].geometry.iloc[0]
            try:
                landcover = _read_remote_raster(
                    f"resources/LANDCOVER_{aoi_id}_{end_year}.tiff", geom=geom
                )
            except FileNotFoundError as exc:
                logger.error("missing landcover raster for demo AOI %s", aoi_id)
                raise RuntimeError(f"demo resources missing for AOI {aoi_id}") from exc

            intactness = float(np.isin(landcover, [1, 2, 6]).sum() / landcover.size)

            vals = landcover[~np.isnan(landcover)].astype(int).ravel()
            counts = np.bincount(vals)
            probs = counts[counts > 0] / vals.size
            shannon = float(-np.sum(probs * np.log(probs)))

            edges = np.count_nonzero(
                landcover[:, 1:] != landcover[:, :-1]
            ) + np.count_nonzero(landcover[1:, :] != landcover[:-1, :])
            fragmentation = float(edges / landcover.size)

            ndvi_decomp_url = signed_url(f"resources/decomp/{aoi_id}_decomposition.csv")
            ndvi_decomp_df = pd.read_csv(ndvi_decomp_url, parse_dates=["date"])
            mask = (ndvi_decomp_df["date"].dt.year >= start_year) & (
                ndvi_decomp_df["date"].dt.year <= end_year
            )
            ndvi_decomp_df = ndvi_decomp_df.loc[mask]
            ndvi_ts = ndvi_decomp_df[["date", "observed"]].rename(
                columns={"observed": "mean_ndvi"}
            )
            ndvi_ts["id"] = aoi_id
            ndvi_ts_bytes = _df_to_bytes(ndvi_ts)
            ndvi_decomp_bytes = _df_to_bytes(ndvi_decomp_df)

            msavi_url = signed_url("resources/msavi.csv")
            msavi_df = pd.read_csv(msavi_url, parse_dates=["date"])
            if "id" in msavi_df.columns:
                msavi_df = msavi_df[msavi_df["id"] == aoi_id]
            mask = (msavi_df["date"].dt.year >= start_year) & (
                msavi_df["date"].dt.year <= end_year
            )
            msavi_df = msavi_df.loc[mask]
            msavi_bytes = _df_to_bytes(msavi_df)

            with ThreadPoolExecutor() as ex:
                ndvi_future = ex.submit(
                    compute_summary_stats,
                    ndvi_ts_bytes,
                    decomp_dir={aoi_id: ndvi_decomp_bytes},
                    value_col="mean_ndvi",
                )
                msavi_future = ex.submit(
                    compute_summary_stats,
                    msavi_bytes,
                    value_col="mean_msavi",
                )
                stats_df = ndvi_future.result().to_dataframe()
                msavi_stats_df = msavi_future.result().to_dataframe()

            ndvi_row = stats_df.iloc[0]
            msavi_row = msavi_stats_df.iloc[0]

            msa_val = float("nan")
            try:
                msa_val = self.msa_service.mean_msa(geom)
            except Exception:  # pragma: no cover - network or raster issues
                msa_val = float("nan")

            metrics = MetricsResult(
                intactness=intactness,
                shannon=shannon,
                fragmentation=FragmentStats(
                    edge_density=fragmentation, normalised_density=fragmentation
                ),
                msa=msa_val,
            )
            bscore = self.calc.score(metrics)

            data = {
                "intactness": intactness,
                "shannon": shannon,
                "fragmentation": fragmentation,
                "ndvi_mean": float(ndvi_row["Mean NDVI"]),
                "ndvi_std": float(ndvi_row["Std NDVI"]),
                "ndvi_slope": float(ndvi_row["Sen's Slope (NDVI/yr)"]),
                "ndvi_delta": float(ndvi_row["Trend ΔNDVI"]),
                "ndvi_p_value": float(ndvi_row["Mann–Kendall p-value"]),
                "ndvi_peak": (
                    ndvi_row["Peak Month"] if pd.notna(ndvi_row["Peak Month"]) else ""
                ),
                "ndvi_pct_fill": float(ndvi_row["% Gapfilled"]),
                "msavi_mean": float(msavi_row["Mean MSAVI"]),
                "msavi_std": float(msavi_row["Std MSAVI"]),
                "bscore": bscore,
            }
            result = (data, ndvi_decomp_df, msavi_df)
            _persist_cache(self.storage, cache_key, result)
            logger.info("computed demo metrics for AOI %s", aoi_id)
            return result
        except Exception:
            logger.exception("demo metrics computation failed for AOI %s", aoi_id)
            raise

    # ------------------------------------------------------------------
    def compute_live_metrics(
        _self, gdf: gpd.GeoDataFrame, *, start_year: int, end_year: int
    ) -> tuple[dict[str, float | str], pd.DataFrame, pd.DataFrame]:
        """Compute metrics and vegetation indices for uploaded AOIs."""

        self = _self
        logger.info(
            "compute live metrics for uploaded AOI(s) (%s-%s)", start_year, end_year
        )
        cache_key = f"live_{CACHE_VERSION}_{_hash_gdf(gdf)}_{start_year}_{end_year}"
        cached = _load_cache(self.storage, cache_key)
        if cached is not None:
            logger.info("live metrics cache hit")
            return cached  # type: ignore[return-value]

        try:
            aois = AOI.from_gdf(gdf)
            if len(aois) > 1:
                # Keep project around for potential future use
                config = ConfigManager()
                project = VerdeSatProject("Web Upload", "WebApp", aois, config)
                aois_iter = project.aois
            else:
                aois_iter = aois

            engine = MetricEngine(storage=self.storage)
            records: list[dict[str, float | int]] = []
            for aoi in aois_iter:
                metrics = engine.run_all(aoi, end_year)
                metrics.msa = self.msa_service.mean_msa(aoi.geometry)
                bscore = self.calc.score(metrics)
                records.append(
                    {
                        "id": int(aoi.static_props.get("id", 0)),
                        "intactness": metrics.intactness,
                        "shannon": metrics.shannon,
                        "fragmentation": metrics.fragmentation.normalised_density,
                        "bscore": bscore,
                    }
                )

            df = pd.DataFrame.from_records(records)

            csv_bytes = df.to_csv(index=False).encode("utf-8")
            dest = self.storage.join("results", "live_metrics.csv")
            self.storage.write_bytes(dest, csv_bytes)

            first_gdf = gdf.iloc[[0]]
            with tempfile.TemporaryDirectory() as tmpdir:
                aoi_path = Path(tmpdir) / "aoi.geojson"
                first_gdf.to_file(aoi_path, driver="GeoJSON")
                with ThreadPoolExecutor() as ex:
                    ndvi_future = ex.submit(
                        _ndvi_stats, str(aoi_path), start_year, end_year
                    )
                    msavi_future = ex.submit(
                        _msavi_stats, str(aoi_path), start_year, end_year
                    )
                    ndvi_stats, ndvi_decomp = ndvi_future.result()
                    msavi_stats, msavi_df = msavi_future.result()

            row = df.iloc[0]
            data: dict[str, float | str] = {
                "intactness": float(row["intactness"]),
                "shannon": float(row["shannon"]),
                "fragmentation": float(row["fragmentation"]),
                "bscore": float(row["bscore"]),
            }
            data.update(ndvi_stats)
            data.update(msavi_stats)
            result = (data, ndvi_decomp, msavi_df)
            _persist_cache(self.storage, cache_key, result)
            logger.info("computed live metrics for %s AOI(s)", len(aois))
            return result
        except Exception:
            logger.exception("live metrics computation failed")
            raise


@st.cache_data
def _ndvi_stats(
    aoi_path: str, start_year: int, end_year: int
) -> tuple[dict[str, float | str], pd.DataFrame]:
    """Return NDVI stats and decomposition for ``aoi_path``."""

    ts_df = download_timeseries(
        geojson=aoi_path,
        collection="COPERNICUS/S2_SR_HARMONIZED",
        start=f"{start_year}-01-01",
        end=f"{end_year}-12-31",
        index="ndvi",
        chunk_freq="ME",
        agg="ME",
    )
    ts = TimeSeries.from_dataframe(ts_df, index="ndvi").fill_gaps()
    decomp = ts.decompose(period=12)
    pid = ts.df["id"].iloc[0]
    res = decomp.get(pid)
    if res is None:  # pragma: no cover - requires non-empty series
        raise ValueError("decomposition failed")
    decomp_df = pd.DataFrame(
        {
            "date": res.observed.index,
            "observed": res.observed.values,
            "trend": res.trend.values,
            "seasonal": res.seasonal.values,
            "resid": res.resid.values,
        }
    )
    ts_bytes = _df_to_bytes(ts.df)
    decomp_bytes = _df_to_bytes(decomp_df)
    stats_df = compute_summary_stats(
        ts_bytes, decomp_dir={pid: decomp_bytes}, value_col="mean_ndvi"
    ).to_dataframe()
    row = stats_df.iloc[0]
    stats = {
        "ndvi_mean": float(row["Mean NDVI"]),
        "ndvi_std": float(row["Std NDVI"]),
        "ndvi_slope": float(row["Sen's Slope (NDVI/yr)"]),
        "ndvi_delta": float(row["Trend ΔNDVI"]),
        "ndvi_p_value": float(row["Mann–Kendall p-value"]),
        "ndvi_peak": row["Peak Month"] if pd.notna(row["Peak Month"]) else "",
        "ndvi_pct_fill": float(row["% Gapfilled"]),
    }
    return stats, decomp_df[["date", "observed", "trend", "seasonal"]]


@st.cache_data
def _msavi_stats(
    aoi_path: str, start_year: int, end_year: int
) -> tuple[dict[str, float], pd.DataFrame]:
    """Return MSAVI stats and monthly time series for ``aoi_path``."""

    ts_df = download_timeseries(
        geojson=aoi_path,
        collection="COPERNICUS/S2_SR_HARMONIZED",
        start=f"{start_year}-01-01",
        end=f"{end_year}-12-31",
        index="msavi",
        chunk_freq="ME",
        agg="ME",
    )
    ts = TimeSeries.from_dataframe(ts_df, index="msavi").fill_gaps()
    ts_bytes = _df_to_bytes(ts.df)
    stats_df = compute_summary_stats(ts_bytes, value_col="mean_msavi").to_dataframe()
    row = stats_df.iloc[0]
    stats = {
        "msavi_mean": float(row["Mean MSAVI"]),
        "msavi_std": float(row["Std MSAVI"]),
    }
    return stats, ts.df
