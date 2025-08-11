from __future__ import annotations

import pytest

from verdesat.adapters.prompt_store import PROMPT_VERSION, get_prompts


def test_get_prompts_returns_bundle():
    bundle = get_prompts()
    assert bundle.system
    assert bundle.developer
    assert bundle.user


def test_get_prompts_unknown_version():
    with pytest.raises(ValueError):
        get_prompts("v999")


def test_prompt_version_constant():
    assert isinstance(PROMPT_VERSION, str)
