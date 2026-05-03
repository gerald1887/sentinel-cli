"""Unit tests for Guard guardrail evaluator."""

from __future__ import annotations

from sentinel.guardrail.evaluator import evaluate_assertions


def test_exists_pass_and_fail() -> None:
    result = evaluate_assertions(
        input_json={"a": 1},
        assertions=[
            {"id": "e1", "type": "exists", "path": "/a"},
            {"id": "e2", "type": "exists", "path": "/missing"},
        ],
    )

    assert result.status == "FAIL"
    assert result.summary["total"] == 2
    assert result.summary["pass"] == 1
    assert result.summary["fail"] == 1
    assert result.summary["error"] == 0
    assert result.assertions[0].status == "PASS"
    assert result.assertions[0].message == "Path exists."
    assert result.assertions[0].expected is None
    assert result.assertions[0].actual == 1
    assert result.assertions[1].status == "FAIL"
    assert result.assertions[1].message == "Path does not exist."
    assert result.assertions[1].expected is None
    assert result.assertions[1].actual is None


def test_not_exists_pass_and_fail() -> None:
    result = evaluate_assertions(
        input_json={"a": 1},
        assertions=[
            {"id": "n1", "type": "not_exists", "path": "/missing"},
            {"id": "n2", "type": "not_exists", "path": "/a"},
        ],
    )

    assert result.status == "FAIL"
    assert result.summary["total"] == 2
    assert result.summary["pass"] == 1
    assert result.summary["fail"] == 1
    assert result.assertions[0].status == "PASS"
    assert result.assertions[0].message == "Path does not exist."
    assert result.assertions[1].status == "FAIL"
    assert result.assertions[1].message == "Path exists."


def test_equals_pass_and_fail() -> None:
    result = evaluate_assertions(
        input_json={"a": 1},
        assertions=[
            {"id": "eq1", "type": "equals", "path": "/a", "value": 1},
            {"id": "eq2", "type": "equals", "path": "/a", "value": 2},
        ],
    )

    assert result.status == "FAIL"
    assert result.summary["fail"] == 1
    assert result.assertions[0].status == "PASS"
    assert result.assertions[0].message == "Value matched."
    assert result.assertions[0].expected == 1
    assert result.assertions[0].actual == 1
    assert result.assertions[1].status == "FAIL"
    assert result.assertions[1].message == "Value did not match."
    assert result.assertions[1].expected == 2
    assert result.assertions[1].actual == 1


def test_not_equals_pass_and_fail() -> None:
    result = evaluate_assertions(
        input_json={"a": 1},
        assertions=[
            {"id": "ne1", "type": "not_equals", "path": "/a", "value": 2},
            {"id": "ne2", "type": "not_equals", "path": "/a", "value": 1},
        ],
    )

    assert result.status == "FAIL"
    assert result.summary["fail"] == 1
    assert result.assertions[0].status == "PASS"
    assert result.assertions[0].message == "Value did not match forbidden value."
    assert result.assertions[1].status == "FAIL"
    assert result.assertions[1].message == "Value matched forbidden value."


def test_in_pass_and_fail() -> None:
    result = evaluate_assertions(
        input_json={"a": "x"},
        assertions=[
            {"id": "in1", "type": "in", "path": "/a", "values": ["x", "y"]},
            {"id": "in2", "type": "in", "path": "/a", "values": ["y", "z"]},
        ],
    )

    assert result.status == "FAIL"
    assert result.summary["fail"] == 1
    assert result.assertions[0].status == "PASS"
    assert result.assertions[0].message == "Value matched allowed set."
    assert result.assertions[0].expected == ["x", "y"]
    assert result.assertions[0].actual == "x"
    assert result.assertions[1].status == "FAIL"
    assert result.assertions[1].message == "Value did not match allowed set."
    assert result.assertions[1].expected == ["y", "z"]
    assert result.assertions[1].actual == "x"


def test_not_in_pass_and_fail() -> None:
    result = evaluate_assertions(
        input_json={"a": "x"},
        assertions=[
            {"id": "ni1", "type": "not_in", "path": "/a", "values": ["y", "z"]},
            {"id": "ni2", "type": "not_in", "path": "/a", "values": ["x", "y"]},
        ],
    )

    assert result.status == "FAIL"
    assert result.summary["fail"] == 1
    assert result.assertions[0].status == "PASS"
    assert result.assertions[0].message == "Value did not match forbidden set."
    assert result.assertions[1].status == "FAIL"
    assert result.assertions[1].message == "Value matched forbidden set."


def test_array_index_path_and_root_path_resolution() -> None:
    result = evaluate_assertions(
        input_json={"items": [{"name": "alice"}]},
        assertions=[
            {"id": "a1", "type": "equals", "path": "/items/0/name", "value": "alice"},
            {"id": "a2", "type": "exists", "path": "/"},
        ],
    )

    assert result.status == "PASS"
    assert result.summary["total"] == 2
    assert result.summary["fail"] == 0
    assert result.assertions[0].actual == "alice"
    assert result.assertions[1].actual == {"items": [{"name": "alice"}]}


def test_nested_object_path_resolution() -> None:
    result = evaluate_assertions(
        input_json={"user": {"profile": {"name": "alice"}}},
        assertions=[
            {"id": "n1", "type": "equals", "path": "/user/profile/name", "value": "alice"},
        ],
    )

    assert result.status == "PASS"
    assert result.summary["total"] == 1
    assert result.summary["fail"] == 0
    assert result.assertions[0].actual == "alice"


def test_missing_path_behavior_for_relevant_types() -> None:
    result = evaluate_assertions(
        input_json={"a": 1},
        assertions=[
            {"id": "m1", "type": "exists", "path": "/missing"},
            {"id": "m2", "type": "not_exists", "path": "/missing"},
            {"id": "m3", "type": "equals", "path": "/missing", "value": 1},
            {"id": "m4", "type": "not_equals", "path": "/missing", "value": 1},
            {"id": "m5", "type": "in", "path": "/missing", "values": [1, 2]},
            {"id": "m6", "type": "not_in", "path": "/missing", "values": [1, 2]},
        ],
    )

    assert result.status == "FAIL"
    assert result.summary["total"] == 6
    assert result.summary["fail"] == 5
    assert [item.status for item in result.assertions] == ["FAIL", "PASS", "FAIL", "FAIL", "FAIL", "FAIL"]


def test_unsupported_type_returns_error_result() -> None:
    result = evaluate_assertions(
        input_json={"a": 1},
        assertions=[{"id": "u1", "type": "gt", "path": "/a"}],
    )

    assert result.status == "ERROR"
    assert result.summary["total"] == 0
    assert result.summary["pass"] == 0
    assert result.summary["fail"] == 0
    assert result.summary["error"] == 1
    assert result.assertions == []


def test_missing_value_or_values_returns_error_result() -> None:
    missing_value = evaluate_assertions(
        input_json={"a": 1},
        assertions=[{"id": "e1", "type": "equals", "path": "/a"}],
    )
    missing_values = evaluate_assertions(
        input_json={"a": 1},
        assertions=[{"id": "i1", "type": "in", "path": "/a"}],
    )

    assert missing_value.status == "ERROR"
    assert missing_value.summary["total"] == 0
    assert missing_value.summary["error"] == 1
    assert missing_value.assertions == []
    assert missing_values.status == "ERROR"
    assert missing_values.summary["total"] == 0
    assert missing_values.summary["error"] == 1
    assert missing_values.assertions == []


def test_malformed_path_returns_error_result() -> None:
    malformed = evaluate_assertions(
        input_json={"a": 1},
        assertions=[{"id": "p1", "type": "exists", "path": "a"}],
    )
    malformed_array_token = evaluate_assertions(
        input_json={"items": [1]},
        assertions=[{"id": "p2", "type": "exists", "path": "/items/not-an-index"}],
    )

    assert malformed.status == "ERROR"
    assert malformed.summary["total"] == 0
    assert malformed.summary["error"] == 1
    assert malformed.assertions == []

    assert malformed_array_token.status == "ERROR"
    assert malformed_array_token.summary["total"] == 0
    assert malformed_array_token.summary["error"] == 1
    assert malformed_array_token.assertions == []


def test_malformed_assertion_core_fields_return_error_result() -> None:
    missing_id = evaluate_assertions(
        input_json={"a": 1},
        assertions=[{"type": "exists", "path": "/a"}],
    )
    wrong_type_for_path = evaluate_assertions(
        input_json={"a": 1},
        assertions=[{"id": "x", "type": "exists", "path": 123}],
    )

    assert missing_id.status == "ERROR"
    assert missing_id.summary["total"] == 0
    assert missing_id.summary["error"] == 1
    assert missing_id.assertions == []

    assert wrong_type_for_path.status == "ERROR"
    assert wrong_type_for_path.summary["total"] == 0
    assert wrong_type_for_path.summary["error"] == 1
    assert wrong_type_for_path.assertions == []


def test_assertion_order_is_preserved() -> None:
    result = evaluate_assertions(
        input_json={"a": 1},
        assertions=[
            {"id": "third", "type": "equals", "path": "/a", "value": 0},
            {"id": "first", "type": "exists", "path": "/a"},
            {"id": "second", "type": "not_exists", "path": "/missing"},
        ],
    )

    assert [item.id for item in result.assertions] == ["third", "first", "second"]


def test_top_level_summary_and_status_semantics() -> None:
    passing = evaluate_assertions(
        input_json={"a": 1},
        assertions=[
            {"id": "s1", "type": "exists", "path": "/a"},
            {"id": "s2", "type": "equals", "path": "/a", "value": 1},
        ],
    )
    failing = evaluate_assertions(
        input_json={"a": 1},
        assertions=[
            {"id": "s3", "type": "exists", "path": "/missing"},
            {"id": "s4", "type": "equals", "path": "/a", "value": 2},
        ],
    )

    assert passing.status == "PASS"
    assert passing.summary["total"] == 2
    assert passing.summary["pass"] == 2
    assert passing.summary["fail"] == 0
    assert passing.summary["error"] == 0

    assert failing.status == "FAIL"
    assert failing.summary["total"] == 2
    assert failing.summary["pass"] == 0
    assert failing.summary["fail"] == 2
    assert failing.summary["error"] == 0

