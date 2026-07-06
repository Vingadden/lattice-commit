# Using Lattice Commit with Claude Code

Claude Code's `Bash` tool can run any command, so the simplest integration is to invoke `lattice-commit` from inside a Claude Code session.

## Setup

```bash
pip install lattice-commit
```

## Manual invocation pattern

When Claude Code is debugging a multi-file issue, first make sure the repo is a
clean git tree. Then prompt it:

> Run `lattice-commit --workspace . --test-cmd "python -m pytest -q" --max-cycles 20` and tell me what it converged to, including the run-log path.

Claude Code will run the command, and Lattice Commit's Ollama-backed loop will
iterate on the bug. The result tells Claude Code what fixes landed, and Claude
Code can inspect the git commits and JSONL run log before continuing.

## Hands-off pattern (Slash command)

Add a custom Claude Code slash command at `.claude/commands/repair.md`:

```markdown
---
description: Run Lattice Commit incremental repair until tests pass
---

Run `lattice-commit --workspace . --test-cmd "python -m pytest -q" --max-cycles 20`. Report:
- Whether it solved the issue (look for "SOLVED" in output)
- How many cycles it took
- Which files were modified
- The final test count
- The run-log path

If unsolved, summarize what the loop tried and where it got stuck.
```

Then in any Claude Code session: `/repair`

## MCP server pattern (advanced)

A custom MCP server exposing `lattice_commit` as a tool is on the roadmap for v0.2. Until then, the slash-command pattern above is the cleanest hands-off integration.

If you want to build an MCP server now:

```python
# C:\my-mcp-server\server.py
from mcp.server.fastmcp import FastMCP
import subprocess

mcp = FastMCP("lattice-commit")

@mcp.tool()
def run_repair(workspace: str, test_cmd: str, max_cycles: int = 20) -> str:
    """Run incremental repair until tests pass or budget exhausted."""
    result = subprocess.run(
        ["lattice-commit", "--workspace", workspace, "--test-cmd", test_cmd, "--max-cycles", str(max_cycles)],
        capture_output=True, text=True, timeout=900,
    )
    return result.stdout + result.stderr

if __name__ == "__main__":
    mcp.run()
```

Then in Claude Code's settings, register the MCP server pointing at your script.

## When NOT to use it with Claude Code

- **Claude Code's native multi-file editing usually works.** Don't reach for Lattice Commit until you've seen the regression pattern in a real session.
- **Documentation / writing tasks.** No test signal, no wrapper benefit.
- **Greenfield code where there are no tests yet.** The wrapper helps fix bugs against a test suite; it doesn't help write code from scratch.
