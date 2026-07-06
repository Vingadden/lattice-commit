"""Standalone usage: custom LLM proposer with a test command as the signal.

Setup:
    pip install lattice-commit anthropic

Then run from a clean git repo that has tests:
    export ANTHROPIC_API_KEY=sk-ant-...
    export ANTHROPIC_MODEL=<your-model-id>
    python standalone.py
"""

from __future__ import annotations

import os
import shlex
import sys

from lattice_commit import LatticeCommitSafetyError, incremental_repair


def make_anthropic_fix(model: str):
    """Build an llm_fix function that uses Anthropic's API."""
    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise RuntimeError("Install with: pip install anthropic") from exc

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def fix(filepath, content: str, error: str) -> str | None:
        message = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Fix the bug in this file. Return the complete fixed file "
                        "content only - no markdown, no explanation, no prose.\n\n"
                        f"FILE: {filepath}\n"
                        f"TEST OUTPUT:\n{error}\n\n"
                        f"CURRENT CONTENT:\n{content}"
                    ),
                }
            ],
        )
        text = ""
        for block in message.content:
            if hasattr(block, "text"):
                text += block.text
        return text.strip() or None

    return fix


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 1
    if not os.environ.get("ANTHROPIC_MODEL"):
        print("ERROR: ANTHROPIC_MODEL not set", file=sys.stderr)
        return 1

    workspace = sys.argv[1] if len(sys.argv) > 1 else "."
    test_cmd = sys.argv[2] if len(sys.argv) > 2 else "pytest -q"

    print(f"Running incremental repair on {workspace} with test command: {test_cmd}")
    try:
        result = incremental_repair(
            workspace=workspace,
            test_cmd=shlex.split(test_cmd, posix=(os.name != "nt")),
            llm_fix=make_anthropic_fix(os.environ["ANTHROPIC_MODEL"]),
            max_cycles=20,
        )
    except LatticeCommitSafetyError as exc:
        print(f"Safety refusal: {exc}", file=sys.stderr)
        return 2

    print(result)
    print(result.run_log)
    return 0 if result.solved else 1


if __name__ == "__main__":
    sys.exit(main())
