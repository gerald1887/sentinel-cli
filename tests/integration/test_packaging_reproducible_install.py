"""external integration reproducible install deterministic command check."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _venv_python(venv_dir: Path) -> Path:
    return venv_dir / "bin" / "python"


def test_packaging_reproducible_install(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    venv_dir = tmp_path / "venv"

    create_proc = subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        cwd=str(repo_root),
        check=False,
        capture_output=True,
        text=True,
    )
    assert create_proc.returncode == 0, create_proc.stdout + create_proc.stderr

    vpy = _venv_python(venv_dir)
    install_proc = subprocess.run(
        [str(vpy), "-m", "pip", "install", "."],
        cwd=str(repo_root),
        check=False,
        capture_output=True,
        text=True,
    )
    assert install_proc.returncode == 0, install_proc.stdout + install_proc.stderr

    input_path = tmp_path / "input.json"
    schema_path = tmp_path / "schema.json"
    input_path.write_text('{"ok": true}\n', encoding="utf-8")
    schema_path.write_text('{"type":"object","required":["ok"],"properties":{"ok":{"type":"boolean"}}}\n', encoding="utf-8")

    validate_proc = subprocess.run(
        [
            str(venv_dir / "bin" / "sentinel"),
            "validate",
            "--input",
            str(input_path),
            "--schema",
            str(schema_path),
        ],
        cwd=str(tmp_path),
        check=False,
        capture_output=True,
        text=True,
    )
    assert validate_proc.returncode == 0, validate_proc.stdout + validate_proc.stderr
    assert "PASS: Contract satisfied" in validate_proc.stdout
