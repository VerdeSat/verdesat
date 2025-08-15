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
        seed: int | None = None,
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
        seed:
            Optional random seed for deterministic responses. Defaults to the
            value provided when the client was initialised.

        Returns
        -------
        Dict[str, Any]
            Parsed model output as a Python dictionary.
        """

        # Ensure JSON Schema is strict (additionalProperties: false for all objects)
        def _strictify(schema: Dict[str, Any]) -> Dict[str, Any]:
            def _patch(node: Any) -> None:
                if isinstance(node, dict):
                    if node.get("type") == "object":
                        # OpenAI strict mode requires explicit additionalProperties: false
                        node["additionalProperties"] = False
                        # And `required` must include every key present in properties
                        props = node.get("properties")
                        if isinstance(props, dict):
                            node["required"] = list(props.keys())
                    # Recurse into nested values
                    for v in node.values():
                        _patch(v)
                elif isinstance(node, list):
                    for v in node:
                        _patch(v)

            out = dict(schema)
            _patch(out)
            return out

        attempt = 0
        while True:
            attempt += 1
            start = time.perf_counter()
            try:
                # Build request kwargs so we can drop unsupported params (e.g., seed) if needed
                req_kwargs = {
                    "model": model,
                    "input": prompt,
                    "temperature": 0,
                    "top_p": 1,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": response_model.__name__,
                            "schema": response_model.model_json_schema(),
                            "strict": True,
                        },
                    },
                }
                # Prefer deterministic seed when supported
                req_kwargs["seed"] = self._seed if seed is None else seed

                used_chat_api = False
                try:
                    try:
                        response = self._client.responses.create(**req_kwargs)
                    except TypeError as te:
                        # Some OpenAI SDK versions for the Responses API don't accept `seed`
                        if "seed" in str(te):
                            req_kwargs.pop("seed", None)
                            response = self._client.responses.create(**req_kwargs)
                        # Older SDKs may not support `response_format` for Responses API — fall back to Chat Completions
                        elif "response_format" in str(te):
                            raise
                        else:
                            raise
                    content = response.output[0].content[0].text
                except TypeError as te:
                    if "response_format" in str(te):
                        # Fallback preference 1: Chat Completions with JSON Schema (structured outputs)
                        strict_schema = _strictify(response_model.model_json_schema())
                        chat_schema = {
                            "type": "json_schema",
                            "json_schema": {
                                "name": response_model.__name__,
                                "schema": strict_schema,
                                "strict": True,
                            },
                        }
                        chat_kwargs = {
                            "model": model,
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0,
                            "top_p": 1,
                            "response_format": chat_schema,
                        }
                        chat_kwargs["seed"] = self._seed if seed is None else seed
                        try:
                            response = self._client.chat.completions.create(
                                **chat_kwargs
                            )
                        except TypeError as te2:
                            # Older SDKs may not support structured outputs on Chat; fall back to json_object + hard schema instruction
                            if "response_format" in str(te2):
                                messages = [
                                    {
                                        "role": "system",
                                        "content": (
                                            "Return ONLY a JSON object that strictly matches this Pydantic schema; "
                                            "no extra keys, no prose. Schema:\n"
                                            + str(response_model.model_json_schema())
                                        ),
                                    },
                                    {"role": "user", "content": prompt},
                                ]
                                chat_kwargs = {
                                    "model": model,
                                    "messages": messages,
                                    "temperature": 0,
                                    "top_p": 1,
                                    "response_format": {"type": "json_object"},
                                }
                                chat_kwargs["seed"] = (
                                    self._seed if seed is None else seed
                                )
                                try:
                                    response = self._client.chat.completions.create(
                                        **chat_kwargs
                                    )
                                except TypeError as te3:
                                    if "seed" in str(te3):
                                        chat_kwargs.pop("seed", None)
                                        response = self._client.chat.completions.create(
                                            **chat_kwargs
                                        )
                                    else:
                                        raise
                            elif "seed" in str(te2):
                                chat_kwargs.pop("seed", None)
                                response = self._client.chat.completions.create(
                                    **chat_kwargs
                                )
                            else:
                                raise
                        except OpenAIError as oe:
                            # If Chat structured outputs reject the schema (400), fall back to function-calling tools
                            # using the same strict schema as function parameters.
                            tools = [
                                {
                                    "type": "function",
                                    "function": {
                                        "name": response_model.__name__,
                                        "description": "Return a JSON object matching the schema.",
                                        "parameters": strict_schema,
                                    },
                                }
                            ]
                            fc_kwargs = {
                                "model": model,
                                "messages": [{"role": "user", "content": prompt}],
                                "temperature": 0,
                                "top_p": 1,
                                "tools": tools,
                                "tool_choice": {
                                    "type": "function",
                                    "function": {"name": response_model.__name__},
                                },
                            }
                            fc_kwargs["seed"] = self._seed if seed is None else seed
                            try:
                                response = self._client.chat.completions.create(
                                    **fc_kwargs
                                )
                            except TypeError as te4:
                                if "seed" in str(te4):
                                    fc_kwargs.pop("seed", None)
                                    response = self._client.chat.completions.create(
                                        **fc_kwargs
                                    )
                                else:
                                    raise
                        used_chat_api = True
                        # Extract content: prefer tool call arguments if present
                        try:
                            msg = response.choices[0].message
                            tool_calls = getattr(msg, "tool_calls", None)
                            if tool_calls:
                                content = tool_calls[0].function.arguments
                            else:
                                content = msg.content
                        except Exception:
                            # Fallback to Responses-like access if the SDK normalizes differently
                            content = response.choices[0].message.content
                    else:
                        raise
            except OpenAIError as exc:  # pragma: no cover - network errors
                raise RuntimeError("OpenAI request failed") from exc

            latency_ms = (time.perf_counter() - start) * 1000

            usage = getattr(response, "usage", {}) or {}
            input_tokens = None
            output_tokens = None
            if isinstance(usage, dict):
                # Responses API reports input/output_tokens; Chat uses prompt/completion_tokens
                input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens")
                output_tokens = usage.get("output_tokens") or usage.get(
                    "completion_tokens"
                )
            else:
                input_tokens = getattr(usage, "input_tokens", None) or getattr(
                    usage, "prompt_tokens", None
                )
                output_tokens = getattr(usage, "output_tokens", None) or getattr(
                    usage, "completion_tokens", None
                )

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
