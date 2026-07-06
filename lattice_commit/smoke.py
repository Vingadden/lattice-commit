"""Built-in local smoke test for lattice-commit."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from .core import IncrementalResult, incremental_repair


def _run(cmd: list[str], cwd: Path) -> str:
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return result.stdout.strip()


def _init_repo(workspace: Path) -> None:
    _run(["git", "init"], cwd=workspace)
    _run(["git", "config", "user.email", "smoke@example.invalid"], cwd=workspace)
    _run(["git", "config", "user.name", "Lattice Smoke"], cwd=workspace)
    _run(["git", "add", "-A"], cwd=workspace)
    _run(["git", "commit", "-m", "initial failing project"], cwd=workspace)


def run_self_test() -> tuple[Path, IncrementalResult, str]:
    """Repair a disposable failing repo without Ollama, pytest, or API keys."""
    workspace = Path(tempfile.mkdtemp(prefix="lattice-commit-self-test-"))
    (workspace / "app.py").write_text(
        "def add(a, b):\n"
        "    return a - b  # BUG\n",
        encoding="utf-8",
    )
    if os.name == "nt":
        (workspace / "check.cmd").write_text(
            "@echo off\n"
            "findstr /C:\"return a + b\" app.py >nul\n"
            "if errorlevel 1 (\n"
            "  echo FAILED app.py\n"
            "  exit /b 1\n"
            ")\n"
            "echo 2 passed\n",
            encoding="utf-8",
        )
        test_cmd = ["cmd", "/c", "check.cmd"]
    else:
        (workspace / "check.sh").write_text(
            "#!/bin/sh\n"
            "if grep -q 'return a + b' app.py; then\n"
            "  echo '2 passed'\n"
            "  exit 0\n"
            "fi\n"
            "echo 'FAILED app.py'\n"
            "exit 1\n",
            encoding="utf-8",
        )
        test_cmd = ["sh", "check.sh"]
    _init_repo(workspace)

    def deterministic_fix(filepath: Path, content: str, error_output: str) -> str | None:
        if filepath.name != "app.py":
            return None
        return content.replace("return a - b  # BUG", "return a + b")

    result = incremental_repair(
        workspace=str(workspace),
        llm_fix=deterministic_fix,
        test_cmd=test_cmd,
        max_cycles=3,
    )
    latest_commit = _run(["git", "log", "--oneline", "-1"], cwd=workspace)
    return workspace, result, latest_commit
