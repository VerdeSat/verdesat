"""Tests for :mod:`verdesat.services.ai_report`."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any

import pandas as pd
import pytest
from pydantic import ValidationError

from verdesat.adapters.llm_openai import OpenAiLlmClient
from verdesat.adapters.prompt_store import get_prompts
from verdesat.core.config import ConfigManager
from verdesat.core.storage import StorageAdapter, LocalFS
from verdesat.schemas.ai_report import AiReportRequest
from verdesat.services.ai_report import AiReportService


class FakeStorage(StorageAdapter):
    """In-memory :class:`StorageAdapter` for tests."""

    def __init__(self) -> None:  # pragma: no cover - trivial
        self.files: dict[str, bytes] = {}
        self.reads = 0
        self.writes = 0

    def join(self, *parts: str) -> str:  # pragma: no cover - trivial
        return "/".join(p.strip("/") for p in parts)

    def write_bytes(self, uri: str, data: bytes) -> str:
        self.writes += 1
        self.files[uri] = data
        return uri

    def read_bytes(self, uri: str) -> bytes:
        self.reads += 1
        try:
            return self.files[uri]
        except KeyError as exc:  # pragma: no cover - defensive
            raise FileNotFoundError(uri) from exc

    def open_raster(self, uri: str, **kwargs):  # pragma: no cover - not used
        raise NotImplementedError


class RecordingLlm:
    """LLM stub that records the last prompt and kwargs."""

    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.calls = 0
        self.last_prompt: str | None = None
        self.last_kwargs: dict[str, Any] = {}

    def generate(self, prompt: str, **kwargs: Any) -> Any:  # pragma: no cover - simple
        self.calls += 1
        self.last_prompt = prompt
        self.last_kwargs = kwargs
        return self.payload


class SchemaLlm(RecordingLlm):
    """LLM stub that validates against provided Pydantic model."""

    def generate(self, prompt: str, **kwargs: Any) -> Any:
        self.calls += 1
        self.last_prompt = prompt
        self.last_kwargs = kwargs
        model = kwargs["response_model"]
        if isinstance(self.payload, str):
            return model.model_validate_json(self.payload).model_dump()
        return model.model_validate(self.payload).model_dump()


def _service(llm: RecordingLlm, storage: StorageAdapter) -> AiReportService:
    return AiReportService(
        llm=llm,
        storage=storage,
        logger=logging.getLogger("test"),
        config=ConfigManager(),
    )


def _write_metrics(storage: FakeStorage, path: str) -> str:
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
    storage.write_bytes(path, df.to_csv(index=False).encode("utf-8"))
    return path


def _write_timeseries(storage: FakeStorage, path: str) -> str:
    df = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-02-01"],
            "metric": ["ndvi_mean", "ndvi_mean"],
            "value": [0.5, 0.6],
            "aoi_id": ["a1", "a1"],
        }
    )
    storage.write_bytes(path, df.to_csv(index=False).encode("utf-8"))
    return path


def test_compute_hash():
    storage = FakeStorage()
    llm = RecordingLlm({})
    svc = _service(llm, storage)

    metrics = _write_metrics(storage, "metrics.csv")
    timeseries = _write_timeseries(storage, "ts.csv")
    lineage_path = "lineage.json"
    storage.write_bytes(lineage_path, b"{}")

    req = AiReportRequest(
        aoi_id="a1",
        project_id="p1",
        metrics_path=metrics,
        timeseries_path=timeseries,
        lineage_path=lineage_path,
    )

    digest = svc._compute_hash(req, model="model-x", prompt_version="v1")
    prompts = get_prompts("v1")
    expected = hashlib.sha256(
        b"".join(
            [
                storage.files[metrics],
                storage.files[timeseries],
                storage.files[lineage_path],
                prompts.system.encode("utf-8"),
                prompts.developer.encode("utf-8"),
                prompts.user.encode("utf-8"),
                b"model-x",
            ]
        )
    ).hexdigest()
    assert digest == expected


def test_prompt_assembly_golden():
    storage = FakeStorage()
    payload = {
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
    llm = RecordingLlm(payload)
    svc = _service(llm, storage)

    metrics = _write_metrics(storage, "metrics.csv")
    timeseries = _write_timeseries(storage, "ts.csv")

    req = AiReportRequest(
        aoi_id="a1",
        project_id="p1",
        metrics_path=metrics,
        timeseries_path=timeseries,
    )

    svc.generate_summary(req)
    prompts = get_prompts("v1")
    metrics_csv = pd.read_csv(pd.io.common.BytesIO(storage.files[metrics])).to_csv(
        index=False
    ).strip()
    ts_df = pd.read_csv(pd.io.common.BytesIO(storage.files[timeseries]))
    ts_df["date"] = pd.to_datetime(ts_df["date"]).dt.to_period("M").astype(str)
    timeseries_str = "\n".join(
        f"{r.date},{r.value:.3f}" for r in ts_df.sort_values("date").itertuples()
    )
    context = "ecoregion=Tropical, elevation_mean_m=100.0, wdpa_inside=False"
    user_prompt = prompts.user.format(
        aoi_id="a1",
        project_id="p1",
        window_start="2024-01-01",
        window_end="2024-12-31",
        metrics_row=metrics_csv,
        timeseries=timeseries_str,
        context=context,
    )
    expected_prompt = "\n\n".join([prompts.system, prompts.developer, user_prompt])
    assert llm.last_prompt == expected_prompt


def test_schema_validation_error():
    storage = FakeStorage()
    # Missing required kpi_sentences and esrs_e4 blocks
    invalid_payload = json.dumps({"executive_summary": "hi"})
    llm = SchemaLlm(invalid_payload)
    svc = _service(llm, storage)

    metrics = _write_metrics(storage, "metrics.csv")
    timeseries = _write_timeseries(storage, "ts.csv")

    req = AiReportRequest(
        aoi_id="a1",
        project_id="p1",
        metrics_path=metrics,
        timeseries_path=timeseries,
    )

    with pytest.raises(ValidationError):
        svc.generate_summary(req)


def test_generate_summary_caches():
    storage = FakeStorage()
    payload = {
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
    llm = RecordingLlm(payload)
    svc = _service(llm, storage)

    metrics = _write_metrics(storage, "metrics.csv")
    timeseries = _write_timeseries(storage, "ts.csv")

    req = AiReportRequest(
        aoi_id="a1",
        project_id="p1",
        metrics_path=metrics,
        timeseries_path=timeseries,
    )

    initial_writes = storage.writes
    res1 = svc.generate_summary(req)
    assert llm.calls == 1
    assert storage.writes == initial_writes + 1  # cache artifact
    assert res1.summary["executive_summary"] == "exec"

    res2 = svc.generate_summary(req)
    assert llm.calls == 1  # cache hit
    assert storage.writes == initial_writes + 1
    assert res2.summary == res1.summary


@pytest.mark.slow
@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="requires OpenAI credentials",
)
def test_openai_smoke(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    storage = LocalFS()
    llm = OpenAiLlmClient(seed=0)
    svc = _service(llm, storage)

    metrics = _write_metrics(storage, str(tmp_path / "metrics.csv"))
    timeseries = _write_timeseries(storage, str(tmp_path / "ts.csv"))

    req = AiReportRequest(
        aoi_id="a1",
        project_id="p1",
        metrics_path=metrics,
        timeseries_path=timeseries,
    )

    res = svc.generate_summary(req)
    assert "executive_summary" in res.summary

