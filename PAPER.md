# The Multi-File Wall in LLM Code Repair

**Bentley Moon**
April 2026

> This is a public-facing extract of §3 ("Finding 1: The Multi-File Wall") from a longer research synthesis on boundary mechanisms in AI systems. The full synthesis covers two additional findings — Governor Routing for LLM cost orchestration, and momentum protection for continual learning under metabolic energy constraint.

## Abstract

We study LLM-based code repair in an edit-test-revert loop. Across 22 purpose-built Python workspaces, 3 different LLMs, and 986+ pre-registered trials, we observe a structural failure mode: **bare LLM repair fails at F=2 files, regardless of bug count, bug complexity, model capability, or prompt engineering.** A 30-line incremental commit mechanism — commit on test improvement, rollback to last committed state — restores 100% solve rate through 8 bugs across 6 files.

The wall is **structural**, not capability-driven. It is caused by the one-file-per-proposal output interface: when the LLM proposes a fix to file A, tests are still failing because of file B, and the loop reverts everything — including the successful fix to A. Multi-file proposer ablation removes the wall entirely, confirming the diagnosis.

## 1. The Wall

| Configuration | Bugs | Buggy files | Bare LLM | With commit | p |
|---|:---:|:---:|:---:|:---:|:---:|
| 3 bugs, 1 file | 3 | 1 | **100%** (8/8) | 100% | — |
| 4 bugs, 1 file | 4 | 1 | **100%** (8/8) | 100% | — |
| 2 bugs, 2 files | 2 | 2 | **0%** (0/8) | 100% | <0.0001 |
| 4 bugs, 4 files | 4 | 4 | **0%** (0/10) | 100% | <0.0001 |
| 5 bugs, 3 files | 5 | 3 | **0%** (0/10) | 100% | <0.0001 |
| 8 bugs, 4 files | 8 | 4 | **0%** (0/10) | 100%* | <0.0001 |

*7/8 on the original scaling run; 10/10 on the isolation control.

The wall is at **F=2 files**, not at any number of bugs. **4 bugs in 1 file: 100% bare. 2 bugs in 2 files: 0% bare.**

## 2. The Mechanism

```python
best_passing = count_passing_tests()
for cycle in range(max_cycles):
    proposed_fix = llm.propose_fix(test_output)
    apply(proposed_fix)
    current_passing = count_passing_tests()
    if current_passing > best_passing:
        commit()              # protect this progress
        best_passing = current_passing
    else:
        rollback()            # to last committed state, NOT original
    if current_passing == total_tests:
        break
```

30 lines. No framework. No learned parameters. The mechanism is `git commit` triggered by test improvement.

## 3. Why The Wall Exists

Each LLM proposal modifies one file. If the proposal fixes file A but file B still has a bug, the test suite still fails, and the bare loop reverts everything — including the fix to A. With commit protection, the fix to A is committed and protected; subsequent cycles can work on B from a state where A is already fixed.

**Causal confirmation:** When the LLM outputs fixes for multiple files in one response (multi-file proposer), the same 2-bug/2-file workspace that scores 0/8 with single-file output scores **5/5 with multi-file output** — bare loop, no commit. The wall is the interface constraint, confirmed by ablation.

## 4. Invariances

The wall is:
- **Model-invariant:** Same step function for llama3.1:8b, qwen2.5-coder:7b, qwen2.5-coder:14b
- **Bug-complexity-invariant:** Algorithmic bugs (binary search off-by-one, Fibonacci wrong base case) show the same pattern as operator flips
- **Test-sparsity-robust:** 1 test per bug is sufficient for the mechanism to work
- **Temperature-invariant:** 0.0 through 1.0 produce identical results (7.6 cycles average)
- **Prompt-invariant:** Decomposition ("fix one bug at a time") is worse; history-in-prompt has no effect

## 5. Isolation Control

A 30-line wrapper implementing only the commit/rollback mechanism produces identical results (p=1.0, 40 trials) to a 2,100-line substrate system with typed transitions, containment validation, state caching, and proposal journals. **The value is in the commit pattern, not the infrastructure.**

This is the core finding for productization: the mechanism that breaks the wall is small enough to package as a library and deploy alongside any coding agent.

## 6. Scaling

Cycles-to-solve scales linearly with bug count: **cycles ≈ 0.72 × bugs + 2.2** (R² ≈ 0.85). At cloud pricing, an 8-bug multi-file fix costs $0.002 (GPT-4o-mini) to $0.05 (Claude Sonnet).

## 7. Relation to Existing Work

- **SWE-bench** (Jimenez et al., 2024): benchmark for LLM repair on real issues. This work explains *why* multi-file tasks are harder.
- **GenProg** (Le Goues et al., 2012): genetic programming for repair using test-suite fitness. Same fitness signal, with LLM proposals.
- **Agentless** (Xia et al., 2024): LLM repair without agents. The commit mechanism is complementary — it wraps any proposer.
- **TCR** (Beck, 2018): Test && Commit || Revert. This work shows TCR is **necessary** for LLM repair, not just convenient.

## 8. Limitations

1. **Synthetic workspaces.** Validated on planted bugs in small Python files. Real-world validation on SWE-bench is the next experiment.
2. **Test signal required.** The mechanism needs a test suite that grows monotonically with correctness. Won't help if bugs aren't covered by tests.
3. **Rollback-on-tie.** Current implementation rolls back when test count is equal. This may discard genuine improvements that don't add new passing tests (e.g., type fixes that don't change behavior). A configurable "tie = commit" mode is on the roadmap.

## 9. What This Doesn't Claim

- That this generalizes to non-test-driven domains. The mechanism specifically requires a measurable correctness signal.
- That this beats fine-tuned multi-file proposers. We show the bare LLM doesn't need the wrapper if it can output multi-file changes — but commercial agents don't always do that.
- That commercial coding agents are broken. They mostly handle this in their own ways (Cursor's multi-file edits, Claude Code's tool-use loops). The wall manifests when those internal mechanisms aren't engaged.

## 10. Reproducing the Results

The mechanism source is at `lattice_commit/core.py` in the open-source `lattice-commit` PyPI package. The 22 test workspaces and the 986-trial dataset are available on request.

To reproduce on your own workload:

1. Pick a multi-file bug in your project where your current agent has been struggling
2. Install: `pip install lattice-commit`
3. Run: `lattice-commit --workspace ./your_project --test-cmd "your test command"`
4. Compare cycles-to-solve against your baseline

## 11. Citation

> Moon, B. (2026). *Boundary Mechanisms for Efficient AI Systems: Findings from a Multi-Project Research Program*. §3 (The Multi-File Wall). Independent research preprint.

The full synthesis paper is the canonical reference; this document is an extract.
