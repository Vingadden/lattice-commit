"""Smoke tests for the lattice-commit package.

Intentionally minimal: they verify the public API imports and the CLI is
invokable. The mechanism's behavioral evidence — the 986-trial multi-file-wall
study — is documented in PAPER.md.
"""


def test_lattice_commit_importable():
    from lattice_commit import incremental_repair
    assert callable(incremental_repair)


def test_lattice_commit_has_result_dataclass():
    from lattice_commit import IncrementalResult
    r = IncrementalResult(solved=True, cycles=5, commits=3)
    assert r.solved is True
    assert r.cycles == 5


def test_cli_module_help_works():
    """The CLI is invokable via `python -m lattice_commit`. (The console
    script `lattice-commit` may or may not be on PATH depending on the
    install — `python -m` always works.)"""
    import subprocess
    import sys
    result = subprocess.run(
        [sys.executable, "-m", "lattice_commit", "--help"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    out = (result.stdout + result.stderr).lower()
    assert "workspace" in out or "test-cmd" in out or "test_cmd" in out
