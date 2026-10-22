from __future__ import annotations
import ast
import json
import re
import threading
import tkinter as tk
import tkinter.font as tkfont
import urllib.request

class AIAssistantMixin:
    def _toggle_ai_panel(self) -> None:

        if self.ai_panel_visible:

            self.main.forget(self.ai_panel)

            self.ai_panel_visible = False

            self.ai_toggle_button.configure(text="AI Assistant")

            return

        self.main.add(self.ai_panel, weight=1)

        self.ai_panel_visible = True

        self.ai_toggle_button.configure(text="Hide AI")

        self._refresh_ai_models()

    def _refresh_ai_models(self) -> None:

        self.ai_status.set("Checking local Ollama...")

        def check_models() -> None:

            try:

                with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as response:

                    models = json.load(response).get("models", [])

                names = [item["name"] for item in models if item.get("name")]

                self.root.after(0, lambda: self._show_ai_models(names))

            except Exception as error:

                message = (

                    "Ollama is unavailable. Install and start Ollama, then refresh. "

                    f"Code is sent only to the local Ollama service. ({error})"

                )

                self.root.after(0, lambda text=message: self.ai_status.set(text))

        threading.Thread(target=check_models, daemon=True).start()

    def _show_ai_models(self, models: list[str]) -> None:

        self.ai_model_box.configure(values=models)

        if models:

            if self.ai_model_var.get() not in models:

                self.ai_model_var.set(models[0])

            self.ai_status.set(f"Connected to local Ollama. {len(models)} model(s) available.")

        else:

            self.ai_status.set("Ollama is running, but no models are installed. Choose a model and click Pull Model.")

    def _pull_ai_model(self) -> None:

        model = self.ai_model_var.get().strip()

        if not model:

            self.ai_status.set("Enter a model name first.")

            return

        if self.ai_busy:

            self.ai_status.set("Wait for the current AI request to finish.")

            return

        self.ai_busy = True

        self.ai_pull_button.configure(state=tk.DISABLED)

        self.ai_send_button.configure(state=tk.DISABLED)

        self.ai_complete_button.configure(state=tk.DISABLED)

        self.ai_status.set(f"Downloading {model} from Ollama...")

        def pull_model() -> None:

            error_message = None

            try:

                payload = json.dumps({"name": model, "stream": True}).encode("utf-8")

                request = urllib.request.Request(

                    "http://localhost:11434/api/pull",

                    data=payload,

                    headers={"Content-Type": "application/json"},

                    method="POST",

                )

                with urllib.request.urlopen(request, timeout=30) as response:

                    for line in response:

                        result = json.loads(line)

                        if result.get("error"):

                            raise RuntimeError(result["error"])

                        total = result.get("total")

                        completed = result.get("completed")

                        progress = f" {completed * 100 // total}%" if total and completed else ""

                        status = f"{result.get('status', 'Downloading')}{progress}"

                        self.root.after(0, lambda text=status: self.ai_status.set(text))

            except Exception as error:

                error_message = str(error)

            self.root.after(0, lambda: self._finish_model_pull(error_message))

        threading.Thread(target=pull_model, daemon=True).start()

    def _finish_model_pull(self, error: str | None) -> None:

        self.ai_busy = False

        self.ai_pull_button.configure(state=tk.NORMAL)

        self.ai_send_button.configure(state=tk.NORMAL)

        self.ai_complete_button.configure(state=tk.NORMAL)

        if error:

            self.ai_status.set(f"Could not pull model. Install/start Ollama first. {error}")

        else:

            self.ai_status.set("Model downloaded. Refreshing model list...")

            self._refresh_ai_models()

    def _append_ai_message(self, speaker: str, message: str) -> None:
        body_label = self._create_ai_message_card(speaker)
        body_label.configure(state=tk.NORMAL)
        body_label.insert("1.0", message.strip())
        body_label.configure(state=tk.DISABLED)
        self._size_ai_message_card(body_label)
        self.ai_chat.see(tk.END)

    def _create_ai_message_card(self, speaker: str) -> tk.Text:
        is_assistant = speaker == "Assistant"
        palette = self._active_palette
        card_background = palette["panel"] if is_assistant else palette["surface"]
        card = tk.Frame(
            self.ai_chat,
            background=card_background,
            highlightbackground=(
                self.AI_RESPONSE_RED if is_assistant else palette["border"]
            ),
            highlightthickness=2 if is_assistant else 1,
        )
        card.pack_propagate(False)
        text_font = tkfont.Font(root=self.root, font=("Segoe UI", 10))
        card_width = max(140, self.ai_chat.winfo_width() - 24)
        body_width = max(12, (card_width - 24) // max(1, text_font.measure("0")))
        role_label = tk.Label(
            card,
            text=speaker.upper(),
            background=card_background,
            foreground=(
                self.AI_RESPONSE_RED if is_assistant else palette["muted"]
            ),
            font=("Segoe UI", 9, "bold"),
            anchor=tk.W,
            padx=10,
            pady=4,
        )
        role_label.pack(fill=tk.X)
        body_label = tk.Text(
            card,
            wrap=tk.WORD,
            height=1,
            width=body_width,
            state=tk.DISABLED,
            background=card_background,
            foreground=palette["foreground"],
            font=("Segoe UI", 10),
            borderwidth=0,
            highlightthickness=0,
            padx=10,
            pady=4,
            selectbackground=palette["accent"],
            selectforeground=palette["accent_foreground"],
        )
        body_label.pack(fill=tk.X)
        card.configure(
            width=card_width,
            height=role_label.winfo_reqheight() + body_label.winfo_reqheight() + 8,
        )
        for widget in (card, role_label, body_label):
            widget.bind("<MouseWheel>", self._scroll_ai_chat)
        self._ai_chat_cards.append((card, role_label, body_label, speaker))
        self.ai_chat.configure(state=tk.NORMAL)
        if self._ai_chat_cards[:-1]:
            self.ai_chat.insert(tk.END, "\n")
        self.ai_chat.window_create(
            tk.END,
            window=card,
            align=tk.TOP,
            padx=2,
            pady=3,
            stretch=True,
        )
        self.ai_chat.insert(tk.END, "\n")
        self.ai_chat.configure(state=tk.DISABLED)
        return body_label

    def _size_ai_message_card(self, body: tk.Text) -> None:
        for card, role_label, card_body, _speaker in self._ai_chat_cards:
            if card_body is body:
                display_lines = body.count("1.0", "end-1c", "displaylines")
                line_count = display_lines[0] if display_lines else 1
                body.configure(height=max(1, line_count))
                card.configure(
                    height=role_label.winfo_reqheight() + body.winfo_reqheight() + 8
                )
                return

    def _scroll_ai_chat(self, event: tk.Event) -> str:
        self.ai_chat.yview_scroll(-int(event.delta / 120), "units")
        return "break"

    def _submit_ai_prompt(self, _event: tk.Event | None = None) -> str:

        if self.ai_apply_edits_var.get():

            self._request_script_edit()

        else:

            self._send_ai_message()

        return "break"

    def _send_ai_message(self, _event: tk.Event | None = None) -> str:

        if self.ai_busy:

            self.ai_status.set("Wait for the current AI request to finish.")

            return "break"

        message = self.ai_prompt_entry.get().strip()

        if not message:

            return "break"

        self.ai_prompt_entry.delete(0, tk.END)

        self._append_ai_message("You", message)

        code = self.editor.get("1.0", "end-1c")[-12000:]

        history = "\n".join(

            f"{speaker}: {text}" for speaker, text in self.ai_history[-8:]

        )

        self.ai_history.append(("You", message))

        prompt = (

            f"{self.ai_system_prompt_var.get()}\n"

            f"Recent conversation:\n{history or '(none)'}\n\n"

            f"Open file code:\n```python\n{code}\n```\n\nUser: {message}"

        )

        self._request_ai(prompt, "chat")

        return "break"

    def _request_script_edit(self) -> None:

        if self.ai_busy:

            self.ai_status.set("Wait for the current AI request to finish.")

            return

        instruction = self.ai_prompt_entry.get().strip()

        if not instruction:

            self.ai_status.set("Describe the script change in the prompt field first.")

            self.ai_prompt_entry.focus_set()

            return

        source = self.editor.get("1.0", "end-1c")

        self.pending_script_edit = None

        self.pending_script_source = source

        self.pending_script_path = self.current_file

        self.ai_prompt_entry.delete(0, tk.END)

        self._append_ai_message("You", f"Edit script: {instruction}")

        recent_history = "\n".join(

            f"{speaker}: {text}" for speaker, text in self.ai_history[-8:]

        )

        self.ai_history.append(("You", f"Edit script: {instruction}"))

        extension = self.current_file.suffix.lower() if self.current_file else ".py"

        language = {

            ".py": "Python",

            ".html": "HTML",

            ".htm": "HTML",

            ".css": "CSS",

            ".json": "JSON",

            ".js": "JavaScript",

            ".mjs": "JavaScript",

            ".cjs": "JavaScript",

            ".javascript": "JavaScript",

            ".java": "Java",

        }.get(extension)

        if language is None:

            self.pending_script_source = None

            self.pending_script_path = None

            self.ai_status.set(f"AI file editing is not supported for {extension or 'this file'}.")

            return

        prompt = (

            f"{self.ai_system_prompt_var.get()}\n\n"

            f"Edit the user's complete {language} file. Return a full replacement for the entire file "

            f"in exactly one ```{language.lower()} code block. Preserve unrelated behavior. "

            "If the request is ambiguous, ask a question instead of returning code.\n\n"

            f"Recent conversation:\n{recent_history or '(none)'}\n\n"

            f"Current file:\n```{language.lower()}\n{source}\n```\n\n"

            f"Requested change: {instruction}"

        )

        self._request_ai(prompt, "edit")

    def _apply_script_edit(self, replacement: str) -> None:

        current_source = self.editor.get("1.0", "end-1c")

        if (

            current_source != self.pending_script_source

            or self.current_file != self.pending_script_path

        ):

            self.ai_status.set("The open script changed while AI was working. No edit was applied.")

            self._append_ai_message(

                "Assistant",

                "The open file or its contents changed during the request, so I did not apply the edit. Try again.",

            )

            return

        self.editor.edit_separator()

        self.editor.delete("1.0", tk.END)

        self.editor.insert("1.0", replacement)

        self.editor.edit_modified(False)

        self.editor.edit_separator()

        self.dirty = True

        self._set_title()

        self._schedule_syntax_highlighting()

        if self._autosave_after_id is not None:

            self.root.after_cancel(self._autosave_after_id)

        self._autosave_after_id = self.root.after(500, self._autosave)

        self.status.set("AI edit applied; autosaving script...")

        self.ai_status.set("AI edit applied to the editor. Undo with Ctrl+Z if needed.")

        self.pending_script_edit = None

        self.pending_script_source = None

        self.pending_script_path = None

    def _completion_shortcut(self, _event: tk.Event) -> str:

        self._request_completion()

        return "break"

    def _request_completion(self) -> None:

        if self.ai_busy:

            self.ai_status.set("Wait for the current AI request to finish.")

            return

        self.pending_completion_source = self.editor.get("1.0", "end-1c")

        self.pending_completion_index = self.editor.index(tk.INSERT)

        before = self.editor.get("1.0", tk.INSERT)[-8000:]

        after = self.editor.get(tk.INSERT, "end-1c")[:2000]

        prompt = (

            "Complete the Python code at the cursor. Return only the text to insert, "

            "with no explanation or Markdown fences.\n\n"

            f"Code before cursor:\n```python\n{before}\n```\n"

            f"Cursor is here. Code after cursor:\n```python\n{after}\n```"

        )

        self._append_ai_message("You", "Complete code at cursor")

        self._request_ai(prompt, "completion")

    def _explain_last_run(self) -> None:

        if self.ai_busy:

            self.ai_status.set("Wait for the current AI request to finish.")

            return

        output = (
            getattr(self, "last_run_error", "") or self.last_run_output
        )[-12000:].strip()

        if not output:

            self._append_ai_message("Assistant", "There is no captured run output to explain yet. Run a file first.")

            return

        code = self.editor.get("1.0", "end-1c")[-8000:]
        language = self.current_file.suffix.lstrip(".") if self.current_file else "text"
        self._append_ai_message("You", "Explain the last run output")
        prompt = (
            "Explain the program output or error below. Identify the likely cause and give a concise fix. "
            "Do not change the code automatically.\n\n"
            f"Open source code:\n```{language}\n{code}\n```\n\n"
            f"Last run output:\n```text\n{output}\n```"
        )
        self._request_ai(prompt, "explanation")

    def _fix_last_run_with_ai(self) -> None:
        if not self.ai_panel_visible:
            self._toggle_ai_panel()
        self._explain_last_run()

    def _begin_ai_stream(self) -> None:
        self._ai_stream_label = self._create_ai_message_card("Assistant")
        self._ai_stream_active = True

    def _append_ai_stream_chunk(self, chunk: str) -> None:
        if not getattr(self, "_ai_stream_active", False):
            return
        if self._ai_stream_label is not None:
            self._ai_stream_label.configure(state=tk.NORMAL)
            self._ai_stream_label.insert(tk.END, chunk)
            self._ai_stream_label.configure(state=tk.DISABLED)
            self._size_ai_message_card(self._ai_stream_label)
        self.ai_chat.see(tk.END)

    def _finish_ai_stream(self) -> None:
        if not getattr(self, "_ai_stream_active", False):
            return
        self._ai_stream_active = False
        self._ai_stream_label = None
        self.ai_chat.see(tk.END)

    def _request_ai(self, prompt: str, action: str) -> None:

        if self.ai_busy:

            self.ai_status.set("Wait for the current AI request to finish.")

            return

        model = self.ai_model_var.get().strip()

        if not model:

            self.ai_status.set("Choose an Ollama model first.")

            return

        self.ai_busy = True

        self.ai_status.set(f"Asking {model}...")

        self.ai_send_button.configure(state=tk.DISABLED)

        self.ai_complete_button.configure(state=tk.DISABLED)

        self.ai_edit_button.configure(state=tk.DISABLED)
        self._begin_ai_stream()

        def generate() -> None:

            result_parts: list[str] = []
            error_message = None

            try:

                payload = json.dumps(

                    {

                        "model": model,

                        "prompt": prompt,

                        "stream": True,

                        "temperature": self.ai_temperature_var.get(),

                    }

                ).encode("utf-8")

                request = urllib.request.Request(

                    "http://localhost:11434/api/generate",

                    data=payload,

                    headers={"Content-Type": "application/json"},

                    method="POST",

                )

                with urllib.request.urlopen(request, timeout=180) as response:

                    for line in response:
                        if not line.strip():
                            continue
                        message = json.loads(line)
                        chunk = message.get("response", "")
                        if chunk:
                            result_parts.append(chunk)
                            self.root.after(0, self._append_ai_stream_chunk, chunk)

            except urllib.error.HTTPError as error:

                try:

                    details = json.loads(error.read().decode("utf-8")).get("error", str(error))

                except (UnicodeError, json.JSONDecodeError):

                    details = str(error)

                error_message = f"HTTP {error.code}: {details}"

            except Exception as error:

                error_message = str(error)

            result = "".join(result_parts).strip()
            self.root.after(
                0, lambda: self._finish_ai_request(action, result, error_message)
            )

        threading.Thread(target=generate, daemon=True).start()

    def _finish_ai_request(self, action: str, result: str | None, error: str | None) -> None:

        self._finish_ai_stream()
        self.ai_busy = False

        self.ai_send_button.configure(state=tk.NORMAL)

        self.ai_complete_button.configure(state=tk.NORMAL)

        self.ai_edit_button.configure(state=tk.NORMAL)

        if error:

            if action == "edit":

                self.pending_script_edit = None

                self.pending_script_source = None

                self.pending_script_path = None

            if error.startswith("HTTP 404:"):

                model = self.ai_model_var.get().strip()

                setup = (

                    f"Run `ollama signin`, then `ollama pull {model}`, then refresh the model list."

                    if model.endswith(":cloud")

                    else f"Run `ollama pull {model}`, then refresh the model list."

                )

                message = (

                    f"Ollama is running, but model {model!r} is unavailable. "

                    f"{setup}"

                )

                self.ai_status.set(message)

                self._append_ai_message("Assistant", f"Model not found. {error}\n{message}")

            else:

                self.ai_status.set(f"AI request failed. Check Ollama and the selected model: {error}")

                self._append_ai_message("Assistant", f"Could not reach Ollama: {error}")

            return

        if not result or not result.strip():

            self.ai_status.set("The model returned an empty response.")

            self._append_ai_message("Assistant", "The model returned an empty response.")

            return

        answer = result.strip()

        self.ai_history.append(("Assistant", answer))

        self.ai_status.set("Ready. Your code was sent to the local Ollama service.")

        if action == "edit":

            match = re.search(

                r"```[^\r\n]*\r?\n(.*?)```", answer, re.DOTALL

            )

            replacement = match.group(1) if match else ""

            if not replacement.strip():

                self.pending_script_edit = None

                self.pending_script_source = None

                self.pending_script_path = None

                self.ai_status.set("The AI responded without code; no changes were made.")


                return

            extension = self.pending_script_path.suffix.lower() if self.pending_script_path else ".py"

            try:

                if extension == ".py":

                    ast.parse(replacement)

                elif extension == ".json":

                    json.loads(replacement)

            except (SyntaxError, json.JSONDecodeError) as syntax_error:

                self.pending_script_edit = None

                self.pending_script_source = None

                self.pending_script_path = None

                self.ai_status.set(f"AI returned invalid {extension[1:].upper()} code: {syntax_error}")

                self._append_ai_message(

                    "Assistant",

                    f"I couldn't apply that response because it wasn't valid {extension[1:].upper()}.",

                )

                return

            self.pending_script_edit = replacement

            self._apply_script_edit(replacement)

        elif action == "completion":

            lines = answer.splitlines()

            if lines and lines[0].strip().startswith("```"):

                lines = lines[1:]

            if lines and lines[-1].strip() == "```":

                lines = lines[:-1]

            completion = "\n".join(lines)

            current_source = self.editor.get("1.0", "end-1c")

            if (

                self.pending_completion_index is None

                or current_source != self.pending_completion_source

            ):

                self.ai_status.set("The code changed while completion was running; nothing was inserted.")

            elif completion:

                insertion_index = self.pending_completion_index

                self.editor.insert(insertion_index, completion)

                end_index = self.editor.index(f"{insertion_index} + {len(completion)} chars")

                self.editor.mark_set(tk.INSERT, end_index)

                self.editor.focus_set()

                self.ai_status.set("AI completion inserted at the cursor.")

            else:

                self.ai_status.set("The AI returned an empty completion.")

            self.pending_completion_source = None

            self.pending_completion_index = None

    def _edit_system_prompt(self) -> None:

        dialog = tk.Toplevel(self.root)

        dialog.title("System Prompt")

        dialog.transient(self.root)

        dialog.resizable(False, False)

        dialog.columnconfigure(0, weight=1)

        dialog.rowconfigure(0, weight=1)

        text = tk.Text(dialog, wrap=tk.WORD, font=("Segoe UI", 10), padx=8, pady=8)

        text.grid(row=0, column=0, sticky="nsew")

        text.insert("1.0", self.ai_system_prompt_var.get())

        scroll = ttk.Scrollbar(dialog, orient=tk.VERTICAL, command=text.yview)

        scroll.grid(row=0, column=1, sticky="ns")

        text.configure(yscrollcommand=scroll.set)

        button_frame = ttk.Frame(dialog)

        button_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        def save() -> None:

            self.ai_system_prompt_var.set(text.get("1.0", "end-1c").strip())

            self._save_settings()

            dialog.destroy()

        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(

            side=tk.RIGHT, padx=(4, 0)

        )

        ttk.Button(button_frame, text="Save", command=save).pack(side=tk.RIGHT)

    def _clear_ai_history(self) -> None:

        self.ai_history.clear()
        self.ai_chat.configure(state=tk.NORMAL)
        self.ai_chat.delete("1.0", tk.END)
        self.ai_chat.configure(state=tk.DISABLED)
        for card, _role_label, _body_label, _speaker in self._ai_chat_cards:
            if card.winfo_exists():
                card.destroy()
        self._ai_chat_cards.clear()
        self._ai_stream_label = None
        self._ai_stream_active = False
        self.ai_status.set("AI conversation history cleared.")

        self._save_settings()
