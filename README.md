# Lattice Commit

**A git-native checkpoint layer for test-gated AI code repair.**

Lattice Commit wraps an LLM repair loop with a simple rule: commit only when the
test signal improves, and reset when it does not. The goal is to preserve partial
progress across multi-file fixes instead of throwing away a good change because
another bug still fails.

This repository is the project home for the published package: the research
extract, examples, tests, and the distribution layer. The package itself is on
PyPI: `pip install lattice-commit`.

## Status

- Open-source package: alpha — `lattice-commit 0.1.0` on PyPI, 0.1.1 staged here
- Core behavior: git commits for improvements, `git reset --hard HEAD` for regressions
- Safety default: refuses to run unless the workspace is a clean git repository root
- Audit trail: JSONL run logs under `.git/lattice-commit/runs/`
- Evidence: synthetic multi-file repair benchmark, 986+ trials
- Next evidence target: real-repo validation and reproducible benchmark bundle

## The failure mode

The motivating benchmark studied a one-file-at-a-time edit/test/revert loop. In
that setup, the bare loop solved one-file bug sets but failed when fixes had to
accumulate across multiple files: a failed later test run reverted earlier useful
work. Lattice Commit changes the state boundary from "all-or-nothing per cycle"
to "keep monotone test improvements."

| Scenario | Bare loop | Lattice Commit |
|---|---:|---:|
| Bugs isolated in one file | Solved in benchmark | Solved in benchmark |
| Fixes required across 2+ files | Failed in benchmark | Solved in benchmark |

The current claim is deliberately scoped: this demonstrates a structural failure
mode in the tested loop. It is not yet a universal claim about every coding
agent, repository, model, or test runner.

## Install

```bash
pip install lattice-commit
```

## Use it

### Python library

```python
from lattice_commit import incremental_repair

result = incremental_repair(
    workspace="./my_project",
    test_cmd=["python", "-m", "pytest", "-q"],
    llm_fix=my_fix_function,
    max_cycles=30,
)

print(result)
print(result.run_log)
```

The callback signature is:

```python
def my_fix_function(filepath, content, error_output):
    return complete_replacement_content_or_none
```

### CLI with Ollama

```bash
lattice-commit --workspace ./my_project --test-cmd "python -m pytest -q"
lattice-commit --workspace ./my_project --test-cmd "python -m pytest -q" --majority-vote 3
```

The CLI uses a local Ollama model by default. It expects a clean git repo and
prints the run-log path after completion.

## Safety model

Lattice Commit now uses real git operations:

- It verifies `workspace` is the repo root.
- It refuses dirty or untracked files unless `--allow-dirty` / `allow_dirty=True`
  is passed.
- It creates commits with messages like `lattice-commit: checkpoint cycle 3`.
- It stages only the selected repair file for each checkpoint.
- It rolls back non-improving edits with `git reset --hard HEAD` plus
  `git clean -fd`.
- It records lifecycle events in `.git/lattice-commit/runs/*.jsonl`.

Run it on a branch or throwaway clone until the behavior has been validated on
your project.

## Research

The public research extract is in [PAPER.md](PAPER.md). It describes the
synthetic multi-file wall result and the boundary-mechanism framing. Claims in
this repo should stay inside the evidence boundary:

- OK: "986+ synthetic trials"
- OK: "tested on llama3.1:8b, qwen2.5-coder:7b, and qwen2.5-coder:14b"
- OK: "commit-on-improvement fixed the tested one-file-proposal loop"
- Avoid: "works with any LLM and any test suite"
- Avoid: "all major coding agents silently throw away good fixes"
- Avoid: "production SaaS features are already shipped"

## Development priorities

1. Publish a reproducible benchmark bundle.
2. Validate the mechanism on real repositories with known multi-file bugs.
3. Improve test-result parsing beyond pytest-style output.
4. Add a dry-run/report mode before editing files.
5. Ship one honest integration recipe that has been exercised end to end.

## Files

- [PAPER.md](PAPER.md) - public research extract
- [CHANGELOG.md](CHANGELOG.md) - release notes
- [examples/](examples/) - integration sketches and examples
- [site/](site/) - static project page

## License

MIT
