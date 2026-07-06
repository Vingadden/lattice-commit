# Lattice Commit Examples

Integration sketches and recipes.

| File | What it shows |
|---|---|
| [cursor.md](cursor.md) | Sidecar usage with Cursor |
| [claude_code.md](claude_code.md) | Manual and slash-command usage with Claude Code |
| [aider.md](aider.md) | Sequential and callback patterns with Aider |
| [standalone.py](standalone.py) | Custom fixer callback via the Python API |

## Quick Decision Matrix

| Workflow | Best starting point | Why |
|---|---|---|
| Cursor session with a recurring multi-file regression | Sidecar | Keep Cursor as the main editor, use Lattice Commit only for test-gated repair |
| Claude Code session | Slash command | Simple command wrapper, no packaged MCP server required |
| Aider session | Sequential or callback | Use test improvement as the commit gate |
| Direct OpenAI/Anthropic/local model API | Standalone Python | Maximum control over the proposer callback |
| Other one-file repair loop | Standalone Python | Implement `llm_fix(filepath, content, error)` |

## Next Examples To Build

- Reproducible benchmark bundle.
- One fully exercised IDE or agent integration.
- Dry-run/report mode.
- Broader test-result parsers beyond pytest-style output.
