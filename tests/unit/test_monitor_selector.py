"""Monitor selector unit tests."""

from __future__ import annotations

from sentinel.monitor.selector import InspectFilters, select_events
from sentinel.monitor.types import EVENT_VERSION, Event


def _event(
    event_id: str,
    timestamp_utc: str,
    command: str,
    provider: str | None,
    model: str | None,
    event_type: str,
    case_id: str | None,
    status: str,
) -> Event:
    return Event(
        event_version=EVENT_VERSION,
        event_id=event_id,
        event_type=event_type,
        timestamp_utc=timestamp_utc,
        command=command,
        provider=provider,
        model=model,
        suite_case_id=case_id,
        status=status,
        exit_code=0,
        duration_ms=1,
        contract_status=None,
        guard_status=None,
        drift_status=None,
        error_category=None,
        error_code=None,
        refusal_detected=None,
        input_tokens=None,
        output_tokens=None,
        total_tokens=None,
        artifact_refs={"source": "s"},
        metadata=None,
    )


def _events() -> list[Event]:
    return [
        _event("e1", "2026-01-01T00:00:00Z", "run", "openai", "m1", "contract.run", "c1", "PASS"),
        _event("e2", "2026-01-02T00:00:00Z", "test", "anthropic", "m2", "guard.check", "c2", "FAIL"),
        _event("e3", "2026-01-03T00:00:00Z", "run", None, None, "contract.run", "c3", "PASS"),
    ]


def test_each_filter_works_independently() -> None:
    events = _events()
    assert [e.event_id for e in select_events(events, InspectFilters(command="run"))] == ["e1", "e3"]  # type: ignore[arg-type]
    assert [e.event_id for e in select_events(events, InspectFilters(provider="anthropic"))] == ["e2"]  # type: ignore[arg-type]
    assert [e.event_id for e in select_events(events, InspectFilters(model="m1"))] == ["e1"]  # type: ignore[arg-type]
    assert [e.event_id for e in select_events(events, InspectFilters(event_type="contract.run"))] == ["e1", "e3"]  # type: ignore[arg-type]
    assert [e.event_id for e in select_events(events, InspectFilters(case_id="c2"))] == ["e2"]  # type: ignore[arg-type]
    assert [e.event_id for e in select_events(events, InspectFilters(status="PASS"))] == ["e1", "e3"]  # type: ignore[arg-type]


def test_combined_filters_respect_fixed_order() -> None:
    events = _events()
    selected = select_events(
        events,
        InspectFilters(
            from_timestamp_utc="2026-01-01T00:00:00Z",
            to_timestamp_utc="2026-01-03T00:00:00Z",
            command="run",
            provider="openai",
            model="m1",
            event_type="contract.run",
            case_id="c1",
            status="PASS",
        ),
    )
    assert [e.event_id for e in selected] == ["e1"]  # type: ignore[arg-type]


def test_from_is_inclusive() -> None:
    events = _events()
    selected = select_events(events, InspectFilters(from_timestamp_utc="2026-01-02T00:00:00Z"))
    assert [e.event_id for e in selected] == ["e2", "e3"]  # type: ignore[arg-type]


def test_to_is_inclusive() -> None:
    events = _events()
    selected = select_events(events, InspectFilters(to_timestamp_utc="2026-01-02T00:00:00Z"))
    assert [e.event_id for e in selected] == ["e1", "e2"]  # type: ignore[arg-type]


def test_last_n_applied_after_all_filters() -> None:
    events = _events() + [_event("e4", "2026-01-04T00:00:00Z", "run", None, None, "contract.run", "c4", "PASS")]
    selected = select_events(events, InspectFilters(command="run", last=2))
    assert [e.event_id for e in selected] == ["e3", "e4"]  # type: ignore[arg-type]


def test_file_order_preserved_and_no_sorting_occurs() -> None:
    events = [
        _event("e10", "2026-01-03T00:00:00Z", "run", None, None, "contract.run", "c10", "PASS"),
        _event("e2", "2026-01-01T00:00:00Z", "run", None, None, "contract.run", "c2", "PASS"),
    ]
    selected = select_events(events, InspectFilters(command="run"))
    assert [e.event_id for e in selected] == ["e10", "e2"]  # type: ignore[arg-type]


def test_invalid_filter_values_return_explicit_error() -> None:
    events = _events()
    bad_timestamp = select_events(events, InspectFilters(from_timestamp_utc="2026-01-01"))
    assert not isinstance(bad_timestamp, list)
    assert bad_timestamp.code == "SENTINEL_MONITOR_INVALID_FILTER"

    bad_last = select_events(events, InspectFilters(last=0))
    assert not isinstance(bad_last, list)
    assert bad_last.code == "SENTINEL_MONITOR_INVALID_FILTER"
