"""Incremental commit mechanism, packaged for reuse.

This is the core finding from "The Multi-File Wall" paper:
LLM code repair fails at 2+ files because the edit-test-revert loop
reverts ALL changes on ANY failure. Incremental commit fixes this by
preserving partial progress.

The mechanism:
  1. Run tests, count passing
  2. Ask LLM to fix a file
  3. Write the fix
  4. Run tests again
  5. If more pass: COMMIT (git checkpoint)
  6. If fewer/same: ROLLBACK (git reset to last checkpoint)
  7. If ALL pass: DONE
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Sequence


class LatticeCommitSafetyError(RuntimeError):
    """Raised when lattice-commit refuses to touch an unsafe workspace."""


@dataclass
class IncrementalResult:
    """Result of an incremental repair run."""
    solved: bool
    cycles: int
    commits: int
    files_modified: list[str] = field(default_factory=list)
    run_log: str | None = None

    def __str__(self):
        if self.solved:
            return f"SOLVED in {self.cycles} cycles ({self.commits} commits, files: {self.files_modified})"
        return f"UNSOLVED after {self.cycles} cycles ({self.commits} commits)"


TestCommand = str | Sequence[str]


def _normalize_test_cmd(test_cmd: TestCommand) -> list[str]:
    """Accept either a shell-like string or an argv sequence."""
    if isinstance(test_cmd, str):
        cmd = shlex.split(test_cmd, posix=(os.name != "nt"))
    else:
        cmd = list(test_cmd)
    if not cmd:
        raise ValueError("test_cmd must not be empty")
    return cmd


def count_passing(
    workspace: str,
    test_cmd: TestCommand,
    timeout: int = 60,
) -> tuple[int, bool, str]:
    """Run the test command and parse the number of passing tests.

    Returns (n_passing, all_passed, output_text).
    """
    cmd = _normalize_test_cmd(test_cmd)
    try:
        r = subprocess.run(
            cmd,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = (r.stdout or "") + (r.stderr or "")
        m = re.search(r"(\d+)\s+passed", output)
        n = int(m.group(1)) if m else 0
        return n, r.returncode == 0, output
    except subprocess.TimeoutExpired:
        return 0, False, "TIMEOUT"
    except Exception as e:
        return 0, False, str(e)


def _run_git(workspace: Path, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command in workspace."""
    result = subprocess.run(
        ["git", *args],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if check and result.returncode != 0:
        msg = (result.stderr or result.stdout or "").strip()
        raise LatticeCommitSafetyError(f"git {' '.join(args)} failed: {msg}")
    return result


def _ensure_clean_git_workspace(workspace: Path, allow_dirty: bool) -> None:
    """Require a clean git root unless the caller explicitly opts out."""
    if not workspace.exists():
        raise LatticeCommitSafetyError(f"workspace does not exist: {workspace}")
    if not workspace.is_dir():
        raise LatticeCommitSafetyError(f"workspace must be a directory: {workspace}")

    root_result = _run_git(workspace, ["rev-parse", "--show-toplevel"], check=False)
    if root_result.returncode != 0:
        raise LatticeCommitSafetyError(
            f"{workspace} is not inside a git repository. "
            "Open PowerShell in your project folder first, or pass "
            "--workspace C:\\path\\to\\repo. To verify the install without a repo, "
            "run this command with --self-test"
        )

    root = root_result.stdout.strip()
    if Path(root).resolve() != workspace:
        raise LatticeCommitSafetyError(
            f"workspace must be the git repository root for this alpha release; "
            f"got {workspace}, repo root is {Path(root).resolve()}"
        )

    status = _run_git(workspace, ["status", "--porcelain"]).stdout.strip()
    if status and not allow_dirty:
        raise LatticeCommitSafetyError(
            "workspace has uncommitted or untracked changes; commit/stash them first "
            "or pass allow_dirty=True"
        )


def _make_run_log(workspace: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    run_dir = workspace / ".git" / "lattice-commit" / "runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir / f"{stamp}.jsonl"


def _write_event(run_log: Path | None, event: str, **fields) -> None:
    if run_log is None:
        return
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    with run_log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, sort_keys=True) + "\n")


def _git_checkpoint(workspace: Path, message: str) -> bool:
    return _git_checkpoint_paths(workspace, message, paths=None)


def _git_checkpoint_paths(workspace: Path, message: str, paths: list[str] | None) -> bool:
    """Commit either all changes or a constrained set of repo-relative paths."""
    if paths is None:
        _run_git(workspace, ["add", "-A"])
    else:
        if not paths:
            return False
        _run_git(workspace, ["add", "--", *paths])
    diff = _run_git(workspace, ["diff", "--cached", "--quiet"], check=False)
    if diff.returncode == 0:
        return False
    _run_git(workspace, [
        "-c", "user.name=Lattice Commit",
        "-c", "user.email=lattice-commit@example.invalid",
        "commit", "--no-verify", "-m", message,
    ])
    return True


def _git_clean_untracked(workspace: Path) -> None:
    """Remove untracked files created during a run, respecting .gitignore."""
    _run_git(workspace, ["clean", "-fd"])


def _git_rollback(workspace: Path) -> None:
    """Rollback tracked changes and untracked artifacts to the last checkpoint."""
    _run_git(workspace, ["reset", "--hard", "HEAD"])
    _git_clean_untracked(workspace)


def _restore_clean_checkpoint(workspace: Path) -> None:
    """Leave the worktree clean at HEAD after tests or a checkpoint."""
    _git_rollback(workspace)


def count_passing_majority(
    workspace: str,
    test_cmd: TestCommand,
    n_votes: int = 3,
    timeout: int = 60,
) -> tuple[int, bool, str]:
    """Run tests n_votes times, return median count. Handles flaky tests."""
    import statistics
    cmd = _normalize_test_cmd(test_cmd)
    counts = []
    passes = []
    outputs = []
    for _ in range(n_votes):
        n, passed, output = count_passing(workspace, cmd, timeout=timeout)
        counts.append(n)
        passes.append(passed)
        outputs.append(output)
    median = int(statistics.median(counts))
    best_idx = min(range(len(counts)), key=lambda i: abs(counts[i] - median))
    # Only report all_pass if majority of runs passed
    all_pass = sum(passes) > n_votes // 2
    return median, all_pass, outputs[best_idx]


def incremental_repair(
    workspace: str,
    llm_fix: Callable[[Path, str, str], Optional[str]],
    test_cmd: TestCommand = ("python", "-m", "pytest", "-q"),
    max_cycles: int = 30,
    file_pattern: str = "*.py",
    exclude_patterns: tuple[str, ...] = ("test_*", "*_test.py", "__pycache__"),
    majority_vote: int = 1,
    allow_dirty: bool = False,
    test_timeout: int = 60,
) -> IncrementalResult:
    """Run incremental LLM code repair on a workspace.

    Args:
        workspace: Path to the project directory.
        llm_fix: Function that takes (file_path, file_content, test_error_output)
                 and returns the fixed file content, or None to skip.
        test_cmd: Command to run tests (must return 0 on all-pass).
        max_cycles: Maximum repair attempts.
        file_pattern: Glob pattern for files the LLM can edit.
        exclude_patterns: Glob patterns for files to exclude from editing.
        majority_vote: Number of test runs per cycle (use 3+ for flaky tests).
        allow_dirty: Allow starting from a dirty git tree. Safer default is False.
        test_timeout: Seconds before a single test command run times out.

    Returns:
        IncrementalResult with solved status, cycle count, and commit count.
    """
    ws = Path(workspace).resolve()
    cmd = _normalize_test_cmd(test_cmd)
    _ensure_clean_git_workspace(ws, allow_dirty=allow_dirty)
    run_log = _make_run_log(ws)
    _write_event(
        run_log,
        "start",
        workspace=str(ws),
        test_cmd=cmd,
        max_cycles=max_cycles,
        file_pattern=file_pattern,
        majority_vote=majority_vote,
        test_timeout=test_timeout,
    )

    if allow_dirty:
        _git_checkpoint(ws, "lattice-commit: initial dirty workspace checkpoint")
        _restore_clean_checkpoint(ws)

    _count_fn = (lambda: count_passing_majority(str(ws), cmd, majority_vote, timeout=test_timeout)) \
        if majority_vote > 1 else (lambda: count_passing(str(ws), cmd, timeout=test_timeout))
    best_passing, already_passing, _ = _count_fn()
    _restore_clean_checkpoint(ws)
    _write_event(run_log, "initial_test", passing=best_passing, all_pass=already_passing)
    if already_passing:
        return IncrementalResult(solved=True, cycles=0, commits=0, run_log=str(run_log))

    commits = 0
    files_modified = set()

    for cycle in range(1, max_cycles + 1):
        # Get current error output
        _, _, error_output = count_passing(str(ws), cmd, timeout=test_timeout)
        _restore_clean_checkpoint(ws)

        # Find editable files
        editable = []
        for p in sorted(ws.rglob(file_pattern)):
            rel = str(p.relative_to(ws))
            if any(p.match(pat) for pat in exclude_patterns):
                continue
            if "__pycache__" in rel or "/tests/" in rel or "\\tests\\" in rel:
                continue
            if ".git" in p.parts:
                continue
            editable.append(p)

        if not editable:
            _write_event(run_log, "stop_no_editable_files", cycle=cycle)
            break

        # Target the file hinted by the error output (if any)
        target_file = None
        for m in re.finditer(r"([\w./\\-]+\.\w+)", error_output):
            hint = Path(m.group(1)).name
            # Skip test files
            if "test_" in hint or hint.startswith("test"):
                continue
            matches = [f for f in editable if f.name == hint]
            if matches:
                target_file = matches[0]
                break

        if target_file is None:
            target_file = editable[0]

        fp = target_file
        rel_fp = str(fp.relative_to(ws))
        content = fp.read_text(encoding="utf-8")
        new_content = llm_fix(fp, content, error_output)

        if not new_content or new_content == content:
            _restore_clean_checkpoint(ws)
            _write_event(run_log, "skip_no_change", cycle=cycle, file=rel_fp)
            continue

        fp.write_text(new_content, encoding="utf-8")

        # Test (with majority vote if configured)
        current, all_pass, _ = _count_fn()
        _git_clean_untracked(ws)
        _write_event(
            run_log,
            "cycle_test",
            cycle=cycle,
            file=rel_fp,
            passing=current,
            best_passing=best_passing,
            all_pass=all_pass,
        )

        if all_pass:
            files_modified.add(rel_fp)
            committed = _git_checkpoint_paths(
                ws, f"lattice-commit: solve at cycle {cycle}", paths=[rel_fp])
            if committed:
                commits += 1
            _restore_clean_checkpoint(ws)
            _write_event(run_log, "solved", cycle=cycle, commits=commits)
            return IncrementalResult(
                solved=True, cycles=cycle, commits=commits,
                files_modified=sorted(files_modified), run_log=str(run_log))

        if current > best_passing:
            # COMMIT - more tests pass
            committed = _git_checkpoint_paths(
                ws, f"lattice-commit: checkpoint cycle {cycle}", paths=[rel_fp])
            if committed:
                commits += 1
            _restore_clean_checkpoint(ws)
            best_passing = current
            files_modified.add(rel_fp)
            _write_event(run_log, "checkpoint", cycle=cycle, commits=commits)
        else:
            # ROLLBACK - no improvement
            _git_rollback(ws)
            _write_event(run_log, "rollback", cycle=cycle, file=rel_fp)

    _write_event(run_log, "unsolved", cycles=max_cycles, commits=commits)
    return IncrementalResult(
        solved=False, cycles=max_cycles, commits=commits,
        files_modified=sorted(files_modified), run_log=str(run_log))
