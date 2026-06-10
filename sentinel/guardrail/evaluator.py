"""Guard guardrail assertion evaluator."""

from __future__ import annotations

from sentinel.guardrail.types import (
    GuardAssertionResult,
    GuardCheckResult,
    GuardCheckSummary,
)


def _error_result() -> GuardCheckResult:
    return GuardCheckResult(
        status="ERROR",
        summary=GuardCheckSummary(total=0, **{"pass": 0}, fail=0, error=1),
        assertions=[],
    )


def _decode_pointer_token(token: str) -> str:
    decoded: list[str] = []
    idx = 0
    while idx < len(token):
        char = token[idx]
        if char != "~":
            decoded.append(char)
            idx += 1
            continue
        if idx + 1 >= len(token):
            raise ValueError("malformed pointer escape")
        next_char = token[idx + 1]
        if next_char == "0":
            decoded.append("~")
        elif next_char == "1":
            decoded.append("/")
        else:
            raise ValueError("malformed pointer escape")
        idx += 2
    return "".join(decoded)


def _resolve_pointer(input_json: object, path: str) -> tuple[bool, object | None]:
    if path == "/":
        return True, input_json
    if not path.startswith("/"):
        raise ValueError("malformed pointer path")

    tokens = path[1:].split("/")
    current: object = input_json

    for raw_token in tokens:
        token = _decode_pointer_token(raw_token)
        if isinstance(current, dict):
            if token not in current:
                return False, None
            current = current[token]
            continue
        if isinstance(current, list):
            if token == "-":
                raise ValueError("malformed array index token")
            try:
                index = int(token)
            except ValueError as exc:
                raise ValueError("malformed array index token") from exc
            if str(index) != token:
                raise ValueError("malformed array index token")
            if index < 0 or index >= len(current):
                return False, None
            current = current[index]
            continue
        return False, None

    return True, current


def evaluate_assertions(input_json: object, assertions: list[dict]) -> GuardCheckResult:
    """Evaluate loaded assertions against loaded JSON input."""
    try:
        results: list[GuardAssertionResult] = []
        failed = 0

        for assertion in assertions:
            assertion_id = assertion["id"]
            assertion_type = assertion["type"]
            path = assertion["path"]

            if not isinstance(assertion_id, str) or not isinstance(assertion_type, str) or not isinstance(path, str):
                return _error_result()

            if assertion_type not in {"exists", "not_exists", "equals", "not_equals", "in", "not_in"}:
                return _error_result()

            if assertion_type in {"equals", "not_equals"} and "value" not in assertion:
                return _error_result()
            if assertion_type in {"in", "not_in"}:
                if "values" not in assertion or not isinstance(assertion["values"], list):
                    return _error_result()

            found, actual = _resolve_pointer(input_json, path)

            expected: object | None = None
            status = "FAIL"
            message = ""

            if assertion_type == "exists":
                status = "PASS" if found else "FAIL"
                message = "Path exists." if found else "Path does not exist."
            elif assertion_type == "not_exists":
                status = "PASS" if not found else "FAIL"
                message = "Path does not exist." if not found else "Path exists."
            elif assertion_type == "equals":
                expected = assertion["value"]
                status = "PASS" if found and actual == expected else "FAIL"
                message = "Value matched." if status == "PASS" else "Value did not match."
            elif assertion_type == "not_equals":
                expected = assertion["value"]
                status = "PASS" if found and actual != expected else "FAIL"
                message = (
                    "Value did not match forbidden value." if status == "PASS" else "Value matched forbidden value."
                )
            elif assertion_type == "in":
                expected = assertion["values"]
                status = "PASS" if found and actual in expected else "FAIL"
                message = "Value matched allowed set." if status == "PASS" else "Value did not match allowed set."
            elif assertion_type == "not_in":
                expected = assertion["values"]
                status = "PASS" if found and actual not in expected else "FAIL"
                message = "Value did not match forbidden set." if status == "PASS" else "Value matched forbidden set."

            if status == "FAIL":
                failed += 1

            results.append(
                GuardAssertionResult(
                    id=assertion_id,
                    status=status,
                    type=assertion_type,
                    path=path,
                    expected=expected,
                    actual=actual if found else None,
                    message=message,
                )
            )

        overall_status = "PASS" if failed == 0 else "FAIL"
        total = len(results)
        return GuardCheckResult(
            status=overall_status,
            summary=GuardCheckSummary(
                total=total,
                **{"pass": total - failed},
                fail=failed,
                error=0,
            ),
            assertions=results,
        )
    except (KeyError, TypeError, ValueError):
        return _error_result()

