#!/usr/bin/env bash
set +e

echo "=== Sentinel Extraction Demo ==="
echo

echo "=== 1) VALIDATE PASS ==="
sentinel validate --input pass.json --schema schema.json
echo "[exit=$? expected=0]"
echo

echo "=== 2) VALIDATE FAIL: LLM omitted required field ==="
sentinel validate --input fail_schema.json --schema schema.json
echo "[exit=$? expected=1]"
echo

echo "=== 3) VALIDATE FAIL: LLM returned unsupported currency ==="
sentinel validate --input fail_currency.json --schema schema.json
echo "[exit=$? expected=1]"
echo
