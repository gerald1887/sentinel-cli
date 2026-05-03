# Contract check fixtures

These fixtures support **contract** (`sentinel run`) and **validate** flows against an example structured data extraction schema.

- The bundled JSON Schema reflects a neutral **example structured data extraction schema** used for documentation and tests.
- Primary execution path documented below uses `sentinel run` with a provider (not file-only validation).

## Files

- `extraction_schema.json` — JSON Schema for structured output
- `prompt_valid.txt` — prompt that yields schema-valid JSON
- `prompt_invalid.txt` — prompt that omits required field `age`
- `regression_suite.yaml` — minimal suite definition for regression tests
- `artifact_valid.json`, `artifact_invalid.json`, `artifact_schema.json` — unified-artifact fixtures for `sentinel validate`

## Contract run (provider)

Run from repository root. PASS (exit `0`):

```bash
sentinel run \
  --prompt examples/fixtures/contract_check/prompt_valid.txt \
  --schema examples/fixtures/contract_check/extraction_schema.json \
  --provider openai \
  --model gpt-4.1
```

FAIL (exit `1`):

```bash
sentinel run \
  --prompt examples/fixtures/contract_check/prompt_invalid.txt \
  --schema examples/fixtures/contract_check/extraction_schema.json \
  --provider openai \
  --model gpt-4.1
```

## Validate unified artifacts

Valid artifact (exit `0`):

```bash
sentinel validate \
  --input examples/fixtures/contract_check/artifact_valid.json \
  --schema examples/fixtures/contract_check/artifact_schema.json
```

Invalid artifact (exit `1`):

```bash
sentinel validate \
  --input examples/fixtures/contract_check/artifact_invalid.json \
  --schema examples/fixtures/contract_check/artifact_schema.json
```

Expected markers: `PASS: Contract satisfied` / `FAIL: Contract violated` with `SCHEMA_VALIDATION_ERROR` on invalid input.
