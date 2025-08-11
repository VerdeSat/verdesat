"""OpenAI client adapter implementing :class:`~verdesat.services.ai_report.LlmClient`.

This adapter uses the OpenAI Responses API with Structured Outputs. Responses
are validated against a supplied Pydantic model to guarantee the schema. The
call is deterministic (``temperature=0``, ``top_p=1`` and seeded) and will retry
once when schema validation fails.
"""

from __future__ import annotations

from typing import Any, Dict, Type

import logging
import time
from openai import OpenAI
from openai._exceptions import OpenAIError
from pydantic import BaseModel, ValidationError

from verdesat.core.logger import Logger


class OpenAiLlmClient:
    """LLM client using the OpenAI Responses API."""

    def __init__(
        self,
        *,
        client: OpenAI | None = None,
        seed: int = 42,
        max_retries: int = 1,
        logger: logging.Logger | None = None,
    ) -> None:
        self._client = client or OpenAI()
        self._seed = seed
        self._max_retries = max_retries
        self.logger = logger or Logger.get_logger(__name__)

    def generate(
        self,
        prompt: str,
        *,
        response_model: Type[BaseModel],
        model: str,
    ) -> Dict[str, Any]:
        """Generate structured output for *prompt* using *response_model*.

        Parameters
        ----------
        prompt:
            User prompt content.
        response_model:
            Pydantic model describing the expected JSON schema.
        model:
            OpenAI model name.

        Returns
        -------
        Dict[str, Any]
            Parsed model output as a Python dictionary.
        """

        attempt = 0
        while True:
            attempt += 1
            start = time.perf_counter()
            try:
                response = self._client.responses.create(
                    model=model,
                    input=prompt,
                    temperature=0,
                    top_p=1,
                    seed=self._seed,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": response_model.__name__,
                            "schema": response_model.model_json_schema(),
                            "strict": True,
                        },
                    },
                )
                content = response.output[0].content[0].text
            except OpenAIError as exc:  # pragma: no cover - network errors
                raise RuntimeError("OpenAI request failed") from exc

            latency_ms = (time.perf_counter() - start) * 1000
            usage = getattr(response, "usage", {}) or {}
            input_tokens = getattr(usage, "input_tokens", None)
            output_tokens = getattr(usage, "output_tokens", None)
            if isinstance(usage, dict):
                input_tokens = usage.get("input_tokens")
                output_tokens = usage.get("output_tokens")

            try:
                parsed = response_model.model_validate_json(content)
                self.logger.info(
                    "openai.response",
                    extra={
                        "event": "openai.response",
                        "model": model,
                        "latency_ms": round(latency_ms, 3),
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "retries": attempt - 1,
                    },
                )
                return parsed.model_dump()
            except ValidationError:
                self.logger.warning(
                    "openai.validation_failed",
                    extra={
                        "event": "openai.validation_failed",
                        "model": model,
                        "attempt": attempt,
                    },
                )
                if attempt > self._max_retries:
                    raise
                continue
