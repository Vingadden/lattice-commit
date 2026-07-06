# Using Lattice Commit with Cursor

Cursor's native agent flow handles many multi-file edits well. Use Lattice
Commit only when you have a specific test-gated repair loop that keeps losing
partial progress.

## Setup

```bash
pip install lattice-commit
```

## Sidecar Pattern

Start from a clean git tree, then run:

```bash
cd /path/to/your/repo
lattice-commit --workspace . --test-cmd "python -m pytest -q" --max-cycles 10
```

The CLI starts an Ollama-backed repair loop. Improving changes are committed to
git, non-improving changes are reset, and the final output includes a run-log
path under `.git/lattice-commit/runs/`.

## Watching The Run

The alpha package does not ship a dashboard. Inspect the git history and JSONL
run log:

```bash
git log --oneline --decorate -n 10
type .git\lattice-commit\runs\<run-id>.jsonl
```

## When To Skip It

- Quick one-file edits.
- Frontend or writing work without a reliable test signal.
- Cursor sessions where the native workflow is already preserving good work.
