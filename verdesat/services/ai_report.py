"""Service for LLM-based report summaries with caching."""

from __future__ import annotations

import hashlib
import io
import json
import logging
from typing import Any, Dict, Protocol

import pandas as pd
from pydantic import BaseModel, Field

from verdesat.adapters.prompt_store import get_prompts
from verdesat.core.config import ConfigManager
from verdesat.core.storage import StorageAdapter
from verdesat.schemas.ai_report import AiReportRequest, AiReportResult


class _KpiSentences(BaseModel):
    """Structured KPI sentences block."""

    bscore: str = Field(max_length=280)
    intactness: str = Field(max_length=280)
    fragmentation: str = Field(max_length=280)
    ndvi_trend: str = Field(max_length=280)


class _EsrsE4(BaseModel):
    """Structured ESRS E4 block."""

    extent_condition: str = Field(max_length=700)
    pressures: str = Field(max_length=700)
    targets: str = Field(max_length=500)
    actions: str = Field(max_length=500)
    financial_effects: str = Field(max_length=500)


class _AiSummaryModel(BaseModel):
    """LLM output schema."""

    executive_summary: str = Field(max_length=1200)
    kpi_sentences: _KpiSentences
    esrs_e4: _EsrsE4
    flags: list[str] = Field(default_factory=list, max_items=10)
    numbers: Dict[str, Any] = Field(default_factory=dict)
    meta: Dict[str, Any] = Field(default_factory=dict)


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
    def _check_numbers(self, metrics: Dict[str, Any], numbers: Dict[str, Any]) -> None:
        """Verify numeric echoes from the LLM against original metrics."""
        for key, val in numbers.items():
            if key not in metrics:
                raise ValueError(f"unexpected number: {key}")
            try:
                metric_val = float(metrics[key])
                llm_val = float(val)
            except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
                raise ValueError(f"non-numeric value for {key}") from exc
            if abs(metric_val - llm_val) > 1e-6:
                raise ValueError(
                    f"numeric mismatch for {key}: {llm_val} != {metric_val}"
                )

    # ------------------------------------------------------------------
    def _compute_hash(
        self, request: AiReportRequest, model: str, prompt_version: str
    ) -> str:
        """Return SHA-256 hash for *request* inputs."""

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
    def _read_table(self, path: str) -> pd.DataFrame:
        """Load CSV or Parquet file from storage into a DataFrame."""

        data = self.storage.read_bytes(path)
        buf = io.BytesIO(data)
        if path.lower().endswith(".parquet"):
            return pd.read_parquet(buf)
        return pd.read_csv(buf)

    # ------------------------------------------------------------------
    def generate_summary(self, request: AiReportRequest) -> AiReportResult:
        """Validate inputs, invoke LLM, and cache structured summary."""

        model = request.model or self.config.get("ai_report_model", "gpt-4o-mini")
        prompt_version = request.prompt_version or self.config.get(
            "ai_report_prompt_version", "v1"
        )
        seed = int(self.config.get("ai_report_seed", 42))
        input_hash = self._compute_hash(request, model, prompt_version)
        uri = self.storage.join("ai_reports", f"{input_hash}.json")

        if not request.force:
            try:
                cached = self.storage.read_bytes(uri)
                obj = json.loads(cached.decode("utf-8"))
                self.logger.info(
                    "ai_report cache",
                    extra={
                        "event": "ai_report.cache",
                        "status": "hit",
                        "model": model,
                        "input_hash": input_hash,
                    },
                )
                url: str | None
                try:
                    url = self.storage.presign(uri)
                except Exception:  # pragma: no cover - optional
                    url = None
                return AiReportResult(
                    aoi_id=request.aoi_id,
                    project_id=request.project_id,
                    model=model,
                    prompt_version=prompt_version,
                    summary=obj,
                    narrative=obj.get("executive_summary", ""),
                    uri=uri,
                    url=url,
                )
            except FileNotFoundError:
                self.logger.info(
                    "ai_report cache",
                    extra={
                        "event": "ai_report.cache",
                        "status": "miss",
                        "model": model,
                        "input_hash": input_hash,
                    },
                )
            except Exception:  # pragma: no cover - defensive
                self.logger.exception("failed to read cached report %s", uri)
                self.logger.info(
                    "ai_report cache",
                    extra={
                        "event": "ai_report.cache",
                        "status": "error",
                        "model": model,
                        "input_hash": input_hash,
                    },
                )

        metrics_df = self._read_table(request.metrics_path)
        if metrics_df.shape[0] != 1:
            raise ValueError("metrics_path must contain exactly one row")
        required_metrics = {
            "aoi_id",
            "project_id",
            "method_version",
            "window_start",
            "window_end",
        }
        missing = required_metrics - set(metrics_df.columns)
        if missing:
            raise ValueError(f"metrics_path missing columns: {sorted(missing)}")

        ts_df = self._read_table(request.timeseries_path)
        required_ts = {"date", "metric", "value", "aoi_id"}
        missing = required_ts - set(ts_df.columns)
        if missing:
            raise ValueError(f"timeseries_path missing columns: {sorted(missing)}")
        ndvi_df = ts_df[ts_df["metric"] == "ndvi_mean"].copy()
        if ndvi_df.empty:
            raise ValueError("timeseries_path must contain ndvi_mean metric")

        metrics_row = metrics_df.iloc[0].to_dict()
        metrics_row_csv = metrics_df.to_csv(index=False).strip()
        ndvi_df["date"] = pd.to_datetime(ndvi_df["date"]).dt.to_period("M").astype(str)
        ndvi_df.sort_values("date", inplace=True)
        timeseries_str = "\n".join(
            f"{row.date},{row.value:.3f}" for row in ndvi_df.itertuples()
        )
        context_parts = []
        for field in ("ecoregion", "elevation_mean_m", "wdpa_inside"):
            val = metrics_row.get(field)
            if val is not None:
                context_parts.append(f"{field}={val}")
        context = ", ".join(context_parts)

        prompts = get_prompts(prompt_version)
        user_prompt = prompts.user.format(
            aoi_id=request.aoi_id,
            project_id=request.project_id,
            window_start=str(metrics_row["window_start"]),
            window_end=str(metrics_row["window_end"]),
            metrics_row=metrics_row_csv,
            timeseries=timeseries_str,
            context=context,
        )
        prompt = "\n\n".join([prompts.system, prompts.developer, user_prompt])

        payload = self.llm.generate(
            prompt,
            model=model,
            seed=seed,
            response_model=_AiSummaryModel,
        )
        if isinstance(payload, str):
            payload = json.loads(payload)

        self._check_numbers(metrics_row, payload.get("numbers", {}))

        artifact = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.storage.write_bytes(uri, artifact)
        self.logger.debug("stored AI report at %s", uri)
        try:
            url = self.storage.presign(uri)
        except Exception:  # pragma: no cover - optional
            url = None
        return AiReportResult(
            aoi_id=request.aoi_id,
            project_id=request.project_id,
            model=model,
            prompt_version=prompt_version,
            summary=payload,
            narrative=payload.get("executive_summary", ""),
            uri=uri,
            url=url,
        )
