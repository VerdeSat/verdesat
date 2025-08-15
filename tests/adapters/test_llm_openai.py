from __future__ import annotations

from typing import Any, Dict

import logging

import pytest
from pydantic import BaseModel

import verdesat.adapters.llm_openai as llm_openai
from verdesat.adapters.llm_openai import OpenAiLlmClient
from verdesat.core.logger import Logger


class _Content:
    def __init__(self, text: str) -> None:
        self.text = text


class _Output:
    def __init__(self, text: str) -> None:
        self.content = [_Content(text)]


class _Response:
    def __init__(self, text: str, usage: Dict[str, int] | None = None) -> None:
        self.output = [_Output(text)]
        self.usage = usage or {"input_tokens": 1, "output_tokens": 2}


class _Responses:
    def __init__(
        self,
        texts: list[str],
        calls: list[Dict[str, Any]],
        usage: Dict[str, int] | None = None,
    ) -> None:
        self._texts = texts
        self._calls = calls
        self._usage = usage or {"input_tokens": 1, "output_tokens": 2}

    def create(self, **kwargs: Any) -> _Response:
        self._calls.append(kwargs)
        text = self._texts.pop(0)
        return _Response(text, self._usage)


class FakeOpenAI:
    def __init__(self, texts: list[str], usage: Dict[str, int] | None = None) -> None:
        self.calls: list[Dict[str, Any]] = []
        self.responses = _Responses(texts, self.calls, usage)


class OutputModel(BaseModel):
    answer: str


def test_generate_passes_deterministic_params() -> None:
    client = OpenAiLlmClient(
        client=FakeOpenAI(['{"answer": "ok"}']),
        seed=99,
        logger=Logger.get_logger("test"),
    )
    result = client.generate("hi", response_model=OutputModel, model="gpt-4o-mini")
    assert result == {"answer": "ok"}
    params = client._client.calls[0]  # type: ignore[attr-defined]
    assert params["temperature"] == 0
    assert params["top_p"] == 1
    assert params["seed"] == 99
    assert params["model"] == "gpt-4o-mini"
    schema = OutputModel.model_json_schema()
    assert params["response_format"]["json_schema"]["schema"] == schema


def test_generate_can_override_seed() -> None:
    fake = FakeOpenAI(['{"answer": "ok"}'])
    client = OpenAiLlmClient(client=fake, seed=1, logger=Logger.get_logger("test"))
    client.generate("hi", response_model=OutputModel, model="gpt-4o-mini", seed=123)
    params = client._client.calls[0]  # type: ignore[attr-defined]
    assert params["seed"] == 123


def test_generate_retries_on_validation_error() -> None:
    texts = ["not json", '{"answer": "ok"}']
    fake = FakeOpenAI(texts)
    client = OpenAiLlmClient(
        client=fake, max_retries=1, logger=Logger.get_logger("test")
    )
    result = client.generate("hi", response_model=OutputModel, model="gpt-4o-mini")
    assert result == {"answer": "ok"}
    assert len(fake.calls) == 2


def test_generate_raises_after_retry() -> None:
    texts = ["not json", "still bad"]
    fake = FakeOpenAI(texts)
    client = OpenAiLlmClient(
        client=fake, max_retries=1, logger=Logger.get_logger("test")
    )
    with pytest.raises(Exception):
        client.generate("hi", response_model=OutputModel, model="gpt-4o-mini")


def test_generate_logs_metrics(caplog, monkeypatch) -> None:
    fake = FakeOpenAI(
        ['{"answer": "ok"}'], usage={"input_tokens": 3, "output_tokens": 4}
    )
    client = OpenAiLlmClient(client=fake, seed=0, logger=Logger.get_logger("test"))

    times = iter([1.0, 1.1])
    monkeypatch.setattr(llm_openai.time, "perf_counter", lambda: next(times))

    with caplog.at_level(logging.INFO):
        client.generate("hi", response_model=OutputModel, model="gpt-4o-mini")

    record = caplog.records[-1]
    assert record.event == "openai.response"
    assert record.model == "gpt-4o-mini"
    assert record.latency_ms == 100.0
    assert record.input_tokens == 3
    assert record.output_tokens == 4
    assert record.retries == 0
