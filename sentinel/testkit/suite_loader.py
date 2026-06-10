"""Regression suite loader and validator."""

from __future__ import annotations

import os

import yaml

from sentinel.core.errors import SCHEMA_INVALID, SentinelError, file_not_found, file_read_error
from sentinel.testkit.types import (
    SuiteCaseDefinition,
    SuiteDefinition,
)


def _suite_error(code: str, message: str, details: dict[str, object] | None = None) -> SentinelError:
    return SentinelError(
        category=SCHEMA_INVALID,
        code=code,
        message=message,
        details=details,
    )


def load_suite(suite_path: str) -> SuiteDefinition | SentinelError:
    """Load and validate a suite YAML file."""
    if not os.path.exists(suite_path):
        return file_not_found(suite_path)

    try:
        with open(suite_path, encoding="utf-8") as fh:
            raw = fh.read()
    except Exception as exc:  # noqa: BLE001
        return file_read_error(suite_path, str(exc))

    try:
        loaded = yaml.safe_load(raw)
    except Exception as exc:  # noqa: BLE001
        return _suite_error(
            code="SENTINEL_SUITE_INVALID_YAML",
            message="Suite file is not valid YAML.",
            details={"path": suite_path, "error": str(exc)},
        )

    if not isinstance(loaded, dict):
        return _suite_error(
            code="SENTINEL_SUITE_INVALID_TOP_LEVEL",
            message="Suite top-level YAML must be a mapping.",
            details={"path": suite_path},
        )

    command = loaded.get("command")
    if command is None or not isinstance(command, str):
        return _suite_error(
            code="SENTINEL_SUITE_MISSING_COMMAND",
            message="Suite must include string field 'command'.",
            details={"path": suite_path},
        )

    cases = loaded.get("cases")
    if cases is None:
        return _suite_error(
            code="SENTINEL_SUITE_MISSING_CASES",
            message="Suite must include field 'cases'.",
            details={"path": suite_path},
        )
    if not isinstance(cases, list):
        return _suite_error(
            code="SENTINEL_SUITE_INVALID_CASES_TYPE",
            message="Suite field 'cases' must be a list.",
            details={"path": suite_path},
        )
    if len(cases) == 0:
        return _suite_error(
            code="SENTINEL_SUITE_EMPTY_CASES",
            message="Suite 'cases' must be a non-empty list.",
            details={"path": suite_path},
        )

    seen_ids: set[str] = set()
    normalized_cases: list[SuiteCaseDefinition] = []

    for idx, case in enumerate(cases):
        if not isinstance(case, dict):
            return _suite_error(
                code="SENTINEL_SUITE_INVALID_CASE_TYPE",
                message="Each suite case must be a mapping.",
                details={"path": suite_path, "case_index": idx},
            )

        case_id = case.get("id")
        if case_id is None or not isinstance(case_id, str) or case_id == "":
            return _suite_error(
                code="SENTINEL_SUITE_MISSING_CASE_ID",
                message="Each suite case must include non-empty string field 'id'.",
                details={"path": suite_path, "case_index": idx},
            )

        if case_id in seen_ids:
            return _suite_error(
                code="SENTINEL_SUITE_DUPLICATE_CASE_ID",
                message="Suite case ids must be unique.",
                details={"path": suite_path, "case_id": case_id},
            )
        seen_ids.add(case_id)

        for field_name in ("prompt", "schema", "provider", "model"):
            field_val = case.get(field_name)
            if field_val is None:
                return _suite_error(
                    code="SENTINEL_SUITE_MISSING_CASE_FIELD",
                    message=f"Suite case is missing required field '{field_name}'.",
                    details={"path": suite_path, "case_id": case_id, "field": field_name},
                )
            if not isinstance(field_val, str):
                return _suite_error(
                    code="SENTINEL_SUITE_INVALID_CASE_FIELD_TYPE",
                    message=f"Suite case field '{field_name}' must be a string.",
                    details={"path": suite_path, "case_id": case_id, "field": field_name},
                )

        timeout = case.get("timeout", 60)
        if not isinstance(timeout, int):
            return _suite_error(
                code="SENTINEL_SUITE_INVALID_TIMEOUT_TYPE",
                message="Suite case field 'timeout' must be an integer.",
                details={"path": suite_path, "case_id": case_id},
            )

        contract_version = case.get("contract_version", "v1")
        if not isinstance(contract_version, str):
            return _suite_error(
                code="SENTINEL_SUITE_INVALID_CONTRACT_VERSION_TYPE",
                message="Suite case field 'contract_version' must be a string.",
                details={"path": suite_path, "case_id": case_id},
            )

        if "ignore_paths" in case:
            raw_ignore = case["ignore_paths"]
            if not isinstance(raw_ignore, list):
                return _suite_error(
                    code="SENTINEL_SUITE_INVALID_IGNORE_PATHS_TYPE",
                    message="Suite case field 'ignore_paths' must be a list of strings.",
                    details={"path": suite_path, "case_id": case_id},
                )
            for item in raw_ignore:
                if not isinstance(item, str):
                    return _suite_error(
                        code="SENTINEL_SUITE_INVALID_IGNORE_PATHS_ITEM_TYPE",
                        message="Suite case field 'ignore_paths' must be a list of strings.",
                        details={"path": suite_path, "case_id": case_id},
                    )
            ignore_paths: tuple[str, ...] = tuple(raw_ignore)
        else:
            ignore_paths = ()

        normalized_cases.append(
            SuiteCaseDefinition(
                case_id=case_id,
                prompt=case["prompt"],
                schema=case["schema"],
                provider=case["provider"],
                model=case["model"],
                timeout=timeout,
                contract_version=contract_version,
                ignore_paths=ignore_paths,
            )
        )

    return SuiteDefinition(
        command=command,
        suite_path=suite_path,
        cases=normalized_cases,
    )

