"""Provider adapters for Sentinel execution flows."""

from __future__ import annotations

from sentinel.core.errors import SentinelError
from sentinel.providers.base import PROVIDER_UNKNOWN_ERROR, ProviderAdapter
from sentinel.providers.openai import OpenAIProviderAdapter


def get_provider_adapter(provider_name: str) -> ProviderAdapter | SentinelError:
    """Resolve a provider name to an adapter implementation."""
    normalized = provider_name.strip().lower()

    if normalized == "openai":
        return OpenAIProviderAdapter()

    return SentinelError(
        category=PROVIDER_UNKNOWN_ERROR,
        code="SENTINEL_PROVIDER_UNKNOWN",
        message="Unknown provider.",
        details={"provider": provider_name},
    )

