# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Public packaging: installable from the repository root with `pip install .`
  (or editable `pip install -e .` for local development).
- OSS baseline documentation: README, LICENSE (MIT), CONTRIBUTING, and this changelog.

### Changed

- `sentinel audit inspect` and `sentinel audit verify` now validate filter
  arguments before executing. Invalid ISO-8601 UTC timestamps in `--from` or
  `--to`, a `--from` value later than `--to`, or a `--last` value less than 1
  exit 2 with a structured `SENTINEL_AUDIT_INVALID_FILTER` error message.
  Previously these filters ran silently and could return empty or incorrect
  subsets. Behavior now matches `sentinel monitor inspect`.

### Scope (high level)

Sentinel provides a **CLI-first**, **deterministic**, **CI-oriented** toolkit for
structured LLM workflows, covering:

- **Contract** — Contract runs with schema-validated JSON and explicit outcomes.
- **Regression** — YAML test suites and snapshot-style regression checks.
- **Guard** — Guardrail assertions over JSON payloads.
- **Drift** — Drift detection from suite metrics and baselines.
- **Monitor** — Runtime event recording, signals, and rule checks.
- **Audit** — Append-only audit records, verification, and replay-oriented workflows.

Details and command shapes are in the README and CLI help.
