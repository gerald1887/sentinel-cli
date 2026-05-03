# Sentinel CLI

**Sentinel** is a command-line toolkit for making **structured LLM workflows**
testable and **CI-friendly**: explicit outcomes, deterministic checks, and
clear exit codes—without dashboards or hosted infrastructure.

## What it does

Sentinel runs **locally** and helps you:

- Run prompts against a provider, enforce **JSON** output, and validate against a **JSON Schema** (Contract).
- Drive **YAML-based** regression suites and snapshot-style comparisons (Regression).
- Apply **guardrail assertions** (JSON Pointer paths, typed checks) to JSON inputs (Guard).
- Record **metrics** from suites, compare to **baselines**, and surface drift (Drift).
- **Record** runtime events, derive **signals**, and evaluate **rules** (Monitor).
- Maintain an **append-only audit trail** (JSONL), with **verify** and **replay**-oriented workflows (Audit).

Positioning: **deterministic checks first**, suitable for pipelines and review gates—not a replacement for your own product guarantees or legal compliance programs.

## Install (from this repository)

Clone the repo, then from the **repository root**:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install .
```

For local development (editable install and dev dependencies):

```bash
pip install -r requirements-dev.txt
pip install -e .
```

## CLI

Show commands and options:

```bash
sentinel --help
```

Print the installed version:

```bash
sentinel --version
```

## Minimal example (no API keys)

Guard check runs entirely on local files:

```bash
printf '%s\n' '{"score":0.9}' > /tmp/sentinel-example.json
printf '%s\n' "version: '1'" > /tmp/sentinel-example.yaml
printf '%s\n' "assertions:" >> /tmp/sentinel-example.yaml
printf '%s\n' "  - id: has_score" >> /tmp/sentinel-example.yaml
printf '%s\n' "    type: exists" >> /tmp/sentinel-example.yaml
printf '%s\n' "    path: /score" >> /tmp/sentinel-example.yaml

sentinel guard check \
  --input /tmp/sentinel-example.json \
  --assertions /tmp/sentinel-example.yaml
```

Contract runs (`sentinel run`) and other subcommands need provider configuration
and credentials as documented in `sentinel --help` and the capability sections below.

## Capabilities by area

| Area | Focus |
|-------|--------|
| Contract | Contract run, strict JSON, schema validation, PASS / FAIL / ERROR |
| Regression | Suite runs, snapshots, structural diff, PASS / DIFF / ERROR |
| Guard | Guard assertions, deterministic pass/fail |
| Drift | Baselines, metrics, thresholds, drift check |
| Monitor | Event record, signal + rule check, summary |
| Audit | Audit record (JSONL), inspect, verify, replay |

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

## Who it is for

Backend engineers who want **repeatable** checks around LLM outputs in **tests**
and **automation**—not a managed SaaS layer on top of this repo.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

MIT — see [LICENSE](LICENSE).
