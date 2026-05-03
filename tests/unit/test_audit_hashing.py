from __future__ import annotations

from sentinel.audit.hashing import compute_hashes_for_record_components


def test_hashes_deterministic_for_same_content() -> None:
    base_input = {"a": 1, "b": 2}
    base_configs = {"x": {"k": "v"}}
    base_result = {"status": "PASS"}

    full_record = {
        "audit_version": "1",
        "audit_id": "id",
        "timestamp_utc": "2024-01-01T00:00:00Z",
        "command": "audit record",
        "execution_id": "exec",
        "input_refs": base_input,
        "configs": base_configs,
        "result": base_result,
        "event_ids": [],
        "hashes": {
            "input_hash": "",
            "config_hash": "",
            "result_hash": "",
        },
        "metadata": None,
    }

    h1 = compute_hashes_for_record_components(base_input, base_configs, base_result, full_record)
    h2 = compute_hashes_for_record_components(base_input, base_configs, base_result, full_record)

    assert h1 == h2

