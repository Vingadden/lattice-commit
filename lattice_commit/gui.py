"""Small Tkinter GUI for the lattice-commit executable."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import (
    BooleanVar,
    Button,
    Checkbutton,
    Entry,
    Frame,
    IntVar,
    Label,
    StringVar,
    Text,
    Tk,
    filedialog,
    messagebox,
)
from tkinter import ttk

from .cli import ollama_fixer
from .core import LatticeCommitSafetyError, incremental_repair
from .smoke import run_self_test


class LatticeCommitApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Lattice Commit")
        self.root.geometry("820x620")
        self.root.minsize(720, 520)

        self.workspace = StringVar()
        self.test_cmd = StringVar(value="python -m pytest -q")
        self.model = StringVar(value="qwen2.5-coder:7b")
        self.ollama_url = StringVar(value="http://localhost:11434")
        self.max_cycles = IntVar(value=5)
        self.majority_vote = IntVar(value=1)
        self.test_timeout = IntVar(value=60)
        self.allow_dirty = BooleanVar(value=False)
        self.last_run_log: str | None = None

        self._build()

    def _build(self) -> None:
        outer = Frame(self.root, padx=18, pady=16)
        outer.pack(fill="both", expand=True)

        Label(outer, text="Lattice Commit", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        Label(
            outer,
            text="Choose a clean git repo, then run a test-gated repair loop. Use Self Test first.",
            fg="#555",
        ).pack(anchor="w", pady=(0, 14))

        form = Frame(outer)
        form.pack(fill="x")

        Label(form, text="Repository").grid(row=0, column=0, sticky="w", pady=4)
        Entry(form, textvariable=self.workspace).grid(row=0, column=1, sticky="ew", padx=(8, 8), pady=4)
        Button(form, text="Browse...", command=self._browse).grid(row=0, column=2, sticky="ew", pady=4)

        Label(form, text="Test command").grid(row=1, column=0, sticky="w", pady=4)
        Entry(form, textvariable=self.test_cmd).grid(row=1, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=4)

        Label(form, text="Ollama model").grid(row=2, column=0, sticky="w", pady=4)
        Entry(form, textvariable=self.model).grid(row=2, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=4)

        Label(form, text="Ollama URL").grid(row=3, column=0, sticky="w", pady=4)
        Entry(form, textvariable=self.ollama_url).grid(row=3, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=4)

        numbers = Frame(form)
        numbers.grid(row=4, column=1, columnspan=2, sticky="w", padx=(8, 0), pady=8)

        Label(numbers, text="Max cycles").pack(side="left")
        ttk.Spinbox(numbers, from_=1, to=200, textvariable=self.max_cycles, width=5).pack(side="left", padx=(6, 18))
        Label(numbers, text="Majority vote").pack(side="left")
        ttk.Spinbox(numbers, from_=1, to=9, textvariable=self.majority_vote, width=5).pack(side="left", padx=(6, 18))
        Label(numbers, text="Timeout sec").pack(side="left")
        ttk.Spinbox(numbers, from_=5, to=3600, textvariable=self.test_timeout, width=6).pack(side="left", padx=(6, 18))
        Checkbutton(numbers, text="Allow dirty tree", variable=self.allow_dirty).pack(side="left")

        form.columnconfigure(1, weight=1)

        actions = Frame(outer)
        actions.pack(fill="x", pady=(12, 8))
        self.self_test_button = Button(actions, text="Run Self Test", command=self.run_self_test)
        self.self_test_button.pack(side="left")
        self.run_button = Button(actions, text="Run Repair", command=self.run_repair)
        self.run_button.pack(side="left", padx=(8, 0))
        self.open_log_button = Button(actions, text="Open Run Log Folder", command=self.open_run_log_folder)
        self.open_log_button.pack(side="left", padx=(8, 0))
        Button(actions, text="Clear Output", command=self.clear_output).pack(side="right")

        self.output = Text(outer, wrap="word", height=18)
        self.output.pack(fill="both", expand=True)
        self.output.insert(
            "end",
            "Ready.\n\n"
            "Repair mode uses Ollama. Make sure Ollama is running and the model is available.\n"
            "Self Test does not need Ollama, pytest, or an API key.\n",
        )

    def _browse(self) -> None:
        selected = filedialog.askdirectory(title="Choose a git repository root")
        if selected:
            self.workspace.set(selected)

    def append(self, text: str) -> None:
        self.output.insert("end", text)
        self.output.see("end")

    def append_threadsafe(self, text: str) -> None:
        self.root.after(0, self.append, text)

    def set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.self_test_button.config(state=state)
        self.run_button.config(state=state)

    def clear_output(self) -> None:
        self.output.delete("1.0", "end")

    def run_self_test(self) -> None:
        self.set_busy(True)
        self.append("\nRunning self-test...\n")

        def work() -> None:
            try:
                workspace, result, latest_commit = run_self_test()
                self.last_run_log = result.run_log
                self.append_threadsafe(
                    f"Self-test workspace: {workspace}\n"
                    f"{result}\n"
                    f"Run log: {result.run_log}\n"
                    f"Latest commit: {latest_commit}\n"
                )
            except Exception as exc:
                self.append_threadsafe(f"Self-test failed: {exc}\n")
                self.root.after(0, messagebox.showerror, "Self-test failed", str(exc))
            finally:
                self.root.after(0, self.set_busy, False)

        threading.Thread(target=work, daemon=True).start()

    def run_repair(self) -> None:
        workspace = self.workspace.get().strip()
        if not workspace:
            messagebox.showerror("Repository required", "Choose a git repository folder first.")
            return

        self.set_busy(True)
        self.append(f"\nRunning repair in {workspace}...\n")

        def work() -> None:
            try:
                fixer = ollama_fixer(model=self.model.get().strip(), url=self.ollama_url.get().strip())
                result = incremental_repair(
                    workspace=workspace,
                    llm_fix=fixer,
                    test_cmd=self.test_cmd.get().strip(),
                    max_cycles=int(self.max_cycles.get()),
                    majority_vote=int(self.majority_vote.get()),
                    test_timeout=int(self.test_timeout.get()),
                    allow_dirty=bool(self.allow_dirty.get()),
                )
                self.last_run_log = result.run_log
                self.append_threadsafe(f"{result}\nRun log: {result.run_log}\n")
            except LatticeCommitSafetyError as exc:
                self.append_threadsafe(f"Safety refusal: {exc}\n")
                self.root.after(0, messagebox.showwarning, "Safety refusal", str(exc))
            except Exception as exc:
                self.append_threadsafe(f"Repair failed: {exc}\n")
                self.root.after(0, messagebox.showerror, "Repair failed", str(exc))
            finally:
                self.root.after(0, self.set_busy, False)

        threading.Thread(target=work, daemon=True).start()

    def open_run_log_folder(self) -> None:
        if not self.last_run_log:
            messagebox.showinfo("No run log yet", "Run Self Test or Run Repair first.")
            return
        folder = Path(self.last_run_log).parent
        subprocess.Popen(["explorer", str(folder)])


def run_headless_self_test(output_path: str | None) -> int:
    workspace, result, latest_commit = run_self_test()
    payload = {
        "workspace": str(workspace),
        "solved": result.solved,
        "cycles": result.cycles,
        "commits": result.commits,
        "files_modified": result.files_modified,
        "run_log": result.run_log,
        "latest_commit": latest_commit,
    }
    if output_path:
        Path(output_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    else:
        print(json.dumps(payload, indent=2))
    return 0 if result.solved else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lattice Commit GUI")
    parser.add_argument("--self-test", action="store_true", help="Run the GUI self-test headlessly")
    parser.add_argument("--self-test-output", help="Write headless self-test JSON to this file")
    args = parser.parse_args(argv)

    if args.self_test:
        return run_headless_self_test(args.self_test_output)

    root = Tk()
    LatticeCommitApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
