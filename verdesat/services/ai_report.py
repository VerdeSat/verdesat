from __future__ import annotations

"""Service skeleton for LLM-based report summaries."""

import logging
from typing import Any, Dict, Protocol

from verdesat.core.config import ConfigManager
from verdesat.core.storage import StorageAdapter
from verdesat.schemas.ai_report import AiReportRequest, AiReportResult


class LlmClient(Protocol):
    """Minimal interface for language model clients."""

    def generate(self, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        """Return structured output for *prompt*."""


class AiReportService:
    """Create AI-generated summaries for project AOIs."""

    def __init__(
        self,
        *,
        llm: LlmClient,
        storage: StorageAdapter,
        logger: logging.Logger,
        config: ConfigManager,
    ) -> None:
        self.llm = llm
        self.storage = storage
        self.logger = logger
        self.config = config

    def generate_summary(self, request: AiReportRequest) -> AiReportResult:
        """Generate or retrieve a cached AI report summary."""
        raise NotImplementedError
