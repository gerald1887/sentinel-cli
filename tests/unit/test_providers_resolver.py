"""Unit tests for provider resolver boundary."""

from __future__ import annotations

from sentinel.providers import get_provider_adapter
from sentinel.providers.openai import OpenAIProviderAdapter


def test_get_provider_adapter_openai_returns_openai_adapter() -> None:
    # REQ-F-016, REQ-F-017
    # provider abstraction allows adapter resolution without core changes
    adapter = get_provider_adapter("openai")
    assert isinstance(adapter, OpenAIProviderAdapter)

