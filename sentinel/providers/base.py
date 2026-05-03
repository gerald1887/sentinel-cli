"""Provider boundary: request/response types, adapter contract, error categories.

Implementations must catch exceptions inside ``invoke`` and return
:class:`~sentinel.core.errors.SentinelError` — no raw exceptions past the adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sentinel.core.errors import SentinelError

# ---------------------------------------------------------------------------
# Standardized provider-layer categories (use as SentinelError.category)
# ---------------------------------------------------------------------------

PROVIDER_AUTH_ERROR: str = "PROVIDER_AUTH_ERROR"
PROVIDER_RATE_LIMIT: str = "PROVIDER_RATE_LIMIT"
PROVIDER_NETWORK_ERROR: str = "PROVIDER_NETWORK_ERROR"
PROVIDER_TIMEOUT: str = "PROVIDER_TIMEOUT"
PROVIDER_INVALID_RESPONSE: str = "PROVIDER_INVALID_RESPONSE"
PROVIDER_UNSUPPORTED_MODEL: str = "PROVIDER_UNSUPPORTED_MODEL"
PROVIDER_UNKNOWN_ERROR: str = "PROVIDER_UNKNOWN_ERROR"

# ---------------------------------------------------------------------------
# Data transfer objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    """Normalized input for a single provider invocation."""

    prompt_text: str
    model: str
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class ProviderResponseNormalized:
    """Normalized provider output before core JSON/schema handling."""

    raw_text: str
    provider_request_id: str | None = None
    usage: dict | None = None


# ---------------------------------------------------------------------------
# Adapter contract
# ---------------------------------------------------------------------------


class ProviderAdapter(Protocol):
    """Contract provider adapter: one call, one outcome (success or SentinelError)."""

    def invoke(
        self,
        request: ProviderRequest,
    ) -> ProviderResponseNormalized | SentinelError:
        """Return normalized text or a structured error; do not raise."""
