from __future__ import annotations
import json
import queue
import subprocess
import sys
import threading
import tkinter as tk
import tokenize
import traceback
import webbrowser
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from runners.java import java_command
from runners.web_js import javascript_command

class RunnerMixin:
    def _append_output(self, text: str) -> None:
        self.output.configure(state=tk.NORMAL)
        self.output.insert(tk.END, text)
        self.output.see(tk.END)
        self.output.configure(state=tk.DISABLED)

    def run_file(self) -> None:
        if self.process is not None:
            self.status.set("A file is already running")
            return
        if self.current_file is None:
            if not self.dirty:
                messagebox.showinfo(
                    "Save File First", "Save this file before running it.", parent=self.root
                )
                return
        if not self.save_file():
            return

        self.output.configure(state=tk.NORMAL)
        self.output.delete("1.0", tk.END)
        self.output.configure(state=tk.DISABLED)
        self.last_run_output = ""
        path = self.current_file
        extension = path.suffix.lower()

        if extension in {".html", ".htm"}:
            self._open_in_browser(path)
            return

        if extension == ".css":
            preview = next(
                (
                    candidate
                    for candidate in (
                        path.with_suffix(".html"),
                        path.with_suffix(".htm"),
                        path.parent / "index.html",
                        path.parent / "index.htm",
                    )
                    if candidate.is_file()
                ),
                None,
            )
            if preview is None:
                message = (
                    "CSS needs an HTML page to preview. Add a same-name HTML file "
                    "or an index.html file in this folder."
                )
                self._append_output(message + "\n")
                self.last_run_output = message
                self.status.set("No HTML page found for CSS preview")
                return
            self._open_in_browser(preview)
            return

        if extension == ".json":
            try:
                with path.open(encoding="utf-8") as source_file:
                    formatted_json = json.dumps(
                        json.load(source_file), indent=2, ensure_ascii=False
                    )
            except (OSError, UnicodeError, json.JSONDecodeError) as error:
                message = f"JSON validation failed: {error}"
                self._append_output(message + "\n")
                self.last_run_output = message
                self.status.set("JSON validation failed")
                return
            self._append_output(formatted_json + "\n")
            self.last_run_output = formatted_json
            self.status.set("Valid JSON")
            return

        if extension == ".py":
            try:
                with tokenize.open(path) as source_file:
                    source = source_file.read()
                compile(source, str(path), "exec")
            except (OSError, SyntaxError, UnicodeError) as error:
                compile_error = "".join(traceback.format_exception(error))
                self.last_run_output = compile_error
                self._append_output(f"Compile failed:\n{compile_error}")
                self.status.set("Compile failed; script was not run")
                return
            self._append_output("Compile succeeded. Running script...\n\n")
            command = [sys.executable, "-u", str(path)]
        elif extension in {".js", ".mjs", ".cjs", ".javascript"}:
            self._append_output("Running JavaScript with Node.js...\n\n")
            command = javascript_command(path)
        elif extension == ".java":
            self._append_output("Running Java source file...\n\n")
            command = java_command(path)
        else:
            message = f"Running files with the {extension or 'unknown'} extension is not supported."
            self._append_output(message + "\n")
            self.last_run_output = message
            self.status.set("Unsupported file type")
            return

        try:
            self.process = subprocess.Popen(
                command,
                cwd=str(path.parent),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except FileNotFoundError:
            runtime = {
                "node": "Node.js",
                "java": "Java 11 or newer",
            }.get(command[0], "Python")
            message = f"{runtime} was not found. Install it and ensure its command is on PATH."
            self.process = None
            self.last_run_output = message
            self._append_output(message + "\n")
            self.status.set(f"Could not start: {runtime} was not found")
            messagebox.showerror("Could Not Run File", message, parent=self.root)
            return
        except OSError as error:
            self.process = None
            message = f"Could not start {path.name}: {error}"
            self.last_run_output = message
            self._append_output(message + "\n")
            self.status.set("Could not start program")
            messagebox.showerror("Could Not Run File", message, parent=self.root)
            return

        process = self.process
        self._stop_requested = False
        self.run_button.configure(state=tk.DISABLED, text="Running...")
        self.stop_button.configure(state=tk.NORMAL)
        self.stdin_entry.configure(state=tk.NORMAL)
        self.stdin_send_button.configure(state=tk.NORMAL)
        self.stdin_entry.focus_set()
        self.status.set(f"Running {path.name}...")

        def read_output() -> None:
            if process.stdout is not None:
                while True:
                    character = process.stdout.read(1)
                    if not character:
                        break
                    self.output_queue.put(("output", character))
            self.output_queue.put(("done", process.wait()))

        threading.Thread(target=read_output, daemon=True).start()

    def _open_in_browser(self, path: Path) -> None:
        try:
            opened = webbrowser.open(path.resolve().as_uri())
        except (OSError, webbrowser.Error) as error:
            opened = False
            details = str(error)
        else:
            details = "No browser could be opened."
        if not opened:
            self._append_output(f"Could not open {path}: {details}\n")
            self.last_run_output = f"Could not open {path}: {details}"
            self.status.set("Could not open file in browser")
            messagebox.showerror("Could Not Open Browser", details, parent=self.root)
            return
        message = f"Opened {path.name} in your browser."
        self._append_output(message + "\n")
        self.last_run_output = message
        self.status.set(message)

    def _read_process_output(self) -> None:
        output_text: list[str] = []
        try:
            while True:
                kind, value = self.output_queue.get_nowait()
                if kind == "output":
                    output_text.append(str(value))
                else:
                    if output_text:
                        chunk = "".join(output_text)
                        self.last_run_output = (self.last_run_output + chunk)[-20000:]
                        self._append_output(chunk)
                        output_text.clear()
                    self.process = None
                    self.run_button.configure(state=tk.NORMAL)
                    self.run_button.configure(text="Run ▶")
                    self.stop_button.configure(state=tk.DISABLED)
                    self.stdin_entry.configure(state=tk.DISABLED)
                    self.stdin_send_button.configure(state=tk.DISABLED)
                    if self._stop_requested:
                        self.status.set("Stopped by user")
                    elif value == 0:
                        self.status.set("Finished successfully")
                    else:
                        self.status.set(f"Program exited with errors (exit code {value})")
                    self._stop_requested = False
        except queue.Empty:
            if output_text:
                chunk = "".join(output_text)
                self.last_run_output = (self.last_run_output + chunk)[-20000:]
                self._append_output(chunk)
        if not self._closing:
            self.root.after(60, self._read_process_output)

    def _send_terminal_input(self, _event: tk.Event | None = None) -> str:
        process = self.process
        text = self.stdin_entry.get()
        if process is None or process.stdin is None:
            return "break"
        try:
            process.stdin.write(text + "\n")
            process.stdin.flush()
        except (BrokenPipeError, OSError) as error:
            self.status.set(f"Could not send input: {error}")
            return "break"
        self._append_output(text + "\n")
        self.stdin_entry.delete(0, tk.END)
        self.stdin_entry.focus_set()
        return "break"

    def stop_file(self) -> None:
        if self.process is not None:
            self._stop_requested = True
            self.process.terminate()
            self.status.set("Stopping...")

    def _on_close(self) -> None:
        if not self._save_pending_changes():
            return
        self._closing = True
        if self._syntax_after_id is not None:
            self.root.after_cancel(self._syntax_after_id)
        if self.process is not None:
            self.process.terminate()
        self.root.destroy()
