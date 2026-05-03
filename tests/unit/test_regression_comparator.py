"""Unit tests for Regression exact comparator."""

from __future__ import annotations

from sentinel.testkit.comparator import compare_json


def test_scalar_equality() -> None:
    assert compare_json(1, 1) == []


def test_scalar_mismatch() -> None:
    diffs = compare_json("a", "b")
    assert len(diffs) == 1
    assert diffs[0].record_type == "mismatch"
    assert diffs[0].path == ""


def test_object_equality_ignores_key_order() -> None:
    diffs = compare_json({"a": 1, "b": 2}, {"b": 2, "a": 1})
    assert diffs == []


def test_missing_object_key() -> None:
    diffs = compare_json({"a": 1, "b": 2}, {"a": 1})
    assert len(diffs) == 1
    assert diffs[0].record_type == "missing"
    assert diffs[0].path == "/b"


def test_extra_object_key() -> None:
    diffs = compare_json({"a": 1}, {"a": 1, "b": 2})
    assert len(diffs) == 1
    assert diffs[0].record_type == "extra"
    assert diffs[0].path == "/b"


def test_nested_object_mismatch_path() -> None:
    diffs = compare_json({"items": [{"name": "x"}]}, {"items": [{"name": "y"}]})
    assert len(diffs) == 1
    assert diffs[0].record_type == "mismatch"
    assert diffs[0].path == "/items/0/name"


def test_array_equality() -> None:
    assert compare_json([1, {"a": 2}], [1, {"a": 2}]) == []


def test_array_positional_mismatch() -> None:
    diffs = compare_json([1, 2, 3], [1, 9, 3])
    assert len(diffs) == 1
    assert diffs[0].record_type == "mismatch"
    assert diffs[0].path == "/1"


def test_array_missing_and_extra_elements() -> None:
    missing = compare_json([1, 2, 3], [1, 2])
    assert len(missing) == 1
    assert missing[0].record_type == "missing"
    assert missing[0].path == "/2"

    extra = compare_json([1], [1, 2])
    assert len(extra) == 1
    assert extra[0].record_type == "extra"
    assert extra[0].path == "/1"


def test_type_mismatch() -> None:
    diffs = compare_json({"a": 1}, [{"a": 1}])
    assert len(diffs) == 1
    assert diffs[0].record_type == "mismatch"
    assert diffs[0].path == ""


def test_json_pointer_escaping() -> None:
    diffs = compare_json({"a/b": {"x~y": 1}}, {"a/b": {"x~y": 2}})
    assert len(diffs) == 1
    assert diffs[0].path == "/a~1b/x~0y"


def test_deterministic_ordering_multiple_diffs() -> None:
    diffs = compare_json(
        {"z": 1, "a": 2, "m": {"k2": 1, "k1": 2}},
        {"a": 9, "b": 3, "m": {"k2": 7}},
    )
    assert [d.path for d in diffs] == ["/z", "/b", "/a", "/m/k1", "/m/k2"]
    assert [d.record_type for d in diffs] == [
        "missing",
        "extra",
        "mismatch",
        "missing",
        "mismatch",
    ]


def test_ignore_paths_omits_diffs_under_pointer() -> None:
    assert (
        compare_json(
            {"keep": 1, "drop": 2},
            {"keep": 1, "drop": 9},
            ignore_paths=("/drop",),
        )
        == []
    )


def test_ignore_paths_non_ignored_fields_still_diff() -> None:
    diffs = compare_json(
        {"keep": 1, "drop": 2},
        {"keep": 9, "drop": 2},
        ignore_paths=("/drop",),
    )
    assert len(diffs) == 1
    assert diffs[0].path == "/keep"
    assert diffs[0].record_type == "mismatch"

