"""OpenAI provider adapter used by Sentinel run/test workflows."""

from __future__ import annotations

import os
import re

from sentinel.core.errors import SentinelError
from sentinel.providers.base import (
    PROVIDER_AUTH_ERROR,
    PROVIDER_INVALID_RESPONSE,
    PROVIDER_NETWORK_ERROR,
    PROVIDER_RATE_LIMIT,
    PROVIDER_TIMEOUT,
    PROVIDER_UNKNOWN_ERROR,
    PROVIDER_UNSUPPORTED_MODEL,
    ProviderAdapter,
    ProviderRequest,
    ProviderResponseNormalized,
)

# Strings placed in SentinelError.details must not echo secrets (keys, tokens, env values).
_SK_LIKE = re.compile(r"sk-[a-zA-Z0-9_-]{20,}")
_AUTH_BEARER = re.compile(
    r"(?i)(authorization:\s*bearer\s+)(\S+)",
)
_BEARER_TOKEN = re.compile(r"(?i)(\bbearer\s+)([A-Za-z0-9._\-]{8,})")


def _sanitize_provider_error_detail(text: str) -> str:
    """Redact secret-shaped substrings from provider-originated error text."""
    out = text
    out = _SK_LIKE.sub("[REDACTED]", out)
    out = _AUTH_BEARER.sub(r"\1[REDACTED]", out)
    out = _BEARER_TOKEN.sub(r"\1[REDACTED]", out)
    for env_name in ("OPENAI_API_KEY",):
        val = os.getenv(env_name)
        if val and len(val) >= 8 and val in out:
            out = out.replace(val, "[REDACTED]")
    return out


class OpenAIProviderAdapter(ProviderAdapter):
    """Invoke OpenAI and normalize result into provider boundary types."""

    def invoke(
        self,
        request: ProviderRequest,
    ) -> ProviderResponseNormalized | SentinelError:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return SentinelError(
                category=PROVIDER_AUTH_ERROR,
                code="SENTINEL_PROVIDER_AUTH_MISSING_KEY",
                message="Missing OpenAI API key.",
            )

        try:
            from openai import (
                APIConnectionError,
                APIStatusError,
                APITimeoutError,
                AuthenticationError,
                BadRequestError,
                NotFoundError,
                OpenAI,
                RateLimitError,
            )
        except Exception as exc:  # noqa: BLE001
            return SentinelError(
                category=PROVIDER_UNKNOWN_ERROR,
                code="SENTINEL_PROVIDER_SDK_IMPORT_ERROR",
                message="Failed to import OpenAI SDK.",
                details={"error": _sanitize_provider_error_detail(str(exc))},
            )

        try:
            client = OpenAI(api_key=api_key, timeout=request.timeout_seconds)
            response = client.chat.completions.create(
                model=request.model,
                messages=[{"role": "user", "content": request.prompt_text}],
                temperature=0,
            )

            content = None
            choices = getattr(response, "choices", None)
            if isinstance(choices, list) and choices:
                first_choice = choices[0]
                message = getattr(first_choice, "message", None)
                content = getattr(message, "content", None)

            if not isinstance(content, str) or not content:
                return SentinelError(
                    category=PROVIDER_INVALID_RESPONSE,
                    code="SENTINEL_PROVIDER_INVALID_RESPONSE",
                    message="Provider response did not contain text output.",
                )

            usage = getattr(response, "usage", None)
            usage_dict = usage.model_dump() if usage is not None else None

            return ProviderResponseNormalized(
                raw_text=content,
                provider_request_id=getattr(response, "id", None),
                usage=usage_dict,
            )
        except AuthenticationError:
            return SentinelError(
                category=PROVIDER_AUTH_ERROR,
                code="SENTINEL_PROVIDER_AUTH_ERROR",
                message="Provider authentication failed.",
            )
        except RateLimitError:
            return SentinelError(
                category=PROVIDER_RATE_LIMIT,
                code="SENTINEL_PROVIDER_RATE_LIMIT",
                message="Provider rate limit exceeded.",
            )
        except APITimeoutError:
            return SentinelError(
                category=PROVIDER_TIMEOUT,
                code="SENTINEL_PROVIDER_TIMEOUT",
                message="Provider request timed out.",
            )
        except APIConnectionError:
            return SentinelError(
                category=PROVIDER_NETWORK_ERROR,
                code="SENTINEL_PROVIDER_NETWORK_ERROR",
                message="Provider network connection failed.",
            )
        except NotFoundError:
            return SentinelError(
                category=PROVIDER_UNSUPPORTED_MODEL,
                code="SENTINEL_PROVIDER_UNSUPPORTED_MODEL",
                message="Requested model is not available.",
            )
        except BadRequestError as exc:
            msg = str(exc).lower()
            if "model" in msg:
                return SentinelError(
                    category=PROVIDER_UNSUPPORTED_MODEL,
                    code="SENTINEL_PROVIDER_UNSUPPORTED_MODEL",
                    message="Requested model is not supported.",
                    details={"error": _sanitize_provider_error_detail(str(exc))},
                )
            return SentinelError(
                category=PROVIDER_INVALID_RESPONSE,
                code="SENTINEL_PROVIDER_BAD_REQUEST",
                message="Provider rejected the request.",
                details={"error": _sanitize_provider_error_detail(str(exc))},
            )
        except APIStatusError as exc:
            status_code = getattr(exc, "status_code", None)
            if status_code == 401:
                return SentinelError(
                    category=PROVIDER_AUTH_ERROR,
                    code="SENTINEL_PROVIDER_AUTH_ERROR",
                    message="Provider authentication failed.",
                )
            if status_code == 429:
                return SentinelError(
                    category=PROVIDER_RATE_LIMIT,
                    code="SENTINEL_PROVIDER_RATE_LIMIT",
                    message="Provider rate limit exceeded.",
                )
            if status_code in (400, 404):
                return SentinelError(
                    category=PROVIDER_UNSUPPORTED_MODEL,
                    code="SENTINEL_PROVIDER_UNSUPPORTED_MODEL",
                    message="Requested model is not available.",
                    details={"status_code": status_code},
                )
            return SentinelError(
                category=PROVIDER_UNKNOWN_ERROR,
                code="SENTINEL_PROVIDER_API_STATUS_ERROR",
                message="Provider returned an unexpected API status error.",
                details={"status_code": status_code},
            )
        except Exception as exc:  # noqa: BLE001
            return SentinelError(
                category=PROVIDER_UNKNOWN_ERROR,
                code="SENTINEL_PROVIDER_UNKNOWN_ERROR",
                message="Unknown provider error.",
                details={"error": _sanitize_provider_error_detail(str(exc))},
            )

