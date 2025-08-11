"""OpenAI client adapter implementing :class:`~verdesat.services.ai_report.LlmClient`.

This adapter uses the OpenAI Responses API with Structured Outputs. Responses
are validated against a supplied Pydantic model to guarantee the schema. The
call is deterministic (``temperature=0``, ``top_p=1`` and seeded) and will retry
once when schema validation fails.
"""

from __future__ import annotations

from typing import Any, Dict, Type

from openai import OpenAI
from openai._exceptions import OpenAIError
from pydantic import BaseModel, ValidationError


class OpenAiLlmClient:
    """LLM client using the OpenAI Responses API."""

    def __init__(
        self,
        *,
        client: OpenAI | None = None,
        seed: int = 42,
        max_retries: int = 1,
    ) -> None:
        self._client = client or OpenAI()
        self._seed = seed
        self._max_retries = max_retries

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

            try:
                parsed = response_model.model_validate_json(content)
                return parsed.model_dump()
            except ValidationError:
                if attempt > self._max_retries:
                    raise
                continue
