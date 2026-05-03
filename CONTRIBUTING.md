# Contributing

Thank you for helping improve Sentinel.

## Expectations

- **Tests must pass.** Run `python -m pytest -q` from the repository root before
  opening a change.
- **Preserve deterministic behavior.** Sentinel is built for repeatable,
  CI-safe outcomes; avoid introducing nondeterminism or hidden side effects.
- **No behavior changes without tests.** If you change observable CLI or core
  behavior, add or update tests that lock the intended contract.
- **Stay in scope.** This project is a CLI and local tooling surface—not a
  hosted product. Do not add dashboards, SaaS, background services, or
  open-ended “platform” features as part of routine contributions.

## Development setup

From the repository root (with a virtual environment activated if you use one):

```bash
pip install -r requirements-dev.txt
pip install -e .
python -m pytest -q
```

## Questions

Prefer issues or small, focused pull requests with a clear description of what
changed and why.
