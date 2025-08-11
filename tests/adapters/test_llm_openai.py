from __future__ import annotations

from typing import Any, Dict

import pytest
from pydantic import BaseModel

from verdesat.adapters.llm_openai import OpenAiLlmClient


class _Content:
    def __init__(self, text: str) -> None:
        self.text = text


class _Output:
    def __init__(self, text: str) -> None:
        self.content = [_Content(text)]


class _Response:
    def __init__(self, text: str) -> None:
        self.output = [_Output(text)]


class _Responses:
    def __init__(self, texts: list[str], calls: list[Dict[str, Any]]) -> None:
        self._texts = texts
        self._calls = calls

    def create(self, **kwargs: Any) -> _Response:
        self._calls.append(kwargs)
        text = self._texts.pop(0)
        return _Response(text)


class FakeOpenAI:
    def __init__(self, texts: list[str]) -> None:
        self.calls: list[Dict[str, Any]] = []
        self.responses = _Responses(texts, self.calls)


class OutputModel(BaseModel):
    answer: str


def test_generate_passes_deterministic_params() -> None:
    client = OpenAiLlmClient(client=FakeOpenAI(['{"answer": "ok"}']), seed=99)
    result = client.generate("hi", response_model=OutputModel, model="gpt-4o-mini")
    assert result == {"answer": "ok"}
    params = client._client.calls[0]  # type: ignore[attr-defined]
    assert params["temperature"] == 0
    assert params["top_p"] == 1
    assert params["seed"] == 99
    assert params["model"] == "gpt-4o-mini"
    schema = OutputModel.model_json_schema()
    assert params["response_format"]["json_schema"]["schema"] == schema


def test_generate_retries_on_validation_error() -> None:
    texts = ["not json", '{"answer": "ok"}']
    fake = FakeOpenAI(texts)
    client = OpenAiLlmClient(client=fake, max_retries=1)
    result = client.generate("hi", response_model=OutputModel, model="gpt-4o-mini")
    assert result == {"answer": "ok"}
    assert len(fake.calls) == 2


def test_generate_raises_after_retry() -> None:
    texts = ["not json", "still bad"]
    fake = FakeOpenAI(texts)
    client = OpenAiLlmClient(client=fake, max_retries=1)
    with pytest.raises(Exception):
        client.generate("hi", response_model=OutputModel, model="gpt-4o-mini")
