"""Adapters for external services (APIs, storage, etc.)."""

from .llm_openai import OpenAiLlmClient
from .prompt_store import PROMPT_VERSION, get_prompts

__all__ = ["OpenAiLlmClient", "get_prompts", "PROMPT_VERSION"]
