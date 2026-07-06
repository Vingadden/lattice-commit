"""lattice-commit: Incremental commit for LLM code repair.

Wraps a test-gated code editor with a git-native commit/rollback mechanism
for preserving partial progress in multi-file repair loops.

Usage:
    from lattice_commit import incremental_repair

    result = incremental_repair(
        workspace="./my_project",
        llm_fix=my_fix_function,  # (file_path, content, error) -> new_content
        test_cmd=["python", "-m", "pytest", "-q"],
        max_cycles=30,
    )

Or from the command line:
    lattice-commit --workspace ./my_project --test-cmd "pytest -q" --model qwen2.5-coder:7b
"""

__version__ = "0.1.1"

from .core import IncrementalResult, LatticeCommitSafetyError, incremental_repair

__all__ = ["incremental_repair", "IncrementalResult", "LatticeCommitSafetyError"]
