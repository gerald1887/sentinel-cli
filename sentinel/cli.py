"""Sentinel CLI entry-point."""

from __future__ import annotations

import argparse
import json

import yaml

from sentinel import __version__
from sentinel.audit.runner import (
    SelectionFilters as AuditSelectionFilters,
)
from sentinel.audit.runner import (
    run_audit_inspect,
    run_audit_record,
    run_audit_replay,
    run_audit_verify,
)
from sentinel.core.errors import JSON_PARSE_ERROR, SentinelError, file_not_found, render_error
from sentinel.core.files import load_schema
from sentinel.core.runner import run_contract
from sentinel.core.schema import validate_instance, validate_schema_structure
from sentinel.guardrail.evaluator import evaluate_assertions
from sentinel.monitor import (
    InspectFilters,
    append_event,
    compute_signals,
    load_signal_definitions,
    map_source_artifact_to_event,
    read_events,
    render_inspect_events,
    render_summary,
    select_events,
    validate_event,
)
from sentinel.monitor.output import render_check
from sentinel.monitor.rule_engine import evaluate_rules, load_rule_definitions


def _fail(prefix: str, err: SentinelError) -> int:
    print(f"{prefix} ERROR")
    print(f"{err.category} {err.code} {err.message}")
    return 2


def _print_guard_summary(summary: dict[str, int]) -> None:
    print(
        "GUARD SUMMARY "
        f"total={summary['total']} pass={summary['pass']} fail={summary['fail']} error={summary['error']}"
    )

# ---------------------------------------------------------------------------
# Parser helpers
# ---------------------------------------------------------------------------

def _add_filter_args(parser: argparse.ArgumentParser, *, include_audit_id: bool = False) -> None:
    """Add the standard timestamp/last/field filter arguments shared across inspect-style subcommands."""
    parser.add_argument(
        "--from",
        dest="from_timestamp_utc",
        required=False,
        metavar="TIMESTAMP",
        help="Inclusive lower timestamp bound (ISO-8601 UTC).",
    )
    parser.add_argument(
        "--to",
        dest="to_timestamp_utc",
        required=False,
        metavar="TIMESTAMP",
        help="Inclusive upper timestamp bound (ISO-8601 UTC).",
    )
    parser.add_argument(
        "--last",
        type=int,
        required=False,
        metavar="N",
        help="Return last N records after all other filters.",
    )
    parser.add_argument(
        "--command",
        dest="filter_command",
        required=False,
        metavar="COMMAND",
        help="Filter by command.",
    )
    parser.add_argument("--provider", required=False, metavar="PROVIDER", help="Filter by provider.")
    parser.add_argument("--model", required=False, metavar="MODEL", help="Filter by model.")
    parser.add_argument(
        "--event-type",
        dest="inspect_event_type",
        required=False,
        metavar="TYPE",
        help="Filter by event type.",
    )
    parser.add_argument("--case-id", required=False, metavar="CASE_ID", help="Filter by suite case id.")
    parser.add_argument("--status", required=False, metavar="STATUS", help="Filter by status.")
    if include_audit_id:
        parser.add_argument("--audit-id", required=False, metavar="AUDIT_ID", help="Filter by audit id.")


def _build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="sentinel",
        description="Sentinel CLI – Contract Enforcement Engine.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"sentinel {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")

    # --- run subcommand ---------------------------------------------------
    run_parser = subparsers.add_parser("run", help="Execute a contract run.")
    run_parser.add_argument("--prompt", required=True, metavar="PATH", help="Path to the prompt file.")
    run_parser.add_argument("--schema", required=True, metavar="PATH", help="Path to the JSON-schema file.")
    run_parser.add_argument("--provider", required=True, metavar="PROVIDER", help="Provider name (e.g. openai).")
    run_parser.add_argument("--model", required=True, metavar="MODEL", help="Model identifier (e.g. gpt-4o).")
    run_parser.add_argument(
        "--timeout", type=int, default=60, metavar="SECONDS", help="Request timeout in seconds (default: 60)."
    )
    run_parser.add_argument(
        "--assertions", required=False, metavar="PATH", help="Optional path to a guard assertions file."
    )

    # --- validate subcommand ----------------------------------------------
    validate_parser = subparsers.add_parser("validate", help="Validate JSON input against a schema.")
    validate_parser.add_argument("--input", required=True, metavar="PATH", help="Path to input JSON file.")
    validate_parser.add_argument("--schema", required=True, metavar="PATH", help="Path to the JSON-schema file.")

    # --- test subcommand --------------------------------------------------
    test_parser = subparsers.add_parser("test", help="Regression testkit commands.")
    test_subparsers = test_parser.add_subparsers(dest="test_command", required=True)

    test_run_parser = test_subparsers.add_parser("run", help="Run a Regression test suite.")
    test_run_parser.add_argument("--suite", required=True, metavar="PATH", help="Path to the suite YAML file.")
    test_update_parser = test_subparsers.add_parser("update", help="Update Regression snapshots.")
    test_update_parser.add_argument("--suite", required=True, metavar="PATH", help="Path to the suite YAML file.")

    # --- guard subcommand -------------------------------------------------
    guard_parser = subparsers.add_parser("guard", help="Guardrail commands.")
    guard_subparsers = guard_parser.add_subparsers(dest="guard_command", required=True)

    guard_check_parser = guard_subparsers.add_parser("check", help="Run a guard check.")
    guard_check_parser.add_argument(
        "--input", required=True, metavar="PATH", help="Path to the model output JSON file."
    )
    guard_check_parser.add_argument(
        "--assertions", required=True, metavar="PATH", help="Path to the assertions file."
    )

    # --- drift subcommand -------------------------------------------------
    drift_parser = subparsers.add_parser("drift", help="Drift detection commands.")
    drift_subparsers = drift_parser.add_subparsers(dest="drift_command", required=True)

    drift_baseline_parser = drift_subparsers.add_parser("baseline", help="Build drift baseline.")
    drift_baseline_parser.add_argument("--suite", required=True, metavar="PATH", help="Path to the suite YAML file.")
    drift_baseline_parser.add_argument(
        "--metrics", required=True, metavar="PATH", help="Path to the metrics config file."
    )
    drift_baseline_parser.add_argument(
        "--output", required=True, metavar="PATH", help="Path to write baseline artifact JSON."
    )

    drift_check_parser = drift_subparsers.add_parser("check", help="Check drift against baseline.")
    drift_check_parser.add_argument("--suite", required=True, metavar="PATH", help="Path to the suite YAML file.")
    drift_check_parser.add_argument(
        "--metrics", required=True, metavar="PATH", help="Path to the metrics config file."
    )
    drift_check_parser.add_argument(
        "--baseline", required=True, metavar="PATH", help="Path to baseline artifact JSON."
    )
    drift_check_parser.add_argument(
        "--thresholds", required=True, metavar="PATH", help="Path to thresholds config file."
    )

    # --- monitor subcommand -----------------------------------------------
    monitor_parser = subparsers.add_parser("monitor", help="Runtime monitor commands.")
    monitor_subparsers = monitor_parser.add_subparsers(dest="monitor_command", required=True)

    monitor_record_parser = monitor_subparsers.add_parser("record", help="Record one monitor event.")
    monitor_record_parser.add_argument(
        "--event-file", required=True, metavar="PATH", help="Path to append event JSONL lines."
    )
    monitor_record_parser.add_argument("--source", required=True, metavar="PATH", help="Path to source artifact JSON.")
    monitor_record_parser.add_argument(
        "--event-type", required=True, metavar="TYPE", help="Event type for recorded event."
    )

    monitor_inspect_parser = monitor_subparsers.add_parser("inspect", help="Inspect monitor events.")
    monitor_inspect_parser.add_argument(
        "--event-file", required=True, metavar="PATH", help="Path to read event JSONL lines."
    )
    _add_filter_args(monitor_inspect_parser)

    monitor_summary_parser = monitor_subparsers.add_parser("summary", help="Compute monitor summary signals.")
    monitor_summary_parser.add_argument(
        "--event-file", required=True, metavar="PATH", help="Path to read event JSONL lines."
    )
    monitor_summary_parser.add_argument(
        "--signals", required=True, metavar="PATH", help="Path to signal config (JSON or YAML)."
    )
    _add_filter_args(monitor_summary_parser)

    monitor_check_parser = monitor_subparsers.add_parser("check", help="Evaluate monitor rules.")
    monitor_check_parser.add_argument("--event-file", required=True, metavar="PATH", help="Path to event JSONL.")
    monitor_check_parser.add_argument("--signals", required=True, metavar="PATH", help="Path to signal config.")
    monitor_check_parser.add_argument("--rules", required=True, metavar="PATH", help="Path to rule config.")
    _add_filter_args(monitor_check_parser)

    # --- audit subcommand ---------------------------------------------------
    audit_root = subparsers.add_parser("audit", help="Compliance audit commands.")
    audit_subparsers = audit_root.add_subparsers(dest="audit_command", required=True)

    audit_record_parser = audit_subparsers.add_parser("record", help="Record an audit artifact.")
    audit_record_parser.add_argument(
        "--audit-file", required=True, metavar="PATH", help="Path to append audit JSONL records."
    )
    audit_record_parser.add_argument(
        "--source", required=True, metavar="PATH", help="Path to Sentinel result artifact JSON."
    )
    audit_record_parser.add_argument(
        "--events", required=False, metavar="PATH", help="Optional path to monitor events JSONL file."
    )

    audit_inspect_parser = audit_subparsers.add_parser("inspect", help="Inspect audit records.")
    audit_inspect_parser.add_argument(
        "--audit-file", required=True, metavar="PATH", help="Path to audit JSONL file."
    )
    _add_filter_args(audit_inspect_parser, include_audit_id=True)

    audit_verify_parser = audit_subparsers.add_parser("verify", help="Verify audit record integrity.")
    audit_verify_parser.add_argument(
        "--audit-file", required=True, metavar="PATH", help="Path to audit JSONL file."
    )
    _add_filter_args(audit_verify_parser, include_audit_id=True)

    audit_replay_parser = audit_subparsers.add_parser("replay", help="Replay a single audit record.")
    audit_replay_parser.add_argument(
        "--audit-file", required=True, metavar="PATH", help="Path to audit JSONL file."
    )
    audit_replay_parser.add_argument("--audit-id", required=True, metavar="AUDIT_ID", help="Audit id to replay.")

    return parser


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def _handle_run(args: argparse.Namespace) -> int:
    result = run_contract(
        prompt_path=args.prompt,
        schema_path=args.schema,
        provider=args.provider,
        model=args.model,
        timeout=args.timeout,
    )

    if result.status == "PASS":
        if args.assertions:
            try:
                with open(args.assertions, encoding="utf-8") as assertions_file:
                    assertions_data = yaml.safe_load(assertions_file)
                assertions = assertions_data["assertions"]
                guard_result = evaluate_assertions(result.approved_output, assertions)
            except Exception:
                _print_guard_summary({"total": 0, "pass": 0, "fail": 0, "error": 1})
                print("INTERNAL_ERROR SENTINEL_ASSERTION_ERROR Guard evaluation failed.")
                return 2

            if guard_result.status == "ERROR":
                _print_guard_summary({"total": 0, "pass": 0, "fail": 0, "error": 1})
                print("INTERNAL_ERROR SENTINEL_ASSERTION_ERROR Guard evaluation failed.")
                return 2

            if guard_result.status == "FAIL":
                _print_guard_summary(guard_result.summary)
                for assertion in guard_result.assertions:
                    if assertion.status != "FAIL":
                        continue
                    print(
                        f"ASSERT {assertion.id} FAIL {assertion.type} {assertion.path} "
                        f"expected={repr(assertion.expected)} actual={repr(assertion.actual)}"
                    )
                return 1

        print("PASS: Contract satisfied")
        return 0

    if result.status == "FAIL":
        print("FAIL: Contract violated")
        if result.error is not None:
            print(render_error(result.error))
        return 1

    print("ERROR: Execution failed")
    if result.error is not None:
        print(render_error(result.error))
    return 2


def _handle_validate(args: argparse.Namespace) -> int:
    try:
        with open(args.input, encoding="utf-8") as input_file:
            raw_input = input_file.read()
    except FileNotFoundError:
        print("ERROR: Execution failed")
        print(render_error(file_not_found(args.input)))
        return 2
    except Exception as exc:  # noqa: BLE001
        print("ERROR: Execution failed")
        print(
            render_error(
                SentinelError(
                    category="FILE_READ_ERROR",
                    code="SENTINEL_FILE_READ_ERROR",
                    message=str(exc),
                    location=args.input,
                )
            )
        )
        return 2

    try:
        input_payload = json.loads(raw_input)
    except (json.JSONDecodeError, ValueError) as exc:
        print("FAIL: Contract violated")
        print(
            render_error(
                SentinelError(
                    category=JSON_PARSE_ERROR,
                    code="SENTINEL_JSON_PARSE_ERROR",
                    message="Input file is not valid JSON.",
                    details={"path": args.input, "error": str(exc)},
                )
            )
        )
        return 1

    schema = load_schema(args.schema)
    if isinstance(schema, SentinelError):
        print("ERROR: Execution failed")
        print(render_error(schema))
        return 2

    schema_err = validate_schema_structure(schema)
    if schema_err is not None:
        print("ERROR: Execution failed")
        print(render_error(schema_err))
        return 2

    validation_err = validate_instance(input_payload, schema)
    if validation_err is not None:
        print("FAIL: Contract violated")
        print(render_error(validation_err))
        return 1

    print("PASS: Contract satisfied")
    return 0


def _handle_test_run(args: argparse.Namespace) -> int:
    from sentinel.core.errors import SentinelError
    from sentinel.testkit.suite_runner import run_suite

    suite_result = run_suite(args.suite)

    if isinstance(suite_result, SentinelError):
        print("TEST RUN ERROR")
        print(f"{suite_result.category} {suite_result.code} {suite_result.message}")
        return 2

    summary = suite_result.summary
    print(
        "TEST SUMMARY "
        f"total={summary.total} pass={summary.pass_count} diff={summary.diff_count} error={summary.error_count}"
    )

    exit_code = 0
    for case in suite_result.cases:
        if case.status == "PASS":
            continue
        if case.status == "ERROR":
            exit_code = 2
            err_text = case.errors[0] if case.errors else ""
            if err_text:
                print(f"CASE {case.case_id} ERROR {err_text}")
            else:
                print(f"CASE {case.case_id} ERROR")
            continue
        if case.status == "DIFF":
            if exit_code != 2:
                exit_code = 1
            print(f"CASE {case.case_id} DIFF")

    return exit_code


def _handle_test_update(args: argparse.Namespace) -> int:
    from sentinel.core.errors import SentinelError
    from sentinel.testkit.update_runner import run_update

    update_result = run_update(args.suite)

    if isinstance(update_result, SentinelError):
        print("TEST UPDATE ERROR")
        print(f"{update_result.category} {update_result.code} {update_result.message}")
        return 2

    summary = update_result.summary
    print(
        "TEST UPDATE SUMMARY "
        f"total={summary.total} updated={summary.updated} errors={summary.errors}"
    )

    has_error = False
    for case in update_result.cases:
        if case.status != "ERROR":
            continue
        has_error = True
        err_text = case.errors[0] if case.errors else ""
        if err_text:
            print(f"CASE {case.case_id} ERROR {err_text}")
        else:
            print(f"CASE {case.case_id} ERROR")

    return 2 if has_error else 0


def _handle_guard_check(args: argparse.Namespace) -> int:
    try:
        with open(args.input, encoding="utf-8") as input_file:
            input_json = json.load(input_file)
        with open(args.assertions, encoding="utf-8") as assertions_file:
            assertions_data = yaml.safe_load(assertions_file)
        assertions = assertions_data["assertions"]
    except Exception:
        _print_guard_summary({"total": 0, "pass": 0, "fail": 0, "error": 1})
        print("INTERNAL_ERROR SENTINEL_FILE_ERROR Failed to load input or assertions.")
        return 2

    result = evaluate_assertions(input_json, assertions)

    if result.status == "PASS":
        _print_guard_summary(result.summary)
        return 0

    if result.status == "FAIL":
        _print_guard_summary(result.summary)
        for assertion in result.assertions:
            if assertion.status != "FAIL":
                continue
            print(
                f"ASSERT {assertion.id} FAIL {assertion.type} {assertion.path} "
                f"expected={repr(assertion.expected)} actual={repr(assertion.actual)}"
            )
        return 1

    _print_guard_summary({"total": 0, "pass": 0, "fail": 0, "error": 1})
    print("INTERNAL_ERROR SENTINEL_ASSERTION_ERROR Guard evaluation failed.")
    return 2


def _handle_drift_baseline(args: argparse.Namespace) -> int:
    from sentinel.drift.output import render_drift_baseline
    from sentinel.drift.runner import run_drift_baseline

    result = run_drift_baseline(
        suite_path=args.suite,
        metrics_config_path=args.metrics,
        baseline_path=args.output,
    )
    if isinstance(result, SentinelError):
        return _fail("DRIFT BASELINE", result)

    for line in render_drift_baseline(result):
        print(line)
    return 0


def _handle_drift_check(args: argparse.Namespace) -> int:
    from sentinel.drift.output import render_drift_check
    from sentinel.drift.runner import run_drift_check

    result = run_drift_check(
        suite_path=args.suite,
        metrics_config_path=args.metrics,
        thresholds_config_path=args.thresholds,
        baseline_path=args.baseline,
    )
    if isinstance(result, SentinelError):
        return _fail("DRIFT CHECK", result)

    for line in render_drift_check(result):
        print(line)
    if result.status == "PASS":
        return 0
    if result.status == "FAIL":
        return 1
    return 2


def _handle_monitor_record(args: argparse.Namespace) -> int:
    mapped = map_source_artifact_to_event(source_path=args.source, event_type=args.event_type)
    if isinstance(mapped, SentinelError):
        return _fail("MONITOR RECORD", mapped)

    validation_err = validate_event(mapped)
    if validation_err is not None:
        return _fail("MONITOR RECORD", validation_err)

    append_err = append_event(args.event_file, mapped)
    if append_err is not None:
        return _fail("MONITOR RECORD", append_err)

    return 0


def _build_inspect_filters(args: argparse.Namespace) -> InspectFilters:
    return InspectFilters(
        from_timestamp_utc=args.from_timestamp_utc,
        to_timestamp_utc=args.to_timestamp_utc,
        last=args.last,
        command=args.filter_command,
        provider=args.provider,
        model=args.model,
        event_type=args.inspect_event_type,
        case_id=args.case_id,
        status=args.status,
    )


def _handle_monitor_inspect(args: argparse.Namespace) -> int:
    loaded = read_events(args.event_file)
    if isinstance(loaded, SentinelError):
        return _fail("MONITOR INSPECT", loaded)

    selected = select_events(loaded, _build_inspect_filters(args))
    if isinstance(selected, SentinelError):
        return _fail("MONITOR INSPECT", selected)

    for line in render_inspect_events(selected):
        print(line)
    return 0


def _handle_monitor_summary(args: argparse.Namespace) -> int:
    loaded = read_events(args.event_file)
    if isinstance(loaded, SentinelError):
        return _fail("MONITOR SUMMARY", loaded)

    selected = select_events(loaded, _build_inspect_filters(args))
    if isinstance(selected, SentinelError):
        return _fail("MONITOR SUMMARY", selected)

    definitions = load_signal_definitions(args.signals)
    if isinstance(definitions, SentinelError):
        return _fail("MONITOR SUMMARY", definitions)

    results = compute_signals(selected, definitions)
    if isinstance(results, SentinelError):
        return _fail("MONITOR SUMMARY", results)

    for line in render_summary(len(selected), results):
        print(line)
    return 0


def _handle_monitor_check(args: argparse.Namespace) -> int:
    loaded = read_events(args.event_file)
    if isinstance(loaded, SentinelError):
        return _fail("MONITOR CHECK", loaded)

    selected = select_events(loaded, _build_inspect_filters(args))
    if isinstance(selected, SentinelError):
        return _fail("MONITOR CHECK", selected)

    signal_defs = load_signal_definitions(args.signals)
    if isinstance(signal_defs, SentinelError):
        return _fail("MONITOR CHECK", signal_defs)

    signal_results = compute_signals(selected, signal_defs)
    if isinstance(signal_results, SentinelError):
        return _fail("MONITOR CHECK", signal_results)

    rule_defs = load_rule_definitions(args.rules)
    if isinstance(rule_defs, SentinelError):
        return _fail("MONITOR CHECK", rule_defs)

    evaluated = evaluate_rules(selected, signal_defs, signal_results, rule_defs)
    if isinstance(evaluated, SentinelError):
        return _fail("MONITOR CHECK", evaluated)

    for line in render_check(evaluated):
        print(line)
    if evaluated.summary["error"] > 0:
        return 2
    if evaluated.summary["fail"] > 0:
        return 1
    return 0


def _build_audit_filters(args: argparse.Namespace) -> AuditSelectionFilters:
    return AuditSelectionFilters(
        from_ts=args.from_timestamp_utc,
        to_ts=args.to_timestamp_utc,
        command=getattr(args, "filter_command", None),
        provider=getattr(args, "provider", None),
        model=getattr(args, "model", None),
        event_type=getattr(args, "inspect_event_type", None),
        case_id=getattr(args, "case_id", None),
        status=getattr(args, "status", None),
        audit_id=getattr(args, "audit_id", None),
        last=getattr(args, "last", None),
    )


def _handle_audit_record(args: argparse.Namespace) -> tuple[int, list[str]]:
    return run_audit_record(
        audit_file=args.audit_file,
        source=args.source,
        events=args.events,
    )


def _handle_audit_inspect(args: argparse.Namespace) -> tuple[int, list[str]]:
    return run_audit_inspect(args.audit_file, _build_audit_filters(args))

def _handle_audit_verify(args: argparse.Namespace) -> tuple[int, list[str]]:
    return run_audit_verify(args.audit_file, _build_audit_filters(args))


def _handle_audit_replay(args: argparse.Namespace) -> tuple[int, list[str]]:
    return run_audit_replay(args.audit_file, args.audit_id)


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_SIMPLE_DISPATCH: dict[tuple[str, ...], object] = {
    ("run",): _handle_run,
    ("validate",): _handle_validate,
    ("test", "run"): _handle_test_run,
    ("test", "update"): _handle_test_update,
    ("guard", "check"): _handle_guard_check,
    ("drift", "baseline"): _handle_drift_baseline,
    ("drift", "check"): _handle_drift_check,
    ("monitor", "record"): _handle_monitor_record,
    ("monitor", "inspect"): _handle_monitor_inspect,
    ("monitor", "summary"): _handle_monitor_summary,
    ("monitor", "check"): _handle_monitor_check,
}

_AUDIT_DISPATCH: dict[str, object] = {
    "record": _handle_audit_record,
    "inspect": _handle_audit_inspect,
    "verify": _handle_audit_verify,
    "replay": _handle_audit_replay,
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Run the Sentinel CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    cmd = args.command

    if cmd == "audit":
        audit_cmd = args.audit_command
        handler = _AUDIT_DISPATCH.get(audit_cmd)
        if handler is not None:
            code, lines = handler(args)  # type: ignore[call-arg]
            for line in lines:
                print(line)
            return code
    else:
        sub = getattr(args, f"{cmd}_command", None) if cmd else None
        key = (cmd, sub) if sub is not None else (cmd,)
        handler = _SIMPLE_DISPATCH.get(key)  # type: ignore[assignment]
        if handler is not None:
            return handler(args)  # type: ignore[call-arg]

    # No subcommand given – print help and exit 0.
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
