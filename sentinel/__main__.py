"""Allow running the package with `python -m sentinel`."""

from sentinel.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
