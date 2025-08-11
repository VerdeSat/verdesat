from __future__ import annotations

import logging
from pathlib import Path

from verdesat.core.config import ConfigManager
from verdesat.core.storage import LocalFS
from verdesat.schemas.ai_report import AiReportRequest
from verdesat.services.ai_report import AiReportService
from verdesat.services import report

import pandas as pd


class DummyLlm:
    def generate(self, prompt: str, **kwargs):
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


def _write_metrics(storage: LocalFS, path: Path) -> str:
    df = pd.DataFrame(
        {
            "aoi_id": ["a1"],
            "project_id": ["p1"],
            "method_version": ["0.1"],
            "window_start": ["2024-01-01"],
            "window_end": ["2024-12-31"],
        }
    )
    storage.write_bytes(str(path), df.to_csv(index=False).encode("utf-8"))
    return str(path)


def _write_timeseries(storage: LocalFS, path: Path) -> str:
    df = pd.DataFrame(
        {
            "date": ["2024-01-01"],
            "metric": ["ndvi_mean"],
            "value": [0.5],
            "aoi_id": ["a1"],
        }
    )
    storage.write_bytes(str(path), df.to_csv(index=False).encode("utf-8"))
    return str(path)


def test_build_report_with_ai(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    storage = LocalFS()
    svc = AiReportService(
        llm=DummyLlm(),
        storage=storage,
        logger=logging.getLogger("test"),
        config=ConfigManager(),
    )
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
    out_html = tmp_path / "out.html"
    report.build_report(output_path=str(out_html), ai_service=svc, ai_request=req)
    html = out_html.read_text()
    assert "exec" in html
    assert "extent" in html
