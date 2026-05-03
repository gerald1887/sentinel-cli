from __future__ import annotations

from sentinel.audit.normalizer import NormalizationError, normalize_for_hash


def test_normalizer_sorts_object_keys_and_preserves_arrays() -> None:
    value = {"b": 2, "a": 1, "list": [3, 1, 2]}
    encoded = normalize_for_hash(value)
    # Keys must be sorted lexicographically and list order preserved.
    assert encoded == '{"a":1,"b":2,"list":[3,1,2]}'


def test_normalizer_rejects_unsupported_types() -> None:
    class Custom:
        ...

    try:
        normalize_for_hash(Custom())
        raised = False
    except NormalizationError:
        raised = True

    assert raised

