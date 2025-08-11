from __future__ import annotations

import hashlib
import logging
from pathlib import Path

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
        return {"summary": {"ok": True}, "narrative": "narr"}


def _service(llm: DummyLlm, storage: LocalFS) -> AiReportService:
    return AiReportService(
        llm=llm,
        storage=storage,
        logger=logging.getLogger("test"),
        config=ConfigManager(),
    )


def _write(storage: LocalFS, path: Path, content: str) -> str:
    storage.write_bytes(str(path), content.encode("utf-8"))
    return str(path)


def test_compute_hash(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    storage = LocalFS()
    llm = DummyLlm()
    svc = _service(llm, storage)

    metrics = Path("metrics.csv")
    timeseries = Path("ts.csv")
    lineage = Path("lineage.json")
    _write(storage, metrics, "m")
    _write(storage, timeseries, "t")
    _write(storage, lineage, "{}")

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
    _write(storage, metrics, "m")
    _write(storage, timeseries, "t")

    req = AiReportRequest(
        aoi_id="a1",
        project_id="p1",
        metrics_path=str(metrics),
        timeseries_path=str(timeseries),
    )

    res1 = svc.generate_summary(req)
    assert llm.calls == 1
    assert res1.uri and Path(res1.uri).exists()

    res2 = svc.generate_summary(req)
    assert llm.calls == 1  # cache hit
    assert res2.summary == res1.summary
    assert res2.narrative == res1.narrative
