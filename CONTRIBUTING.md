# Contributing to Lattice Commit

Thanks for considering a contribution. Honest expectations up front:

**This is a one-person project.** Bentley Moon reviews PRs personally. Response time is "within 1 week most weeks."

## In scope

- **Integration recipes** — new agents (Continue, Cline, Roo Code, Codeium, etc.) get integration docs in `examples/`
- **Test-runner adapters** — currently the regex `(\d+) passed` is pytest-shaped. Other runners (jest, mocha, go test, cargo test) need their own count parsers.
- **Multi-file proposer mode** — when the LLM is allowed to output fixes for multiple files in one response, the wall disappears. Adding native multi-file support to the wrapper.
- **Better convergence reporting** — visualizations of the cycle/commit/rollback timeline.
- **MCP server** — a packaged MCP server for Claude Code / Cursor.

## Out of scope (for now)

- **Replacing the commit/rollback mechanism with something more sophisticated.** That's the whole pitch — small, deterministic, auditable. PRs adding learned components or model-based decision logic will be closed unless they include statistical evidence that they outperform the bare mechanism on the same benchmark.
- **General-purpose code analysis** — Lattice Commit is a wrapper, not a static analyzer.
- **UI features beyond integration recipes** — the open-source repo focuses on the mechanism and CLI. A dashboard or GUI is out of scope for now.

## Process

1. Open an issue describing the change before writing code (especially for anything beyond a new integration recipe).
2. Fork, branch, push.
3. PR against `main` with what changed, why, how tested, whether tests added.
4. Run the test suite locally before submitting.
5. CI runs on push. If green and in scope, expect a review within ~1 week.

## Ground rules

- New integrations get a dedicated example in `examples/`.
- New test-runner adapters need at least one test case demonstrating the count parser works on real test output.
- Mechanism changes need empirical evidence (a benchmark run showing the change doesn't regress the F=2 wall result).
- Don't add dependencies that aren't already in the core `lattice-commit` package's `pyproject.toml` without a clear case.

## License

By contributing, you agree your contribution is licensed under MIT (the repo license).
