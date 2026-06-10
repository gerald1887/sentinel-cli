# Sentinel CLI

**Sentinel** is a CLI for making LLM systems deterministic, testable, and CI-safe.

LLM outputs are non-deterministic by default. Sentinel adds explicit **contracts**, **repeatable tests**, and **deterministic pass/fail signals** so you can gate merges and releases like any other service.

Think of Sentinel as tests and contracts for non-deterministic LLM outputs.

## What it does

- **Contract** — enforce JSON output with schema validation
- **Regression** — snapshot-based testing with diffs
- **Guard** — assertions on structured outputs
- **Drift** — baseline vs current metric checks
- **Monitor** — runtime signals and rule evaluation
- **Audit** — append-only logs with verify and replay

## Install

Requires Python 3.11+

### Recommended (pipx)

Clone the repository:

```bash
git clone https://github.com/gerald1887/sentinel-cli.git
cd sentinel-cli
```

Install with `pipx` (core, no provider):

```bash
sudo apt install pipx -y
pipx ensurepath
pipx install .
```

To include the OpenAI provider:

```bash
pipx install ".[openai]"
```

### Development install

From a clone of this repository:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

To develop with the OpenAI provider also available:

```bash
pip install -e ".[openai,dev]"
```

Ubuntu 24.04+ follows PEP 668 and blocks global `pip install`
into the system Python environment. Use `pipx` for global CLI
installation or a virtual environment for development.

## CLI

```bash
sentinel --help
sentinel --version
```

Commands: `run`, `validate`, `test`, `guard`, `drift`, `monitor`, `audit`.

## Minimal example (no API keys)

Guard check runs entirely on local files:

```bash
sentinel guard check \
  --input examples/minimal_guard/input.json \
  --assertions examples/minimal_guard/assertions.yaml
```

Expected (stdout includes):

```text
GUARD SUMMARY total=1 pass=1 fail=0 error=0
```

This runs entirely offline — no API keys required.

Contract runs (`sentinel run`) and other subcommands need provider configuration
and credentials as documented in `sentinel --help` and the sections below.

## Capabilities by area

### Contract — `sentinel run`

```bash
sentinel run \
  --prompt <prompt-file> \
  --schema <schema-file> \
  --provider <provider> \
  --model <model> \
  [--timeout <seconds>] \
  [--assertions <assertions-file>]
```

### Regression — `sentinel test`

```bash
sentinel test run --suite <suite-file>
sentinel test update --suite <suite-file>
```

### Guard — `sentinel guard`

```bash
sentinel guard check \
  --input <json-file> \
  --assertions <assertions-file>
```

### Drift — `sentinel drift`

```bash
sentinel drift baseline \
  --suite <suite-file> \
  --metrics <metrics-file> \
  --output <baseline-file>

sentinel drift check \
  --suite <suite-file> \
  --metrics <metrics-file> \
  --baseline <baseline-file> \
  --thresholds <thresholds-file>
```

Minimal `metrics.yaml` shape:

```yaml
metrics:
  - metric_id: m_numeric
    family: numeric
    path: /score
```

### Monitor — `sentinel monitor`

```bash
sentinel monitor record \
  --event-file <PATH> \
  --source <PATH> \
  --event-type <TYPE>

sentinel monitor check \
  --event-file <PATH> \
  --signals <PATH> \
  --rules <PATH>

sentinel monitor summary \
  --event-file <PATH> \
  --signals <PATH>

sentinel monitor inspect \
  --event-file <PATH>
```

### Audit — `sentinel audit`

```bash
sentinel audit record \
  --audit-file <audit.jsonl> \
  --source <result-file> \
  [--events <event-file>]

sentinel audit inspect \
  --audit-file <audit.jsonl> \
  [--from <ts>] [--to <ts>] [--last <n>] \
  [--command <cmd>] [--provider <p>] [--model <m>] \
  [--event-type <type>] [--case-id <id>] \
  [--status <status>] [--audit-id <id>]

sentinel audit verify \
  --audit-file <audit.jsonl>

sentinel audit replay \
  --audit-file <audit.jsonl> \
  --audit-id <id>
```

## Design principles

- CLI-first, deterministic checks, CI-friendly exit codes  
- Provider-agnostic core; minimal dependencies  
- Explicit failure modes  
- No bundled dashboards or hosted infrastructure  
- Designed to run in CI with deterministic exit codes  

## Who it is for

Backend engineers who want repeatable checks around LLM outputs.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

MIT — see [LICENSE](LICENSE).