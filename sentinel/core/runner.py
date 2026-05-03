"""Core contract-run orchestrator used across Sentinel capabilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal, Optional

from sentinel.core.errors import INTERNAL_ERROR, JSON_PARSE_ERROR, SentinelError
from sentinel.core.files import load_prompt, load_schema
from sentinel.core.schema import validate_instance, validate_schema_structure
from sentinel.providers import get_provider_adapter
from sentinel.providers.base import ProviderRequest


@dataclass(frozen=True, slots=True)
class RunResult:
    status: Literal["PASS", "FAIL", "ERROR"]
    error: Optional[SentinelError] = None
    approved_output: object | None = None


def _parse_json_response(raw: str) -> object | SentinelError:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        return SentinelError(
            category=JSON_PARSE_ERROR,
            code="SENTINEL_JSON_PARSE_ERROR",
            message="Provider response is not valid JSON.",
            details={"error": str(exc)},
        )


def run_contract(
    prompt_path: str,
    schema_path: str,
    provider: str,
    model: str,
    timeout: int,
) -> RunResult:
    try:
        prompt = load_prompt(prompt_path)
        if isinstance(prompt, SentinelError):
            return RunResult(status="ERROR", error=prompt)

        schema = load_schema(schema_path)
        if isinstance(schema, SentinelError):
            return RunResult(status="ERROR", error=schema)

        schema_err = validate_schema_structure(schema)
        if schema_err is not None:
            return RunResult(status="ERROR", error=schema_err)

        adapter = get_provider_adapter(provider)
        if isinstance(adapter, SentinelError):
            return RunResult(status="ERROR", error=adapter)

        provider_request = ProviderRequest(
            prompt_text=prompt,
            model=model,
            timeout_seconds=timeout,
        )
        provider_response = adapter.invoke(provider_request)
        if isinstance(provider_response, SentinelError):
            return RunResult(status="ERROR", error=provider_response)

        contract_payload = _parse_json_response(provider_response.raw_text)
        if isinstance(contract_payload, SentinelError):
            return RunResult(status="FAIL", error=contract_payload)

        validation_err = validate_instance(contract_payload, schema)
        if validation_err is not None:
            return RunResult(status="FAIL", error=validation_err)

        return RunResult(status="PASS", error=None, approved_output=contract_payload)
    except Exception as exc:  # noqa: BLE001
        return RunResult(
            status="ERROR",
            error=SentinelError(
                category=INTERNAL_ERROR,
                code="SENTINEL_INTERNAL_ERROR",
                message="Unexpected internal error.",
                details={"error": str(exc)},
            ),
        )

