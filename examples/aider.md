# Using Lattice Commit with Aider

Aider is close to the same family of workflows because it already uses git.
The distinction is that Lattice Commit commits only when the test signal
improves.

## Setup

```bash
pip install lattice-commit aider-chat
```

## Sequential Pattern

Use Aider normally. If a repair session gets stuck, commit or stash anything you
want to keep, then run Lattice Commit from a clean tree:

```bash
aider --model gpt-4o --auto-commits
lattice-commit --workspace . --test-cmd "python -m pytest -q" --max-cycles 20
```

## Callback Pattern

Use Aider as the proposer inside the Python API:

```python
import subprocess
from lattice_commit import incremental_repair

def aider_fix(filepath, content, error):
    subprocess.run(
        ["aider", "--no-auto-commits", "--message", f"Fix this error: {error}", str(filepath)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return filepath.read_text(encoding="utf-8")

result = incremental_repair(
    workspace=".",
    test_cmd=["python", "-m", "pytest", "-q"],
    llm_fix=aider_fix,
    max_cycles=15,
)
print(result)
print(result.run_log)
```

## When To Skip It

- You already have Aider configured with a strong test workflow.
- The repair is clearly single-file.
- Your test command is too slow to run every cycle.
