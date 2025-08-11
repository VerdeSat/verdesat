"""Service for LLM-based report summaries with caching."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, Protocol

from verdesat.core.config import ConfigManager
from verdesat.core.storage import StorageAdapter
from verdesat.schemas.ai_report import AiReportRequest, AiReportResult
from verdesat.adapters.prompt_store import get_prompts


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

    # ------------------------------------------------------------------
    def _compute_hash(
        self, request: AiReportRequest, model: str, prompt_version: str
    ) -> str:
        """Return SHA-256 hash for *request* inputs.

        The hash incorporates the raw bytes of the metrics, time series, and
        optional lineage files along with the prompt and model configuration.
        """

        prompts = get_prompts(prompt_version)
        sha = hashlib.sha256()
        for path in (
            request.metrics_path,
            request.timeseries_path,
            request.lineage_path,
        ):
            if path:
                sha.update(self.storage.read_bytes(path))
        sha.update(prompts.system.encode("utf-8"))
        sha.update(prompts.developer.encode("utf-8"))
        sha.update(prompts.user.encode("utf-8"))
        sha.update(model.encode("utf-8"))
        return sha.hexdigest()

    # ------------------------------------------------------------------
    def generate_summary(self, request: AiReportRequest) -> AiReportResult:
        """Generate or retrieve a cached AI report summary."""

        model = request.model or self.config.get("ai_report_model", "gpt-4o-mini")
        prompt_version = request.prompt_version or self.config.get(
            "ai_report_prompt_version", "v1"
        )
        input_hash = self._compute_hash(request, model, prompt_version)
        uri = self.storage.join("ai_reports", f"{input_hash}.json")

        if not request.force:
            try:
                cached = self.storage.read_bytes(uri)
                obj = json.loads(cached.decode("utf-8"))
                self.logger.debug("loaded cached AI report %s", uri)
                return AiReportResult(
                    aoi_id=request.aoi_id,
                    project_id=request.project_id,
                    model=model,
                    prompt_version=prompt_version,
                    summary=obj.get("summary", {}),
                    narrative=obj.get("narrative", ""),
                    uri=uri,
                )
            except FileNotFoundError:
                pass
            except Exception:
                self.logger.exception("failed to read cached report %s", uri)

        payload = self.llm.generate("", model=model, prompt_version=prompt_version)
        summary = payload.get("summary", {})
        narrative = payload.get("narrative", "")
        artifact = json.dumps(
            {"summary": summary, "narrative": narrative}, sort_keys=True
        ).encode("utf-8")
        self.storage.write_bytes(uri, artifact)
        self.logger.debug("stored AI report at %s", uri)
        return AiReportResult(
            aoi_id=request.aoi_id,
            project_id=request.project_id,
            model=model,
            prompt_version=prompt_version,
            summary=summary,
            narrative=narrative,
            uri=uri,
        )
