"""external integration help output stability checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _venv_python(venv_dir: Path) -> Path:
    return venv_dir / "bin" / "python"


def test_help_output_stable(tmp_path: Path) -> None:
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

    help_proc = subprocess.run(
        [str(venv_dir / "bin" / "sentinel"), "--help"],
        cwd=str(tmp_path),
        check=False,
        capture_output=True,
        text=True,
    )
    assert help_proc.returncode == 0, help_proc.stdout + help_proc.stderr
    stdout = help_proc.stdout
    assert "sentinel" in stdout
    assert "run" in stdout
    assert "test" in stdout
    assert "guard" in stdout
    assert "drift" in stdout
    assert "monitor" in stdout
    assert "audit" in stdout
