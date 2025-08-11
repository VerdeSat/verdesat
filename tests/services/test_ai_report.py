from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import pandas as pd

from verdesat.adapters.prompt_store import get_prompts
from verdesat.core.config import ConfigManager
from verdesat.core.storage import LocalFS
from verdesat.schemas.ai_report import AiReportRequest
from verdesat.services.ai_report import AiReportService


class DummyLlm:
    """Simple LLM client that records calls."""

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, prompt: str, **kwargs):
        self.calls += 1
        return {
            "executive_summary": "exec",
            "kpi_sentences": {
                "bscore": "bscore sent",
                "intactness": "intact sent",
                "fragmentation": "frag sent",
                "ndvi_trend": "ndvi sent",
            },
            "esrs_e4": {
                "extent_condition": "extent",
                "pressures": "press",
                "targets": "targets",
                "actions": "actions",
                "financial_effects": "effects",
            },
            "flags": [],
            "numbers": {},
            "meta": {},
        }


def _service(llm: DummyLlm, storage: LocalFS) -> AiReportService:
    return AiReportService(
        llm=llm,
        storage=storage,
        logger=logging.getLogger("test"),
        config=ConfigManager(),
    )


def _write_metrics(storage: LocalFS, path: Path) -> str:
    df = pd.DataFrame(
        {
            "aoi_id": ["a1"],
            "project_id": ["p1"],
            "method_version": ["0.1"],
            "window_start": ["2024-01-01"],
            "window_end": ["2024-12-31"],
            "bscore": [50],
            "intactness_pct": [60.0],
            "frag_norm": [0.2],
            "shannon": [1.0],
            "ndvi_mean": [0.5],
            "ndvi_slope_per_year": [0.01],
            "ndvi_delta_yoy": [0.02],
            "valid_obs_pct": [90.0],
            "wdpa_inside": [False],
            "ecoregion": ["Tropical"],
            "elevation_mean_m": [100.0],
        }
    )
    storage.write_bytes(str(path), df.to_csv(index=False).encode("utf-8"))
    return str(path)


def _write_timeseries(storage: LocalFS, path: Path) -> str:
    df = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-02-01"],
            "metric": ["ndvi_mean", "ndvi_mean"],
            "value": [0.5, 0.6],
            "aoi_id": ["a1", "a1"],
        }
    )
    storage.write_bytes(str(path), df.to_csv(index=False).encode("utf-8"))
    return str(path)


def test_compute_hash(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    storage = LocalFS()
    llm = DummyLlm()
    svc = _service(llm, storage)

    metrics = Path("metrics.csv")
    timeseries = Path("ts.csv")
    lineage = Path("lineage.json")
    _write_metrics(storage, metrics)
    _write_timeseries(storage, timeseries)
    storage.write_bytes(str(lineage), b"{}")

    req = AiReportRequest(
        aoi_id="a1",
        project_id="p1",
        metrics_path=str(metrics),
        timeseries_path=str(timeseries),
        lineage_path=str(lineage),
    )

    digest = svc._compute_hash(req, model="model-x", prompt_version="v1")
    prompts = get_prompts("v1")
    expected = hashlib.sha256(
        b"".join(
            [
                metrics.read_bytes(),
                timeseries.read_bytes(),
                lineage.read_bytes(),
                prompts.system.encode("utf-8"),
                prompts.developer.encode("utf-8"),
                prompts.user.encode("utf-8"),
                b"model-x",
            ]
        )
    ).hexdigest()
    assert digest == expected


def test_generate_summary_caches(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    storage = LocalFS()
    llm = DummyLlm()
    svc = _service(llm, storage)

    metrics = Path("metrics.csv")
    timeseries = Path("ts.csv")
    _write_metrics(storage, metrics)
    _write_timeseries(storage, timeseries)

    req = AiReportRequest(
        aoi_id="a1",
        project_id="p1",
        metrics_path=str(metrics),
        timeseries_path=str(timeseries),
    )

    res1 = svc.generate_summary(req)
    assert llm.calls == 1
    assert res1.uri and Path(res1.uri).exists()
    assert res1.summary["executive_summary"] == "exec"
    assert res1.narrative == "exec"

    res2 = svc.generate_summary(req)
    assert llm.calls == 1  # cache hit
    assert res2.summary == res1.summary
    assert res2.narrative == res1.narrative
