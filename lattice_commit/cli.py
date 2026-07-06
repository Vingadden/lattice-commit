"""Command-line interface for lattice-commit.

Usage:
    python -m lattice_commit --workspace ./my_project --test-cmd "pytest -q"
    python -m lattice_commit --workspace ./my_project --model qwen2.5-coder:7b
"""

import argparse
import json
import os
import shlex
import sys
import urllib.request
from pathlib import Path

from . import __version__
from .core import LatticeCommitSafetyError, incremental_repair
from .smoke import run_self_test


def ollama_fixer(model: str = "qwen2.5-coder:7b", url: str = "http://localhost:11434"):
    """Create an LLM fix function using Ollama."""

    def fix(filepath: Path, content: str, error_output: str):
        prompt = (
            f"Fix this file's bug(s).\n\n"
            f"File: {filepath.name}\n```\n{content}\n```\n\n"
            f"Test failures:\n```\n{error_output[-1500:]}\n```\n\n"
            f"Output ONLY the complete fixed file:"
        )
        try:
            payload = json.dumps({
                "model": model, "prompt": prompt, "stream": False,
                "options": {"temperature": 0.2, "num_predict": 1024},
            }).encode()
            req = urllib.request.Request(
                f"{url}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode())
            text = result.get("response", "").strip()
            # Strip markdown fences
            if text.startswith("```"):
                lines = text.split("\n")
                end = len(lines)
                for i in range(1, len(lines)):
                    if lines[i].strip() == "```":
                        end = i
                        break
                text = "\n".join(lines[1:end]).strip()
            return text if text and text != content else None
        except Exception:
            return None

    return fix


def main():
    parser = argparse.ArgumentParser(
        description="lattice-commit: git checkpoints for test-gated LLM code repair",
        epilog="Requires a clean git repository by default; commits improvements and resets regressions.",
    )
    parser.add_argument("--self-test", action="store_true",
                        help="Run a disposable local smoke test and exit")
    parser.add_argument("--workspace", "-w",
                        help="Path to the project directory")
    parser.add_argument("--test-cmd", "-t", default="python -m pytest -q",
                        help="Test command (default: 'python -m pytest -q')")
    parser.add_argument("--model", "-m", default="qwen2.5-coder:7b",
                        help="Ollama model to use (default: qwen2.5-coder:7b)")
    parser.add_argument("--max-cycles", "-c", type=int, default=30,
                        help="Maximum repair cycles (default: 30)")
    parser.add_argument("--ollama-url", default="http://localhost:11434",
                        help="Ollama API URL")
    parser.add_argument("--majority-vote", "-v", type=int, default=1,
                        help="Number of test runs for majority vote (use 3 for flaky tests)")
    parser.add_argument("--test-timeout", type=int, default=60,
                        help="Seconds before each test run times out (default: 60)")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="Allow starting from a dirty git tree (unsafe; default refuses)")

    args = parser.parse_args()

    if args.self_test:
        print(f"lattice-commit v{__version__}")
        print("  self-test: creating a disposable failing git repo")
        try:
            workspace, result, latest_commit = run_self_test()
        except Exception as e:
            print(f"Self-test failed: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"  workspace: {workspace}")
        print(f"  result:    {result}")
        if result.run_log:
            print(f"  run log:   {result.run_log}")
        print(f"  commit:    {latest_commit}")
        sys.exit(0 if result.solved else 1)

    if not args.workspace:
        parser.error("--workspace is required unless --self-test is used")

    print(f"lattice-commit v{__version__}")
    print(f"  workspace: {args.workspace}")
    print(f"  test-cmd:  {args.test_cmd}")
    print(f"  model:     {args.model}")
    print(f"  max-cycles: {args.max_cycles}")
    print(f"  test-timeout: {args.test_timeout}s")
    if args.majority_vote > 1:
        print(f"  majority-vote: {args.majority_vote}x (for flaky tests)")
    print()

    fixer = ollama_fixer(model=args.model, url=args.ollama_url)
    test_cmd = shlex.split(args.test_cmd, posix=(os.name != "nt"))

    try:
        result = incremental_repair(
            workspace=args.workspace,
            llm_fix=fixer,
            test_cmd=test_cmd,
            max_cycles=args.max_cycles,
            majority_vote=args.majority_vote,
            allow_dirty=args.allow_dirty,
            test_timeout=args.test_timeout,
        )
    except LatticeCommitSafetyError as e:
        print(f"Safety refusal: {e}", file=sys.stderr)
        sys.exit(2)

    print(f"\n{result}")
    if result.run_log:
        print(f"run log: {result.run_log}")
    sys.exit(0 if result.solved else 1)


if __name__ == "__main__":
    main()
