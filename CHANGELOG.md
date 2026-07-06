# Changelog

All notable changes to Lattice Commit will be documented here.

## [0.1.1] - 2026-05-08

Local development target after the critique round.

### Mechanism
- Switched the package from directory copy/restore to real git checkpoints.
- Refuse to run by default unless `workspace` is a clean git repository root.
- Added `allow_dirty` / `--allow-dirty` for explicit dirty-tree experiments.
- Commit successful or improving repairs with `lattice-commit: ...` messages.
- Roll back non-improving repairs with `git reset --hard HEAD`.
- Add JSONL run logs under `.git/lattice-commit/runs/`.
- Added safety-refusal tests and rollback-restoration coverage.

### Claim cleanup
- Narrowed README language from universal agent claims to a scoped synthetic
  multi-file repair result.
- Marked hosted dashboard and team features as future product work, not shipped
  capability.

## [0.1.0] - 2026-04-30

Initial public alpha package.

### Mechanism
- Incremental commit / rollback wrapper for test-gated LLM code repair.
- Python API (`incremental_repair`) and CLI (`lattice-commit`).
- Ollama-backed default proposer; pluggable callback API for custom fixers.

### Distribution layer
- Customer-facing README, pricing, GTM materials.
- Integration sketches for Cursor, Claude Code, and Aider.
- Public extract of the multi-file-wall research section.

### Known limitations
- Synthetic workspace evaluation only; real-repo validation remains open.
- Requires a test signal.
- Rollback-on-tie discards changes that do not add newly passing tests.
- Packaged MCP integrations are not shipped yet.
