"""Unit tests for sentinel.providers.openai."""

from __future__ import annotations

import sys
import types

from sentinel.core.errors import SentinelError, render_error
from sentinel.providers.base import (
    PROVIDER_AUTH_ERROR,
    PROVIDER_INVALID_RESPONSE,
    PROVIDER_RATE_LIMIT,
    PROVIDER_TIMEOUT,
    PROVIDER_UNSUPPORTED_MODEL,
    ProviderRequest,
)
from sentinel.providers.openai import OpenAIProviderAdapter


def test_openai_adapter_missing_api_key_returns_auth_error(monkeypatch) -> None:
    # REQ-LLM-003
    # provider auth error mapped to standardized category
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    adapter = OpenAIProviderAdapter()
    result = adapter.invoke(
        ProviderRequest(
            prompt_text="Return JSON.",
            model="gpt-4.1",
            timeout_seconds=5,
        )
    )

    assert isinstance(result, SentinelError)
    assert result.category == PROVIDER_AUTH_ERROR


def _install_fake_openai_module(monkeypatch, create_callable) -> None:
    class _BaseError(Exception):
        pass

    class _FakeOpenAI:
        def __init__(self, api_key: str, timeout: int) -> None:
            _ = (api_key, timeout)
            self.chat = types.SimpleNamespace(
                completions=types.SimpleNamespace(create=create_callable)
            )

    fake_module = types.SimpleNamespace(
        OpenAI=_FakeOpenAI,
        APIConnectionError=type("APIConnectionError", (_BaseError,), {}),
        APIStatusError=type("APIStatusError", (_BaseError,), {}),
        APITimeoutError=type("APITimeoutError", (_BaseError,), {}),
        AuthenticationError=type("AuthenticationError", (_BaseError,), {}),
        BadRequestError=type("BadRequestError", (_BaseError,), {}),
        NotFoundError=type("NotFoundError", (_BaseError,), {}),
        RateLimitError=type("RateLimitError", (_BaseError,), {}),
    )
    monkeypatch.setitem(sys.modules, "openai", fake_module)


def test_openai_adapter_no_usable_text_returns_invalid_response(monkeypatch) -> None:
    # REQ-LLM-002, REQ-LLM-003
    # invalid provider payload is classified deterministically
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def _create(*, model: str, messages: list[dict[str, str]], temperature: int):
        _ = (model, messages, temperature)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=None))],
            id="req_1",
            usage=None,
        )

    _install_fake_openai_module(monkeypatch, _create)

    adapter = OpenAIProviderAdapter()
    result = adapter.invoke(
        ProviderRequest(prompt_text="Return JSON.", model="gpt-4.1", timeout_seconds=5)
    )

    assert isinstance(result, SentinelError)
    assert result.category == PROVIDER_INVALID_RESPONSE
    assert result.code == "SENTINEL_PROVIDER_INVALID_RESPONSE"


def test_openai_adapter_missing_output_text_field_returns_invalid_response(
    monkeypatch,
) -> None:
    # REQ-LLM-002, REQ-LLM-003
    # missing expected output text maps to provider invalid response
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def _create(*, model: str, messages: list[dict[str, str]], temperature: int):
        _ = (model, messages, temperature)
        return types.SimpleNamespace(id="req_2", usage=None)

    _install_fake_openai_module(monkeypatch, _create)

    adapter = OpenAIProviderAdapter()
    result = adapter.invoke(
        ProviderRequest(prompt_text="Return JSON.", model="gpt-4.1", timeout_seconds=5)
    )

    assert isinstance(result, SentinelError)
    assert result.category == PROVIDER_INVALID_RESPONSE
    assert result.code == "SENTINEL_PROVIDER_INVALID_RESPONSE"


def test_openai_adapter_not_found_maps_to_unsupported_model(monkeypatch) -> None:
    # REQ-LLM-003
    # unsupported model errors map to standardized provider category
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    not_found_exc = type("NotFoundError", (Exception,), {})

    class _FakeOpenAI:
        def __init__(self, api_key: str, timeout: int) -> None:
            _ = (api_key, timeout)
            self.chat = types.SimpleNamespace(
                completions=types.SimpleNamespace(create=self._create)
            )

        @staticmethod
        def _create(*, model: str, messages: list[dict[str, str]], temperature: int):
            _ = (model, messages, temperature)
            raise not_found_exc()

    fake_module = types.SimpleNamespace(
        OpenAI=_FakeOpenAI,
        APIConnectionError=type("APIConnectionError", (Exception,), {}),
        APIStatusError=type("APIStatusError", (Exception,), {}),
        APITimeoutError=type("APITimeoutError", (Exception,), {}),
        AuthenticationError=type("AuthenticationError", (Exception,), {}),
        BadRequestError=type("BadRequestError", (Exception,), {}),
        NotFoundError=not_found_exc,
        RateLimitError=type("RateLimitError", (Exception,), {}),
    )
    monkeypatch.setitem(sys.modules, "openai", fake_module)

    adapter = OpenAIProviderAdapter()
    result = adapter.invoke(
        ProviderRequest(prompt_text="Return JSON.", model="bad-model", timeout_seconds=5)
    )

    assert isinstance(result, SentinelError)
    assert result.category == PROVIDER_UNSUPPORTED_MODEL
    assert result.code == "SENTINEL_PROVIDER_UNSUPPORTED_MODEL"


def _install_fake_openai_bad_request(monkeypatch, exc_message: str) -> None:
    class BadRequestError(Exception):
        pass

    class _FakeOpenAI:
        def __init__(self, api_key: str, timeout: int) -> None:
            _ = (api_key, timeout)
            self.chat = types.SimpleNamespace(
                completions=types.SimpleNamespace(create=self._create)
            )

        @staticmethod
        def _create(*, model: str, messages: list[dict[str, str]], temperature: int):
            _ = (model, messages, temperature)
            raise BadRequestError(exc_message)

    fake_module = types.SimpleNamespace(
        OpenAI=_FakeOpenAI,
        APIConnectionError=type("APIConnectionError", (Exception,), {}),
        APIStatusError=type("APIStatusError", (Exception,), {}),
        APITimeoutError=type("APITimeoutError", (Exception,), {}),
        AuthenticationError=type("AuthenticationError", (Exception,), {}),
        BadRequestError=BadRequestError,
        NotFoundError=type("NotFoundError", (Exception,), {}),
        RateLimitError=type("RateLimitError", (Exception,), {}),
    )
    monkeypatch.setitem(sys.modules, "openai", fake_module)


def test_openai_adapter_bad_request_sanitizes_sk_shaped_secret_in_details(
    monkeypatch,
) -> None:
    # REQ-F-012, REQ-NF-008, REQ-NF-009
    # deterministic provider error sanitization must redact key-shaped secrets
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    secret = "sk-proj-" + "A" * 48
    _install_fake_openai_bad_request(
        monkeypatch,
        f"model error: invalid {secret} in response",
    )

    adapter = OpenAIProviderAdapter()
    result = adapter.invoke(
        ProviderRequest(prompt_text="x", model="m", timeout_seconds=5)
    )

    assert isinstance(result, SentinelError)
    assert result.category == PROVIDER_UNSUPPORTED_MODEL
    assert result.details is not None
    err_detail = str(result.details.get("error", ""))
    assert secret not in err_detail
    assert "sk-proj" not in err_detail
    assert "REDACTED" in err_detail
    rendered = render_error(result)
    assert secret not in rendered
    assert "sk-proj" not in rendered


def test_openai_adapter_bad_request_sanitizes_authorization_bearer_in_details(
    monkeypatch,
) -> None:
    # REQ-F-012, REQ-NF-008, REQ-NF-009
    # deterministic sanitization must redact auth-header bearer tokens
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    token = "supersecrettoken12345678901234567890"
    _install_fake_openai_bad_request(
        monkeypatch,
        f"model invalid: Authorization: Bearer {token}",
    )

    adapter = OpenAIProviderAdapter()
    result = adapter.invoke(
        ProviderRequest(prompt_text="x", model="m", timeout_seconds=5)
    )

    assert isinstance(result, SentinelError)
    assert result.category == PROVIDER_UNSUPPORTED_MODEL
    assert result.details is not None
    err_detail = str(result.details.get("error", ""))
    assert token not in err_detail
    assert "Bearer [REDACTED]" in err_detail or "[REDACTED]" in err_detail
    assert token not in render_error(result)


def test_openai_adapter_bad_request_sanitizes_openai_api_key_env_echo(monkeypatch) -> None:
    # REQ-F-012, REQ-NF-008, REQ-NF-009
    # deterministic sanitization must redact echoed sensitive env values
    leaked = "x" * 24
    monkeypatch.setenv("OPENAI_API_KEY", leaked)
    _install_fake_openai_bad_request(
        monkeypatch,
        f"model error: echoed {leaked} from provider",
    )

    adapter = OpenAIProviderAdapter()
    result = adapter.invoke(
        ProviderRequest(prompt_text="x", model="m", timeout_seconds=5)
    )

    assert isinstance(result, SentinelError)
    assert result.category == PROVIDER_UNSUPPORTED_MODEL
    assert result.details is not None
    err_detail = str(result.details.get("error", ""))
    assert leaked not in err_detail
    assert leaked not in render_error(result)


def test_openai_adapter_timeout_maps_to_provider_timeout(monkeypatch) -> None:
    # REQ-F-002, REQ-LLM-003
    # provider timeout mapped to standardized error category
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    api_timeout_exc = type("APITimeoutError", (Exception,), {})

    class _FakeOpenAI:
        def __init__(self, api_key: str, timeout: int) -> None:
            _ = (api_key, timeout)
            self.chat = types.SimpleNamespace(
                completions=types.SimpleNamespace(create=self._create)
            )

        @staticmethod
        def _create(*, model: str, messages: list[dict[str, str]], temperature: int):
            _ = (model, messages, temperature)
            raise api_timeout_exc()

    fake_module = types.SimpleNamespace(
        OpenAI=_FakeOpenAI,
        APIConnectionError=type("APIConnectionError", (Exception,), {}),
        APIStatusError=type("APIStatusError", (Exception,), {}),
        APITimeoutError=api_timeout_exc,
        AuthenticationError=type("AuthenticationError", (Exception,), {}),
        BadRequestError=type("BadRequestError", (Exception,), {}),
        NotFoundError=type("NotFoundError", (Exception,), {}),
        RateLimitError=type("RateLimitError", (Exception,), {}),
    )
    monkeypatch.setitem(sys.modules, "openai", fake_module)

    adapter = OpenAIProviderAdapter()
    result = adapter.invoke(
        ProviderRequest(prompt_text="x", model="m", timeout_seconds=5)
    )

    assert isinstance(result, SentinelError)
    assert result.category == PROVIDER_TIMEOUT
    assert result.code == "SENTINEL_PROVIDER_TIMEOUT"
    assert "timed out" in result.message.lower()


def test_openai_adapter_rate_limit_maps_to_provider_rate_limit(monkeypatch) -> None:
    # REQ-LLM-003, REQ-F-010
    # provider rate limit mapped to standardized error
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    rate_limit_exc = type("RateLimitError", (Exception,), {})

    class _FakeOpenAI:
        def __init__(self, api_key: str, timeout: int) -> None:
            _ = (api_key, timeout)
            self.chat = types.SimpleNamespace(
                completions=types.SimpleNamespace(create=self._create)
            )

        @staticmethod
        def _create(*, model: str, messages: list[dict[str, str]], temperature: int):
            _ = (model, messages, temperature)
            raise rate_limit_exc()

    fake_module = types.SimpleNamespace(
        OpenAI=_FakeOpenAI,
        APIConnectionError=type("APIConnectionError", (Exception,), {}),
        APIStatusError=type("APIStatusError", (Exception,), {}),
        APITimeoutError=type("APITimeoutError", (Exception,), {}),
        AuthenticationError=type("AuthenticationError", (Exception,), {}),
        BadRequestError=type("BadRequestError", (Exception,), {}),
        NotFoundError=type("NotFoundError", (Exception,), {}),
        RateLimitError=rate_limit_exc,
    )
    monkeypatch.setitem(sys.modules, "openai", fake_module)

    adapter = OpenAIProviderAdapter()
    result = adapter.invoke(
        ProviderRequest(prompt_text="x", model="m", timeout_seconds=5)
    )

    assert isinstance(result, SentinelError)
    assert result.category == PROVIDER_RATE_LIMIT
