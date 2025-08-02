from __future__ import annotations

import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
from dataclasses import fields

from verdesat.webapp.components.kpi_cards import Metrics
from verdesat.webapp.services.compute import ComputeService
from verdesat.biodiv.bscore import BScoreCalculator
from verdesat.services.msa import MSAService
from verdesat.core.storage import StorageAdapter
from verdesat.biodiv.metrics import MetricsResult, FragmentStats


class DummyMSA(MSAService):
    """Stub MSAService returning a constant value."""

    def __init__(self) -> None:  # pragma: no cover - simple
        pass

    def mean_msa(self, aoi, dataset_uri=None):  # type: ignore[override]
        self.called = True
        return 0.7


class DummyCalc(BScoreCalculator):
    """Stub calculator returning a fixed score."""

    def __init__(self) -> None:  # pragma: no cover - simple
        pass

    def score(self, metrics):  # type: ignore[override]
        self.last_metrics = metrics
        return 42.0


class DummyStorage(StorageAdapter):
    """In-memory storage capturing writes."""

    def __init__(self) -> None:  # pragma: no cover - simple
        self.writes: list[tuple[str, bytes]] = []

    def join(self, *parts: str) -> str:  # pragma: no cover - simple
        return "/".join(parts)

    def write_bytes(self, uri: str, data: bytes) -> str:  # pragma: no cover - simple
        self.writes.append((uri, data))
        return uri

    def open_raster(self, uri: str, **kwargs):  # pragma: no cover - unused
        raise NotImplementedError


def test_compute_live_metrics_single_aoi(monkeypatch):
    """Service should use injected dependencies and storage."""

    gdf = gpd.GeoDataFrame(
        {"geometry": [Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])]},
        crs="EPSG:4326",
    )

    metrics_stub = MetricsResult(
        intactness=0.5,
        shannon=0.3,
        fragmentation=FragmentStats(edge_density=0.1, normalised_density=0.2),
        msa=0.0,
    )
    monkeypatch.setattr(
        "verdesat.webapp.services.compute.MetricEngine.run_all",
        lambda self, aoi, year: metrics_stub,
    )
    ndvi_stats = {
        "ndvi_mean": 1.0,
        "ndvi_std": 0.1,
        "ndvi_slope": 0.01,
        "ndvi_delta": 0.02,
        "ndvi_p_value": 0.5,
        "ndvi_peak": "2020-06",
        "ndvi_pct_fill": 95.0,
    }
    ndvi_df = pd.DataFrame(
        {
            "date": [pd.Timestamp("2020-01-01")],
            "observed": [0.1],
            "trend": [0.1],
            "seasonal": [0.1],
        }
    )
    msavi_stats = {"msavi_mean": 2.0, "msavi_std": 0.2}
    msavi_df = pd.DataFrame({"date": [pd.Timestamp("2020-01-01")], "msavi": [0.2]})
    monkeypatch.setattr(
        "verdesat.webapp.services.compute._ndvi_stats",
        lambda *args, **kwargs: (ndvi_stats, ndvi_df),
    )
    monkeypatch.setattr(
        "verdesat.webapp.services.compute._msavi_stats",
        lambda *args, **kwargs: (msavi_stats, msavi_df),
    )

    msa = DummyMSA()
    calc = DummyCalc()
    storage = DummyStorage()
    svc = ComputeService(msa, calc, storage)

    metrics_df, ndvi_stats_out, ndvi_out, msavi_stats_out, msavi_out = (
        svc.compute_live_metrics(gdf, start_year=2020, end_year=2021)
    )

    row = metrics_df.iloc[0].to_dict()
    row.update(ndvi_stats_out)
    row.update(msavi_stats_out)
    field_names = {f.name for f in fields(Metrics)}
    data = {k: row[k] for k in field_names}
    metrics = Metrics(**data)

    assert metrics.bscore == 42.0
    assert msa.called
    assert calc.last_metrics.msa == 0.7
    assert storage.writes
    assert "ndvi_mean" in ndvi_stats_out
    assert "msavi_mean" in msavi_stats_out
    assert isinstance(ndvi_out, pd.DataFrame)
    assert isinstance(msavi_out, pd.DataFrame)


def test_compute_live_metrics_multi_aoi_project(monkeypatch):
    """Multiple AOIs should be wrapped in a project."""

    gdf = gpd.GeoDataFrame(
        {
            "geometry": [
                Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
                Polygon([(2, 0), (3, 0), (3, 1), (2, 1)]),
            ]
        },
        crs="EPSG:4326",
    )

    metrics_stub = MetricsResult(
        intactness=0.5,
        shannon=0.3,
        fragmentation=FragmentStats(edge_density=0.1, normalised_density=0.2),
        msa=0.0,
    )
    monkeypatch.setattr(
        "verdesat.webapp.services.compute.MetricEngine.run_all",
        lambda self, aoi, year: metrics_stub,
    )
    monkeypatch.setattr(
        "verdesat.webapp.services.compute._ndvi_stats",
        lambda *a, **k: ({"ndvi_mean": 1.0}, pd.DataFrame()),
    )
    monkeypatch.setattr(
        "verdesat.webapp.services.compute._msavi_stats",
        lambda *a, **k: ({"msavi_mean": 2.0}, pd.DataFrame()),
    )

    created: dict[str, list] = {}

    class DummyProject:
        def __init__(self, name, customer, aois, config):  # pragma: no cover - simple
            created["aois"] = aois
            self.aois = aois

    monkeypatch.setattr(
        "verdesat.webapp.services.compute.VerdeSatProject", DummyProject
    )

    svc = ComputeService(DummyMSA(), DummyCalc(), DummyStorage())
    svc.compute_live_metrics(gdf, start_year=2020, end_year=2021)

    assert len(created["aois"]) == 2
