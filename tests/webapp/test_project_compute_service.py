from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd
from shapely.geometry import Polygon

from verdesat.project.project import Project
from verdesat.geo.aoi import AOI
from verdesat.core.config import ConfigManager
from verdesat.core.storage import LocalFS

from verdesat.webapp.services import project_compute
from verdesat.webapp.services.project_compute import ProjectComputeService
from verdesat.biodiv.metrics import MetricsResult, FragmentStats


class DummyChipService:
    def __init__(self) -> None:
        self.calls: list[tuple[AOI, int, LocalFS]] = []

    def download_chips(self, aoi: AOI, year: int, storage: LocalFS):
        self.calls.append((aoi, year, storage))
        aoi_id = aoi.static_props["id"]
        return {
            "ndvi": f"ndvi_{aoi_id}.tif",
            "msavi": f"msavi_{aoi_id}.tif",
        }


class DummyMSA:
    def mean_msa(self, geom):  # pragma: no cover - simple
        return 0.5


class DummyBScore:
    def score(self, metrics):  # pragma: no cover - simple
        return 42.0


def make_project() -> Project:
    aoi1 = AOI(Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]), {"id": "1"})
    aoi2 = AOI(Polygon([(1, 1), (2, 1), (2, 2), (1, 2)]), {"id": "2"})
    cfg = ConfigManager()
    storage = LocalFS()
    return Project("Test", "Cust", [aoi1, aoi2], cfg, storage=storage)


def test_compute_invokes_chip_service_and_aggregates(monkeypatch):
    project = make_project()
    chip_service = DummyChipService()
    svc = ProjectComputeService(
        DummyMSA(),
        DummyBScore(),
        project.storage,  # type: ignore[arg-type]
        chip_service,  # type: ignore[arg-type]
        project.config,
    )

    # patch heavy helpers
    metrics = MetricsResult(0.1, 0.2, FragmentStats(0.3, 0.4), msa=0.0)

    def fake_run_all(self, aoi, year):
        return metrics

    monkeypatch.setattr(project_compute.MetricEngine, "run_all", fake_run_all)

    def fake_ndvi(path, s, e):
        return (
            {
                "ndvi_mean": 1.0,
                "ndvi_std": 0.1,
                "ndvi_slope": 0.0,
                "ndvi_delta": 0.0,
                "ndvi_p_value": 0.5,
                "ndvi_peak": "Jan",
                "ndvi_pct_fill": 0.0,
            },
            pd.DataFrame(
                {
                    "date": [s],
                    "observed": [0.1],
                    "trend": [0.1],
                    "seasonal": [0.1],
                }
            ),
        )

    def fake_msavi(path, s, e):
        return (
            {"msavi_mean": 2.0, "msavi_std": 0.2},
            pd.DataFrame({"date": [s], "mean_msavi": [0.2]}),
        )

    monkeypatch.setattr(project_compute, "_ndvi_stats", fake_ndvi)
    monkeypatch.setattr(project_compute, "_msavi_stats", fake_msavi)
    monkeypatch.setattr(project_compute, "_load_cache", lambda storage, key: None)

    persisted: dict = {}

    def fake_persist(storage, key, value):
        persisted["key"] = key
        persisted["value"] = value

    monkeypatch.setattr(project_compute, "_persist_cache", fake_persist)

    metrics_df, ndvi_df, msavi_df = svc.compute(
        project, date(2024, 1, 1), date(2024, 12, 31)
    )

    assert len(chip_service.calls) == 2
    assert chip_service.calls[0][2] is project.storage
    assert set(project.rasters.keys()) == {"1", "2"}
    assert "1" in project.metrics
    assert metrics_df.shape[0] == 2
    assert not ndvi_df.empty and not msavi_df.empty
    assert persisted["key"].startswith("project_")
    cached_val = persisted["value"]
    assert isinstance(cached_val, tuple) and len(cached_val) == 6


def test_compute_uses_cache(monkeypatch):
    project = make_project()
    chip_service = DummyChipService()
    svc = ProjectComputeService(
        DummyMSA(),
        DummyBScore(),
        project.storage,  # type: ignore[arg-type]
        chip_service,  # type: ignore[arg-type]
        project.config,
    )

    cached = (
        pd.DataFrame(
            {
                "id": ["1"],
                "ndvi_mean": [1.0],
                "ndvi_std": [0.1],
                "ndvi_slope": [0.0],
                "ndvi_delta": [0.0],
                "ndvi_p_value": [0.5],
                "ndvi_peak": ["Jan"],
                "ndvi_pct_fill": [0.0],
                "msavi_mean": [2.0],
                "msavi_std": [0.2],
            }
        ),
        pd.DataFrame(),
        pd.DataFrame(),
        {"1": "ndvi_1.tif"},
        {"1": "msavi_1.tif"},
        {
            "1": {
                "id": "1",
                "ndvi_mean": 1.0,
                "ndvi_std": 0.1,
                "ndvi_slope": 0.0,
                "ndvi_delta": 0.0,
                "ndvi_p_value": 0.5,
                "ndvi_peak": "Jan",
                "ndvi_pct_fill": 0.0,
                "msavi_mean": 2.0,
                "msavi_std": 0.2,
            }
        },
    )
    project_compute.ProjectComputeService.compute.clear()
    monkeypatch.setattr(project_compute, "_load_cache", lambda storage, key: cached)

    result = svc.compute(project, date(2024, 1, 1), date(2024, 12, 31))
    assert result == cached[:3]
    assert project.rasters["1"]["ndvi"] == "ndvi_1.tif"
    assert not chip_service.calls


def test_compute_recomputes_legacy_cache(monkeypatch):
    """Older cache tuples trigger recomputation so VI stats are present."""
    project = make_project()
    chip_service = DummyChipService()
    svc = ProjectComputeService(
        DummyMSA(),
        DummyBScore(),
        project.storage,  # type: ignore[arg-type]
        chip_service,  # type: ignore[arg-type]
        project.config,
    )

    legacy_cached = (
        pd.DataFrame({"id": ["1"]}),
        pd.DataFrame(),
        pd.DataFrame(),
    )
    project_compute.ProjectComputeService.compute.clear()
    monkeypatch.setattr(
        project_compute, "_load_cache", lambda storage, key: legacy_cached
    )

    metrics = MetricsResult(0.1, 0.2, FragmentStats(0.3, 0.4), msa=0.0)

    def fake_run_all(self, aoi, year):
        return metrics

    monkeypatch.setattr(project_compute.MetricEngine, "run_all", fake_run_all)

    def fake_ndvi(path, s, e):  # pragma: no cover - simple
        return (
            {
                "ndvi_mean": 1.0,
                "ndvi_std": 0.1,
                "ndvi_slope": 0.0,
                "ndvi_delta": 0.0,
                "ndvi_p_value": 0.5,
                "ndvi_peak": "Jan",
                "ndvi_pct_fill": 0.0,
            },
            pd.DataFrame(
                {
                    "date": [s],
                    "observed": [0.1],
                    "trend": [0.1],
                    "seasonal": [0.1],
                }
            ),
        )

    def fake_msavi(path, s, e):  # pragma: no cover - simple
        return (
            {"msavi_mean": 2.0, "msavi_std": 0.2},
            pd.DataFrame({"date": [s], "mean_msavi": [0.2]}),
        )

    monkeypatch.setattr(project_compute, "_ndvi_stats", fake_ndvi)
    monkeypatch.setattr(project_compute, "_msavi_stats", fake_msavi)

    metrics_df, *_ = svc.compute(project, date(2024, 1, 1), date(2024, 12, 31))
    # Recompute should call chip service and include VI stats
    assert chip_service.calls
    required = {
        "ndvi_mean",
        "ndvi_std",
        "ndvi_slope",
        "ndvi_delta",
        "ndvi_p_value",
        "ndvi_peak",
        "ndvi_pct_fill",
        "msavi_mean",
        "msavi_std",
    }
    assert required <= set(metrics_df.columns)


def test_ndvi_stats_returns_required_metrics(monkeypatch):
    df = pd.DataFrame(
        {"id": [1], "date": [pd.Timestamp("2020-01-01")], "mean_ndvi": [0.2]}
    )
    monkeypatch.setattr(project_compute, "download_timeseries", lambda *a, **k: df)

    class DummyTS:
        def __init__(self, df: pd.DataFrame):
            self.df = df

        @classmethod
        def from_dataframe(cls, df: pd.DataFrame, index: str):
            return cls(df)

        def fill_gaps(self):
            return self

        def decompose(self, period: int):
            series = SimpleNamespace(index=df["date"], values=df["mean_ndvi"])
            return {
                df["id"].iloc[0]: SimpleNamespace(
                    observed=series, trend=series, seasonal=series, resid=series
                )
            }

    monkeypatch.setattr(project_compute, "TimeSeries", DummyTS)

    stats_df = pd.DataFrame(
        {
            "Mean NDVI": [0.2],
            "Std NDVI": [0.1],
            "Sen's Slope (NDVI/yr)": [0.0],
            "Trend ΔNDVI": [0.0],
            "Mann–Kendall p-value": [0.5],
            "Peak Month": ["Jan"],
            "% Gapfilled": [0.0],
        }
    )
    monkeypatch.setattr(
        project_compute,
        "compute_summary_stats",
        lambda *a, **k: SimpleNamespace(to_dataframe=lambda: stats_df),
    )

    stats, df_out = project_compute._ndvi_stats("dummy.geojson", 2020, 2020)
    assert set(stats.keys()) == {
        "ndvi_mean",
        "ndvi_std",
        "ndvi_slope",
        "ndvi_delta",
        "ndvi_p_value",
        "ndvi_peak",
        "ndvi_pct_fill",
    }
    assert list(df_out.columns) == ["date", "observed", "trend", "seasonal"]


def test_msavi_stats_returns_required_metrics(monkeypatch):
    df = pd.DataFrame(
        {"id": [1], "date": [pd.Timestamp("2020-01-01")], "mean_msavi": [0.3]}
    )
    monkeypatch.setattr(project_compute, "download_timeseries", lambda *a, **k: df)

    class DummyTS:
        def __init__(self, df: pd.DataFrame):
            self.df = df

        @classmethod
        def from_dataframe(cls, df: pd.DataFrame, index: str):
            return cls(df)

        def fill_gaps(self):
            return self

    monkeypatch.setattr(project_compute, "TimeSeries", DummyTS)

    stats_df = pd.DataFrame({"Mean MSAVI": [0.3], "Std MSAVI": [0.1]})
    monkeypatch.setattr(
        project_compute,
        "compute_summary_stats",
        lambda *a, **k: SimpleNamespace(to_dataframe=lambda: stats_df),
    )

    stats, ts_df = project_compute._msavi_stats("dummy.geojson", 2020, 2020)
    assert stats == {"msavi_mean": 0.3, "msavi_std": 0.1}
    assert ts_df.equals(df)
