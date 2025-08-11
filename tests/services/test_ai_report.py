from __future__ import annotations

import logging
import pytest

from verdesat.core.config import ConfigManager
from verdesat.core.storage import LocalFS
from verdesat.schemas.ai_report import AiReportRequest
from verdesat.services.ai_report import AiReportService, LlmClient


class DummyLlm:
    def generate(self, prompt: str, **kwargs):  # pragma: no cover - placeholder
        return {}


def _service() -> AiReportService:
    return AiReportService(
        llm=DummyLlm(),
        storage=LocalFS(),
        logger=logging.getLogger("test"),
        config=ConfigManager(),
    )


def test_init_sets_dependencies():
    service = _service()
    assert service.llm is not None
    assert service.storage is not None
    assert service.logger is not None
    assert service.config is not None


def test_generate_summary_not_implemented():
    service = _service()
    req = AiReportRequest(
        aoi_id="a1",
        project_id="p1",
        metrics_path="metrics.csv",
        timeseries_path="ts.csv",
    )
    with pytest.raises(NotImplementedError):
        service.generate_summary(req)
