
from __future__ import annotations

import ast
import fnmatch
import io
import json
import keyword
import queue
import shutil
import re
import subprocess
import sys
import threading
import tkinter as tk
import token
import tokenize
import traceback
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from tkinter import font as tkfont


class PythonEditor:
    VERSION = "1.0.2"
    SUPPORTED_FILETYPES = (
        ("Supported files", "*.py *.html *.htm *.css *.json *.js *.mjs *.cjs *.javascript *.java"),
        ("Python files", "*.py"),
        ("HTML files", "*.html *.htm"),
        ("CSS files", "*.css"),
        ("JSON files", "*.json"),
        ("JavaScript files", "*.js *.mjs *.cjs *.javascript"),
        ("Java files", "*.java"),
        ("All files", "*.*"),
    )
    FILE_ICONS = {
        ".py": "python",
        ".html": "html",
        ".htm": "html",
        ".css": "css",
        ".json": "json",
        ".js": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".javascript": "javascript",
        ".java": "java",
    }
    THEMES = {
        "Light": {
            "background": "#ffffff", "foreground": "#202124", "selection": "#cde8ff",
            "keyword": "#7b2cbf", "constant": "#b42318", "string": "#18794e",
            "comment": "#777f8b", "number": "#a04b00", "operator": "#405a78",
            "panel": "#f3f4f6", "field": "#ffffff", "surface": "#f3f4f6",
            "border": "#c9cdd3", "muted": "#68707c", "accent": "#c9363e",
            "accent_hover": "#ad2931", "accent_foreground": "#ffffff",
        },
        "Dark": {
            "background": "#17181b", "foreground": "#e2e4e9", "selection": "#702b31",
            "keyword": "#cf8ef4", "constant": "#ff7b72", "string": "#a5d6a7",
            "comment": "#89929e", "number": "#f2b880", "operator": "#91b9e8",
            "panel": "#1e2024", "field": "#191a1e", "surface": "#292b30",
            "border": "#393c43", "muted": "#a0a5af", "accent": "#e0444d",
            "accent_hover": "#f0525b", "accent_foreground": "#ffffff",
        },
        "Forest": {
            "background": "#f1f5ef", "foreground": "#27352a", "selection": "#c9dfc7",
            "keyword": "#7651a6", "constant": "#b64f39", "string": "#28734d",
            "comment": "#748276", "number": "#a46526", "operator": "#386778",
            "panel": "#e8eee5", "field": "#ffffff", "surface": "#e8eee5",
            "border": "#c4d0c1", "muted": "#667469", "accent": "#4b7657",
            "accent_hover": "#3c6548", "accent_foreground": "#ffffff",
        },
    }
    SYNTAX_TAGS = ("keyword", "constant", "string", "comment", "number", "operator")
    CUSTOMIZABLE_COLORS = (
        ("background", "Background"),
        ("keyword", "Keyword"),
        ("comment", "Comment"),
        ("panel", "Panel"),
        ("border", "Border"),
        ("accent_hover", "Accent Hover"),
    )

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("GRAVEL Code Editor")
        self.root.geometry("1100x720")
        self.root.minsize(720, 480)

        self.current_file: Path | None = None
        self.project_folder: Path | None = None
        self.process: subprocess.Popen[str] | None = None
        self.output_queue: queue.Queue[tuple[str, str | int]] = queue.Queue()
        self.last_run_output = ""
        self.dirty = False
        self._stop_requested = False
        self._autosave_after_id: str | None = None
        self._syntax_after_id: str | None = None
        self._closing = False
        self.settings_path = Path.home() / ".gravel" / "settings.json"
        initial_theme, self.custom_theme_colors, self.recent_paths = self._load_settings()
        self.theme_var = tk.StringVar(value=initial_theme)
        self.tab_size_var = tk.IntVar(value=4)
        self.ai_apply_edits_var = tk.BooleanVar(value=True)
        images_folder = Path(__file__).resolve().parent / "images"
        self.file_icon_images = {
            icon_name: tk.PhotoImage(
                file=str(images_folder / f"{icon_name}.png")
            ).subsample(2, 2)
            for icon_name in set(self.FILE_ICONS.values())
        }
        welcome_logo = tk.PhotoImage(file=str(images_folder / "logo.png"))
        self.welcome_logo_large = welcome_logo.subsample(3, 3)
        self.welcome_logo_small = welcome_logo.subsample(4, 4)
        self.ai_model_var = tk.StringVar(value="gemma4:cloud")
        self.ai_status = tk.StringVar(value="Local Ollama model not checked")
        self.ai_history: list[tuple[str, str]] = []
        self.ai_busy = False
        self.pending_script_edit: str | None = None
        self.pending_script_source: str | None = None
        self.pending_script_path: Path | None = None
        self.pending_completion_source: str | None = None
        self.pending_completion_index: str | None = None
        self.ai_panel_visible = False

        self._create_menu()
        self._create_widgets()
        self._set_theme(self.theme_var.get())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind_all("<Control-o>", self._open_file_shortcut)
        self.root.bind_all("<Control-Shift-O>", self._open_folder_shortcut)
        self.root.bind_all("<Control-s>", self._save_shortcut)
        self.root.bind_all("<Control-n>", self._new_file_shortcut)
        self.root.bind_all("<F5>", self._run_shortcut)
        self.root.after(60, self._read_process_output)

    def _create_menu(self) -> None:
        self.menu = tk.Menu(self.root)
        file_menu = tk.Menu(self.menu, tearoff=False)
        file_menu.add_command(label="New File", accelerator="Ctrl+N", command=self.new_file)
        file_menu.add_command(label="Open File...", accelerator="Ctrl+O", command=self.open_file)
        file_menu.add_command(
            label="Open Folder...", accelerator="Ctrl+Shift+O", command=self.open_folder
        )
        self.recent_menu = tk.Menu(file_menu, tearoff=False)
        self._refresh_recent_menu()
        file_menu.add_cascade(label="Recent Files", menu=self.recent_menu)
        file_menu.add_separator()
        file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self.save_file)
        file_menu.add_command(label="Save As...", command=self.save_file_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        self.menu.add_cascade(label="File", menu=file_menu)

        run_menu = tk.Menu(self.menu, tearoff=False)
        run_menu.add_command(label="Run Current File", accelerator="F5", command=self.run_file)
        run_menu.add_command(label="Stop", command=self.stop_file)
        self.menu.add_cascade(label="Run", menu=run_menu)

        view_menu = tk.Menu(self.menu, tearoff=False)
        theme_menu = self._create_theme_menu(view_menu)
        view_menu.add_cascade(label="Theme", menu=theme_menu)
        self.menu.add_cascade(label="View", menu=view_menu)

        settings_menu = tk.Menu(self.menu, tearoff=False)
        tab_size_menu = tk.Menu(settings_menu, tearoff=False)
        for tab_size in (2, 4, 8):
            tab_size_menu.add_radiobutton(
                label=f"{tab_size} spaces",
                variable=self.tab_size_var,
                value=tab_size,
                command=self._apply_tab_size,
            )
        settings_menu.add_cascade(label="Tab Size", menu=tab_size_menu)
        theme_menu.add_separator()
        theme_menu.add_command(
            label="Customize Theme Colors...",
            command=self._customize_theme_colors,
        )
        theme_menu.add_command(
            label="Reset Colors to Light",
            command=self._reset_colors_to_light,
        )
        self.menu.add_cascade(label="Settings", menu=settings_menu)
        self.root.config(menu=self.menu)

    def _create_theme_menu(self, parent: tk.Menu) -> tk.Menu:
        theme_menu = tk.Menu(parent, tearoff=False)
        for theme_name in self.THEMES:
            theme_menu.add_radiobutton(
                label=theme_name,
                variable=self.theme_var,
                value=theme_name,
                command=self._select_theme,
            )
        return theme_menu

    def _load_settings(self) -> tuple[str, dict[str, dict[str, str]], list[str]]:
        try:
            with self.settings_path.open(encoding="utf-8") as settings_file:
                settings = json.load(settings_file)
        except FileNotFoundError:
            return "Light", {}, []
        except (json.JSONDecodeError, UnicodeError) as error:
            messagebox.showwarning(
                "Settings", f"Could not read settings file:\n{error}", parent=self.root
            )
            return "Light", {}, []
        except OSError as error:
            messagebox.showwarning(
                "Settings", f"Could not read settings file:\n{error}", parent=self.root
            )
            return "Light", {}, []

        if not isinstance(settings, dict):
            messagebox.showwarning(
                "Settings",
                "Settings file has an invalid format. Using default settings.",
                parent=self.root,
            )
            return "Light", {}, []

        theme = settings.get("theme")
        if not isinstance(theme, str) or theme not in self.THEMES:
            if "theme" in settings:
                messagebox.showwarning(
                    "Settings",
                    "Saved theme is invalid. Using the Light theme.",
                    parent=self.root,
                )
            theme = "Light"

        custom_colors: dict[str, dict[str, str]] = {}
        saved_colors = settings.get("custom_colors", {})
        if isinstance(saved_colors, dict):
            for theme_name, colors in saved_colors.items():
                if theme_name not in self.THEMES or not isinstance(colors, dict):
                    continue
                valid_colors = {
                    color_name: color
                    for color_name, color in colors.items()
                    if color_name in dict(self.CUSTOMIZABLE_COLORS)
                    and isinstance(color, str)
                    and re.fullmatch(r"#[0-9a-fA-F]{6}", color)
                }
                if valid_colors:
                    custom_colors[theme_name] = valid_colors

        recent = settings.get("recent_files", [])
        recent_paths: list[str] = []
        if isinstance(recent, list):
            recent_paths = [
                item
                for item in recent
                if isinstance(item, str) and Path(item).exists()
            ][:8]
        return theme, custom_colors, recent_paths

    def _save_settings(self) -> bool:
        settings = {
            "theme": self.theme_var.get(),
            "custom_colors": self.custom_theme_colors,
            "recent_files": self.recent_paths,
        }
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            with self.settings_path.open("w", encoding="utf-8") as settings_file:
                json.dump(settings, settings_file, indent=2)
                settings_file.write("\n")
        except OSError as error:
            messagebox.showerror(
                "Settings", f"Could not save settings:\n{error}", parent=self.root
            )
            return False
        return True

    def _select_theme(self) -> None:
        self._set_theme(self.theme_var.get())
        self._save_settings()

    def _reset_colors_to_light(self) -> None:
        previous_theme = self.theme_var.get()
        previous_colors = {
            theme_name: colors.copy()
            for theme_name, colors in self.custom_theme_colors.items()
        }
        self.theme_var.set("Light")
        self.custom_theme_colors.clear()
        self._set_theme("Light")
        if not self._save_settings():
            self.custom_theme_colors.update(previous_colors)
            self.theme_var.set(previous_theme)
            self._set_theme(previous_theme)

    def _customize_theme_colors(self) -> None:
        theme_name = self.theme_var.get()
        original_colors = self.custom_theme_colors.get(theme_name, {}).copy()
        palette = {
            **self.THEMES[theme_name],
            **original_colors,
        }
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Customize {theme_name} Theme")
        dialog.transient(self.root)
        dialog.resizable(True, True)
        dialog.geometry("820x680")
        dialog.minsize(720, 600)
        dialog.configure(background=palette["background"])

        tk.Label(
            dialog,
            text="Adjust the RGB sliders to customize this theme.",
            anchor=tk.W,
            padx=12,
            pady=10,
            background=palette["background"],
            foreground=palette["foreground"],
        ).pack(fill=tk.X)

        controls: dict[str, tuple[list[tk.IntVar], tk.Label]] = {}

        def update_color(color_name: str) -> None:
            values, preview = controls[color_name]
            color = "#{:02x}{:02x}{:02x}".format(
                *(channel.get() for channel in values)
            )
            preview.configure(background=color)
            self.custom_theme_colors.setdefault(theme_name, {})[color_name] = color
            self._set_theme(theme_name)

        def slider_changed(color_name: str, channel_index: int, value: str) -> None:
            values = controls[color_name][0]
            values[channel_index].set(round(float(value)))
            update_color(color_name)

        for color_name, label in self.CUSTOMIZABLE_COLORS:
            color_frame = tk.LabelFrame(
                dialog,
                text=label,
                padx=8,
                pady=4,
                background=palette["background"],
                foreground=palette["foreground"],
            )
            color_frame.pack(fill=tk.X, padx=12, pady=4)
            for column in (1, 2, 3):
                color_frame.columnconfigure(column, weight=1)
            preview = tk.Label(
                color_frame,
                width=6,
                relief=tk.SUNKEN,
                background=palette[color_name],
            )
            preview.grid(row=0, column=0, rowspan=2, padx=(0, 10))
            channels = [
                int(palette[color_name][index:index + 2], 16)
                for index in (1, 3, 5)
            ]
            channel_vars: list[tk.IntVar] = []
            for column, (channel, value) in enumerate(zip(("R", "G", "B"), channels), 1):
                tk.Label(
                    color_frame,
                    text=channel,
                    background=palette["background"],
                    foreground=palette["foreground"],
                ).grid(row=0, column=column, sticky=tk.W)
                value_var = tk.IntVar(value=value)
                scale = tk.Scale(
                    color_frame,
                    from_=0,
                    to=255,
                    orient=tk.HORIZONTAL,
                    resolution=1,
                    showvalue=True,
                    variable=value_var,
                    background=palette["background"],
                    foreground=palette["foreground"],
                    troughcolor=palette["panel"],
                    activebackground=palette["accent_hover"],
                    highlightthickness=0,
                    command=lambda value, name=color_name, index=column - 1: slider_changed(
                        name, index, value
                    ),
                )
                scale.grid(row=1, column=column, sticky=tk.EW, padx=3)
                channel_vars.append(value_var)
            controls[color_name] = (channel_vars, preview)

        buttons = tk.Frame(dialog, background=palette["background"])
        buttons.pack(fill=tk.X, padx=12, pady=10)

        def restore_original() -> None:
            if original_colors:
                self.custom_theme_colors[theme_name] = original_colors
            else:
                self.custom_theme_colors.pop(theme_name, None)
            self._set_theme(theme_name)

        def cancel() -> None:
            restore_original()
            dialog.destroy()

        def reset_defaults() -> None:
            self.custom_theme_colors.pop(theme_name, None)
            for color_name in dict(self.CUSTOMIZABLE_COLORS):
                values = controls[color_name][0]
                for value_var, index in zip(values, (1, 3, 5)):
                    value_var.set(int(self.THEMES[theme_name][color_name][index:index + 2], 16))
                update_color(color_name)
            self.custom_theme_colors.pop(theme_name, None)
            self._set_theme(theme_name)

        def apply() -> None:
            if self._save_settings():
                dialog.destroy()

        tk.Button(
            buttons,
            text="Reset Defaults",
            command=reset_defaults,
            background=palette["surface"],
            foreground=palette["foreground"],
        ).pack(side=tk.LEFT)
        tk.Button(
            buttons,
            text="Cancel",
            command=cancel,
            background=palette["surface"],
            foreground=palette["foreground"],
        ).pack(side=tk.RIGHT, padx=(6, 0))
        tk.Button(
            buttons,
            text="Apply",
            command=apply,
            background=palette["accent"],
            foreground=palette["accent_foreground"],
        ).pack(side=tk.RIGHT)
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        dialog.grab_set()
        dialog.wait_window()

    def _create_widgets(self) -> None:
        self.welcome = tk.Canvas(self.root, bd=0, highlightthickness=0)
        self.welcome.pack(fill=tk.BOTH, expand=True)
        self.welcome_open_folder_button = ttk.Button(
            self.welcome, text="Open Project Folder", command=self.open_folder,
            style="Welcome.TButton",
        )
        self.welcome_open_file_button = ttk.Button(
            self.welcome, text="Open File", command=self.open_file,
            style="Welcome.TButton",
        )
        self.welcome_new_file_button = ttk.Button(
            self.welcome, text="Create New File", command=self.new_file,
            style="Welcome.TButton",
        )
        self.welcome.bind("<Configure>", self._draw_welcome)

        self.workspace = ttk.Frame(self.root)
        toolbar = ttk.Frame(self.workspace, padding=(8, 6))
        toolbar.pack(fill=tk.X)
        ttk.Button(toolbar, text="Open File", command=self.open_file).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="Open Folder", command=self.open_folder).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Save", command=self.save_file).pack(side=tk.LEFT, padx=5)
        self.run_button = ttk.Button(
            toolbar, text="Run ▶", command=self.run_file, style="Accent.TButton"
        )
        self.run_button.pack(side=tk.LEFT, padx=(12, 5))
        self.stop_button = ttk.Button(toolbar, text="Stop ■", command=self.stop_file, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        self.ai_toggle_button = ttk.Button(toolbar, text="AI Assistant", command=self._toggle_ai_panel)
        self.ai_toggle_button.pack(side=tk.LEFT, padx=5)
        ttk.Label(toolbar, text=f"Version {self.VERSION}").pack(
            side=tk.RIGHT, padx=(8, 4)
        )
        self.path_label = ttk.Label(toolbar, text="", anchor=tk.W)
        self.path_label.pack(side=tk.LEFT, padx=12, fill=tk.X, expand=True)

        self.main = ttk.PanedWindow(self.workspace, orient=tk.HORIZONTAL)
        self.main.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self.explorer = ttk.Frame(self.main, width=240)
        explorer = self.explorer
        explorer.columnconfigure(0, weight=1)
        ttk.Label(explorer, text="PROJECT", padding=(6, 5)).grid(
            row=0, column=0, sticky=tk.W
        )
        explorer_actions = ttk.Frame(explorer)
        explorer_actions.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 4))
        ttk.Button(
            explorer_actions, text="New File", command=self.new_project_file
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(
            explorer_actions, text="New Folder", command=self.new_project_folder
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

        self.tree = ttk.Treeview(explorer, show="tree")
        self.tree.grid(row=2, column=0, sticky="nsew")
        tree_scroll = ttk.Scrollbar(explorer, orient=tk.VERTICAL, command=self.tree.yview)
        tree_scroll.grid(row=2, column=1, sticky="ns")
        explorer.rowconfigure(2, weight=1)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.bind("<<TreeviewOpen>>", self._expand_tree_item)
        self.tree.bind("<ButtonRelease-1>", self._tree_click)
        self.tree.bind("<Button-3>", self._tree_context_menu)
        self.tree_menu = tk.Menu(self.root, tearoff=False)
        self.tree_menu.add_command(label="New File", command=self.new_project_file)
        self.tree_menu.add_command(label="New Folder", command=self.new_project_folder)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="Rename", command=self._rename_project_item)
        self.tree_menu.add_command(label="Delete", command=self._delete_project_item)
        self.context_item: str | None = None
        self.main.add(explorer, weight=1)

        work_area = ttk.PanedWindow(self.main, orient=tk.VERTICAL)
        self.main.add(work_area, weight=4)

        editor_frame = ttk.Frame(work_area)
        editor_frame.rowconfigure(0, weight=1)
        editor_frame.columnconfigure(0, weight=1)
        self.editor = tk.Text(
            editor_frame,
            wrap=tk.NONE,
            undo=True,
            font=("Consolas", 11),
            padx=8,
            pady=8,
        )
        self._apply_tab_size()
        self.editor.grid(row=0, column=0, sticky="nsew")
        self.editor.bind("<Tab>", self._insert_tab_spaces)
        editor_y = ttk.Scrollbar(editor_frame, orient=tk.VERTICAL, command=self.editor.yview)
        editor_y.grid(row=0, column=1, sticky="ns")
        editor_x = ttk.Scrollbar(editor_frame, orient=tk.HORIZONTAL, command=self.editor.xview)
        editor_x.grid(row=1, column=0, sticky="ew")
        self.editor.configure(yscrollcommand=editor_y.set, xscrollcommand=editor_x.set)
        self.editor.bind("<<Modified>>", self._editor_modified)
        work_area.add(editor_frame, weight=3)

        output_frame = ttk.Frame(work_area)
        output_frame.rowconfigure(1, weight=1)
        output_frame.columnconfigure(0, weight=1)
        ttk.Label(output_frame, text="TERMINAL", padding=(6, 5)).grid(
            row=0, column=0, sticky=tk.W
        )
        self.output = tk.Text(
            output_frame,
            height=9,
            wrap=tk.NONE,
            state=tk.DISABLED,
            font=("Consolas", 10),
            padx=8,
            pady=6,
        )
        self.output.grid(row=1, column=0, sticky="nsew")
        output_y = ttk.Scrollbar(output_frame, orient=tk.VERTICAL, command=self.output.yview)
        output_y.grid(row=1, column=1, sticky="ns")
        output_x = ttk.Scrollbar(output_frame, orient=tk.HORIZONTAL, command=self.output.xview)
        output_x.grid(row=2, column=0, sticky="ew")
        self.output.configure(yscrollcommand=output_y.set, xscrollcommand=output_x.set)
        terminal_input = ttk.Frame(output_frame, padding=(6, 4))
        terminal_input.grid(row=3, column=0, columnspan=2, sticky="ew")
        terminal_input.columnconfigure(0, weight=1)
        self.stdin_entry = ttk.Entry(terminal_input, state=tk.DISABLED)
        self.stdin_entry.grid(row=0, column=0, sticky="ew")
        self.stdin_entry.bind("<Return>", self._send_terminal_input)
        self.stdin_send_button = ttk.Button(
            terminal_input,
            text="Send",
            command=self._send_terminal_input,
            state=tk.DISABLED,
        )
        self.stdin_send_button.grid(row=0, column=1, padx=(5, 0))
        work_area.add(output_frame, weight=1)

        self.ai_panel = ttk.Frame(self.main, width=340, padding=8)
        self.ai_panel.columnconfigure(0, weight=1)
        self.ai_panel.rowconfigure(5, weight=1)
        ai_header = ttk.Frame(self.ai_panel)
        ai_header.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ai_header.columnconfigure(0, weight=1)
        ttk.Label(ai_header, text="AI ASSISTANT").grid(row=0, column=0, sticky=tk.W)
        ttk.Button(ai_header, text="Close", command=self._toggle_ai_panel).grid(row=0, column=1)

        model_row = ttk.Frame(self.ai_panel)
        model_row.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        model_row.columnconfigure(0, weight=1)
        self.ai_model_box = ttk.Combobox(
            model_row, textvariable=self.ai_model_var, values=(), width=22
        )
        self.ai_model_box.grid(row=0, column=0, sticky="ew")
        ttk.Button(model_row, text="Refresh", command=self._refresh_ai_models).grid(
            row=0, column=1, padx=(4, 0)
        )
        self.ai_pull_button = ttk.Button(model_row, text="Pull Model", command=self._pull_ai_model)
        self.ai_pull_button.grid(
            row=0, column=2, padx=(4, 0)
        )
        ttk.Label(
            self.ai_panel,
            textvariable=self.ai_status,
            wraplength=310,
            justify=tk.LEFT,
        ).grid(row=2, column=0, sticky="ew", pady=(0, 6))

        ai_actions = ttk.Frame(self.ai_panel)
        ai_actions.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        self.ai_complete_button = ttk.Button(
            ai_actions, text="Complete (Ctrl+Space)", command=self._request_completion
        )
        self.ai_complete_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(
            ai_actions, text="Explain Last Run", command=self._explain_last_run
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

        self.ai_edit_button = ttk.Button(
            self.ai_panel,
            text="Edit Open Script with AI",
            command=self._request_script_edit,
        )
        self.ai_edit_button.grid(row=4, column=0, sticky="ew", pady=(0, 6))

        self.ai_chat = tk.Text(
            self.ai_panel, wrap=tk.WORD, state=tk.DISABLED, font=("Segoe UI", 10), padx=7, pady=7
        )
        self.ai_chat.grid(row=5, column=0, sticky="nsew")
        ai_chat_scroll = ttk.Scrollbar(self.ai_panel, orient=tk.VERTICAL, command=self.ai_chat.yview)
        ai_chat_scroll.grid(row=5, column=1, sticky="ns")
        self.ai_chat.configure(yscrollcommand=ai_chat_scroll.set)
        ai_prompt_row = ttk.Frame(self.ai_panel)
        ai_prompt_row.grid(row=6, column=0, sticky="ew")
        ai_prompt_row.columnconfigure(0, weight=1)
        self.ai_apply_edits_check = ttk.Checkbutton(
            ai_prompt_row,
            text="Apply code changes to the open file",
            variable=self.ai_apply_edits_var,
        )
        self.ai_apply_edits_check.grid(row=0, column=0, columnspan=2, sticky=tk.W)
        self.ai_prompt_entry = ttk.Entry(ai_prompt_row)
        self.ai_prompt_entry.grid(row=1, column=0, sticky="ew")
        self.ai_prompt_entry.bind("<Return>", self._submit_ai_prompt)
        self.ai_send_button = ttk.Button(
            ai_prompt_row, text="Send", command=self._submit_ai_prompt, style="Accent.TButton"
        )
        self.ai_send_button.grid(
            row=1, column=1, padx=(5, 0)
        )
        self.editor.bind("<Control-space>", self._completion_shortcut)

        self.status = tk.StringVar(value="Ready")
        self.save_state = tk.StringVar(value="Not saved")
        status_bar = ttk.Frame(self.workspace, relief=tk.SUNKEN)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Label(status_bar, textvariable=self.status, anchor=tk.W).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=4
        )
        ttk.Label(status_bar, textvariable=self.save_state, anchor=tk.E, padding=(8, 0)).pack(
            side=tk.RIGHT
        )

    def _set_title(self) -> None:
        name = self.current_file.name if self.current_file else "Untitled"
        marker = " *" if self.dirty else ""
        self.root.title(f"{name}{marker} - GRAVEL")
        self.path_label.config(
            text=str(self.current_file or self.project_folder or "No folder selected")
        )
        if self.dirty and self.current_file is None and self.project_folder is None:
            self.save_state.set("Unsaved — save to choose a location")
        elif self.dirty:
            self.save_state.set("Unsaved changes")
        elif self.current_file is None:
            self.save_state.set("Not saved")
        else:
            self.save_state.set("Saved")

    def _add_recent_path(self, path: Path | None) -> None:
        if path is None:
            return
        normalized = str(path.resolve())
        self.recent_paths = [item for item in self.recent_paths if item != normalized]
        self.recent_paths.insert(0, normalized)
        self.recent_paths = self.recent_paths[:8]
        self._save_settings()
        self._refresh_recent_menu()

    def _refresh_recent_menu(self) -> None:
        if not hasattr(self, "recent_menu"):
            return
        self.recent_menu.delete(0, tk.END)
        if not self.recent_paths:
            self.recent_menu.add_command(label="No recent files", state=tk.DISABLED)
            return
        for recent_path in self.recent_paths:
            file_path = Path(recent_path)
            if not file_path.exists():
                continue
            self.recent_menu.add_command(
                label=file_path.name,
                command=lambda path=recent_path: self._open_recent_file(path),
            )

    def _open_recent_file(self, path: str) -> None:
        file_path = Path(path)
        if file_path.exists():
            self._load_file(file_path)
        else:
            self.recent_paths = [item for item in self.recent_paths if item != path]
            self._save_settings()
            self._refresh_recent_menu()

    def _apply_tab_size(self) -> None:
        space_width = tkfont.Font(
            root=self.root, font=self.editor.cget("font")
        ).measure(" " * self.tab_size_var.get())
        self.editor.configure(tabs=(space_width,))

    def _insert_tab_spaces(self, _event: tk.Event) -> str:
        self.editor.insert(tk.INSERT, " " * self.tab_size_var.get())
        return "break"

    def _open_file_shortcut(self, _event: tk.Event) -> str:
        self.open_file()
        return "break"

    def _open_folder_shortcut(self, _event: tk.Event) -> str:
        self.open_folder()
        return "break"

    def _save_shortcut(self, _event: tk.Event) -> str:
        self.save_file()
        return "break"

    def _new_file_shortcut(self, _event: tk.Event) -> str:
        self.new_file()
        return "break"

    def _run_shortcut(self, _event: tk.Event) -> str:
        self.run_file()
        return "break"

    def _editor_modified(self, _event: tk.Event) -> None:
        if self.editor.edit_modified():
            self.dirty = True
            self._set_title()
            self.editor.edit_modified(False)
            self._schedule_syntax_highlighting()
            if self._autosave_after_id is not None:
                self.root.after_cancel(self._autosave_after_id)
            self._autosave_after_id = self.root.after(500, self._autosave)

    def _autosave(self) -> None:
        self._autosave_after_id = None
        if self.dirty and (self.current_file is not None or self.project_folder is not None):
            self.save_file()

    def _set_editor_text(self, text: str) -> None:
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", text)
        self.editor.edit_modified(False)
        self._highlight_syntax()
        self.dirty = False
        self._set_title()

    def _set_theme(self, theme_name: str) -> None:
        palette = {
            **self.THEMES[theme_name],
            **self.custom_theme_colors.get(theme_name, {}),
        }
        self.theme_var.set(theme_name)
        self.root.configure(background=palette["background"])

        style = ttk.Style(self.root)
        if style.theme_use() != "clam":
            style.theme_use("clam")
        style.configure(
            ".",
            background=palette["background"],
            foreground=palette["foreground"],
            fieldbackground=palette["field"],
            bordercolor=palette["border"],
            focuscolor=palette["accent"],
            lightcolor=palette["surface"],
            darkcolor=palette["border"],
            troughcolor=palette["field"],
            insertcolor=palette["foreground"],
        )
        style.configure("TFrame", background=palette["background"])
        style.configure(
            "TLabel",
            background=palette["background"],
            foreground=palette["foreground"],
        )
        style.configure(
            "TButton",
            background=palette["surface"],
            foreground=palette["foreground"],
            bordercolor=palette["border"],
            focusthickness=1,
            padding=(8, 4),
        )
        style.map(
            "TButton",
            background=[
                ("disabled", palette["background"]),
                ("pressed", palette["accent"]),
                ("active", palette["accent"]),
            ],
            foreground=[
                ("disabled", palette["muted"]),
                ("pressed", palette["accent_foreground"]),
                ("active", palette["accent_foreground"]),
            ],
        )
        style.configure(
            "Accent.TButton",
            background=palette["accent"],
            foreground=palette["accent_foreground"],
            bordercolor=palette["accent"],
        )
        style.map(
            "Accent.TButton",
            background=[
                ("disabled", palette["surface"]),
                ("pressed", palette["accent_hover"]),
                ("active", palette["accent_hover"]),
            ],
            foreground=[
                ("disabled", palette["muted"]),
                ("pressed", palette["accent_foreground"]),
                ("active", palette["accent_foreground"]),
            ],
        )
        style.configure(
            "TEntry",
            fieldbackground=palette["field"],
            foreground=palette["foreground"],
            bordercolor=palette["border"],
            insertcolor=palette["foreground"],
        )
        style.map(
            "TEntry",
            fieldbackground=[("disabled", palette["panel"]), ("readonly", palette["field"])],
            foreground=[("disabled", palette["muted"])],
            bordercolor=[("focus", palette["accent"])],
        )
        style.configure(
            "TCombobox",
            fieldbackground=palette["field"],
            background=palette["surface"],
            foreground=palette["foreground"],
            arrowcolor=palette["foreground"],
            bordercolor=palette["border"],
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", palette["field"]), ("disabled", palette["panel"])],
            foreground=[("disabled", palette["muted"])],
            selectbackground=[("readonly", palette["selection"])],
            selectforeground=[("readonly", palette["foreground"])],
            bordercolor=[("focus", palette["accent"])],
        )
        style.configure(
            "TCheckbutton",
            background=palette["background"],
            foreground=palette["foreground"],
            indicatorcolor=palette["field"],
        )
        style.map(
            "TCheckbutton",
            background=[("active", palette["background"])],
            foreground=[("disabled", palette["muted"])],
            indicatorcolor=[
                ("selected", palette["accent"]),
                ("active", palette["surface"]),
            ],
        )
        style.configure(
            "Treeview",
            background=palette["field"],
            fieldbackground=palette["field"],
            foreground=palette["foreground"],
            bordercolor=palette["border"],
            rowheight=24,
        )
        style.map(
            "Treeview",
            background=[("selected", palette["accent"])],
            foreground=[("selected", palette["accent_foreground"])],
        )
        style.configure(
            "Treeview.Heading",
            background=palette["surface"],
            foreground=palette["foreground"],
            bordercolor=palette["border"],
        )
        style.map(
            "Treeview.Heading",
            background=[("active", palette["accent"])],
            foreground=[("active", palette["accent_foreground"])],
        )

        style.configure(
            "Explorer.TFrame",
            background=palette["panel"],
        )
        self.explorer.configure(style="Explorer.TFrame")
        style.configure(
            "TScrollbar",
            background=palette["surface"],
            troughcolor=palette["background"],
            bordercolor=palette["background"],
            arrowcolor=palette["foreground"],
        )
        style.map(
            "TScrollbar",
            background=[("active", palette["accent"])],
        )
        style.configure("TPanedwindow", background=palette["border"])
        style.configure("Sash", background=palette["border"])
        style.configure(
            "Welcome.TButton",
            background="#286be8",
            foreground="#ffffff",
            bordercolor="#286be8",
            padding=(16, 9),
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "Welcome.TButton",
            background=[("pressed", "#174caf"), ("active", "#174caf")],
            foreground=[("pressed", "#ffffff"), ("active", "#ffffff")],
        )

        for menu in (self.menu, self.tree_menu):
            menu.configure(
                background=palette["surface"],
                foreground=palette["foreground"],
                activebackground=palette["accent"],
                activeforeground=palette["accent_foreground"],
                disabledforeground=palette["muted"],
                selectcolor=palette["accent"],
                borderwidth=1,
            )
        for widget in (self.editor, self.output, self.ai_chat):
            widget.configure(
                background=palette["field"],
                foreground=palette["foreground"],
                insertbackground=palette["foreground"],
                selectbackground=palette["accent"],
                selectforeground=palette["accent_foreground"],
                highlightbackground=palette["border"],
                highlightcolor=palette["accent"],
            )
        self.editor.configure(background=palette["background"], selectbackground=palette["selection"])
        self.root.option_add("*TCombobox*Listbox.background", palette["field"])
        self.root.option_add("*TCombobox*Listbox.foreground", palette["foreground"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", palette["accent"])
        self.root.option_add(
            "*TCombobox*Listbox.selectForeground", palette["accent_foreground"]
        )
        for tag in self.SYNTAX_TAGS:
            self.editor.tag_configure(f"syntax_{tag}", foreground=palette[tag])
        self._highlight_syntax()

    def _draw_welcome(self, event: tk.Event) -> None:
        width = event.width
        height = event.height
        if width <= 1 or height <= 1:
            return

        self.welcome.delete("welcome_background", "welcome_content")
        top_color = (255, 255, 255)
        middle_color = (232, 250, 255)
        bottom_color = (91, 139, 255)
        band_height = max(1, height // 120)
        for y in range(0, height, band_height):
            progress = y / max(1, height - 1)
            if progress < 0.42:
                start, end = top_color, middle_color
                blend = progress / 0.42
            else:
                start, end = middle_color, bottom_color
                blend = (progress - 0.42) / 0.58
            color = "#" + "".join(
                f"{round(first + (last - first) * blend):02x}"
                for first, last in zip(start, end)
            )
            self.welcome.create_rectangle(
                0, y, width, y + band_height, fill=color, outline=color,
                tags="welcome_background",
            )

        self.welcome.create_text(
            width - 16,
            14,
            anchor=tk.NE,
            text=f"Version {self.VERSION}",
            fill="#405a78",
            font=("Segoe UI", 9),
            tags="welcome_content",
        )
        logo = (
            self.welcome_logo_large
            if height >= self.welcome_logo_large.height() + 100
            else self.welcome_logo_small
        )
        title_height = 34
        subtitle_height = 24
        button_height = max(
            self.welcome_open_folder_button.winfo_reqheight(),
            self.welcome_open_file_button.winfo_reqheight(),
            self.welcome_new_file_button.winfo_reqheight(),
        )
        content_height = (
            logo.height()
            + 18
            + title_height
            + 8
            + subtitle_height
            + 20
            + button_height
        )
        top = max(12, (height - content_height) // 2)
        self.welcome.create_image(
            width // 2,
            top + logo.height() // 2,
            image=logo,
            tags="welcome_content",
        )
        title_y = top + logo.height() + 18
        self.welcome.create_text(
            width // 2,
            title_y + title_height // 2,
            text="Welcome to GRAVEL",
            fill="#202124",
            font=("Segoe UI", 20, "bold"),
            tags="welcome_content",
        )
        subtitle_y = title_y + title_height + 8
        self.welcome.create_text(
            width // 2,
            subtitle_y + subtitle_height // 2,
            text="Open a project or file, or create a new file to get started.",
            fill="#405a78",
            font=("Segoe UI", 10),
            tags="welcome_content",
        )
        buttons_y = subtitle_y + subtitle_height + 20
        self.welcome.create_window(
            width // 2 - 170,
            buttons_y + button_height // 2,
            window=self.welcome_open_folder_button,
            width=160,
            tags="welcome_content",
        )
        self.welcome.create_window(
            width // 2,
            buttons_y + button_height // 2,
            window=self.welcome_open_file_button,
            width=140,
            tags="welcome_content",
        )
        self.welcome.create_window(
            width // 2 + 165,
            buttons_y + button_height // 2,
            window=self.welcome_new_file_button,
            width=160,
            tags="welcome_content",
        )

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
        self.ai_chat.configure(state=tk.NORMAL)
        self.ai_chat.insert(tk.END, f"{speaker}:\n{message.strip()}\n\n")
        self.ai_chat.see(tk.END)
        self.ai_chat.configure(state=tk.DISABLED)

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
            "You are a helpful Python coding assistant. Answer clearly and provide code when useful.\n"
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
        output = self.last_run_output[-12000:].strip()
        if not output:
            self._append_ai_message("Assistant", "There is no captured run output to explain yet. Run a file first.")
            return
        code = self.editor.get("1.0", "end-1c")[-8000:]
        self._append_ai_message("You", "Explain the last run output")
        prompt = (
            "Explain the program output or error below. Identify the likely cause and give a concise fix. "
            "Do not change the code automatically.\n\n"
            f"Open Python code:\n```python\n{code}\n```\n\n"
            f"Last run output:\n```text\n{output}\n```"
        )
        self._request_ai(prompt, "explanation")

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

        def generate() -> None:
            result = None
            error_message = None
            try:
                payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
                request = urllib.request.Request(
                    "http://localhost:11434/api/generate",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=180) as response:
                    result = json.load(response).get("response", "").strip()
            except urllib.error.HTTPError as error:
                try:
                    details = json.loads(error.read().decode("utf-8")).get("error", str(error))
                except (UnicodeError, json.JSONDecodeError):
                    details = str(error)
                error_message = f"HTTP {error.code}: {details}"
            except Exception as error:
                error_message = str(error)
            self.root.after(0, lambda: self._finish_ai_request(action, result, error_message))

        threading.Thread(target=generate, daemon=True).start()

    def _finish_ai_request(self, action: str, result: str | None, error: str | None) -> None:
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
                self._append_ai_message("Assistant", answer)
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
        self._append_ai_message("Assistant", answer)

    def _schedule_syntax_highlighting(self) -> None:
        if self._syntax_after_id is not None:
            self.root.after_cancel(self._syntax_after_id)
        self._syntax_after_id = self.root.after(120, self._highlight_syntax)

    def _highlight_syntax(self) -> None:
        self._syntax_after_id = None
        for tag in self.SYNTAX_TAGS:
            self.editor.tag_remove(f"syntax_{tag}", "1.0", tk.END)

        if self.current_file is not None and self.current_file.suffix.lower() != ".py":
            return

        source = self.editor.get("1.0", "end-1c")
        try:
            for item in tokenize.generate_tokens(io.StringIO(source).readline):
                category = None
                if item.type == token.NAME:
                    if item.string in {"True", "False", "None"}:
                        category = "constant"
                    elif keyword.iskeyword(item.string):
                        category = "keyword"
                elif item.type == token.STRING:
                    category = "string"
                elif item.type == token.COMMENT:
                    category = "comment"
                elif item.type == token.NUMBER:
                    category = "number"
                elif item.type == token.OP:
                    category = "operator"

                if category is not None:
                    start = f"{item.start[0]}.{item.start[1]}"
                    end = f"{item.end[0]}.{item.end[1]}"
                    self.editor.tag_add(f"syntax_{category}", start, end)
        except (IndentationError, SyntaxError, tokenize.TokenError):
            pass

    def _save_pending_changes(self) -> bool:
        if self._autosave_after_id is not None:
            self.root.after_cancel(self._autosave_after_id)
            self._autosave_after_id = None
        if not self.dirty:
            return True
        if self.current_file is None and self.project_folder is None:
            should_save = messagebox.askyesnocancel(
                "Unsaved Changes",
                "Save this new file before continuing?",
                parent=self.root,
            )
            if should_save is None:
                return False
            return self.save_file_as() if should_save else True
        return self.save_file()

    def new_file(self) -> None:
        if not self._save_pending_changes():
            return
        self.current_file = None
        self._set_editor_text("")
        self.welcome.pack_forget()
        self.workspace.pack(fill=tk.BOTH, expand=True)
        self.status.set("New file — start typing, then save to choose a location")
        self.editor.focus_set()

    def _file_picker_palette(self) -> dict[str, str]:
        theme_name = self.theme_var.get()
        return {
            **self.THEMES[theme_name],
            **self.custom_theme_colors.get(theme_name, {}),
        }

    def _desktop_path(self) -> Path:
        candidates = (
            Path.home() / "OneDrive" / "Desktop",
            Path.home() / "Desktop",
        )
        return next((path for path in candidates if path.is_dir()), Path.home())

    def _show_file_picker(
        self,
        title: str,
        mode: str,
        initial_dir: Path | None = None,
        default_name: str = "",
    ) -> str | None:
        palette = self._file_picker_palette()
        start_dir = initial_dir or self._desktop_path()
        current_dir = start_dir if start_dir.is_dir() else Path.home()
        result: str | None = None

        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.configure(background=palette["background"])
        dialog.geometry("920x600")
        dialog.minsize(680, 430)
        dialog.grab_set()

        style = ttk.Style(dialog)
        style.configure(
            "Picker.Treeview",
            background=palette["field"],
            fieldbackground=palette["field"],
            foreground=palette["foreground"],
            rowheight=27,
            bordercolor=palette["border"],
            font=("Consolas", 10),
        )
        style.map(
            "Picker.Treeview",
            background=[("selected", palette["accent"])],
            foreground=[("selected", palette["accent_foreground"])],
        )
        style.configure(
            "Picker.Treeview.Heading",
            background=palette["surface"],
            foreground=palette["foreground"],
            font=("Consolas", 9, "bold"),
            relief=tk.RAISED,
        )
        style.map(
            "Picker.Treeview.Heading",
            background=[("active", palette["accent"])],
            foreground=[("active", palette["accent_foreground"])],
        )
        style.configure("Picker.TButton", font=("Consolas", 9, "bold"), padding=(8, 5))

        outer = ttk.Frame(dialog, padding=8)
        outer.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        toolbar = ttk.Frame(outer)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(
            toolbar, text="<", style="Picker.TButton", command=lambda: go_back()
        ).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(
            toolbar,
            text="UP",
            style="Picker.TButton",
            command=lambda: navigate(current_dir.parent),
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(
            toolbar,
            text="REFRESH",
            style="Picker.TButton",
            command=lambda: refresh_listing(current_dir),
        ).pack(side=tk.LEFT, padx=4)
        ttk.Label(toolbar, text="LOCATION").pack(side=tk.LEFT, padx=(12, 6))
        location_var = tk.StringVar(value=str(current_dir))
        location_entry = ttk.Entry(toolbar, textvariable=location_var)
        location_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Label(toolbar, text="SEARCH").pack(side=tk.LEFT, padx=(0, 6))
        search_var = tk.StringVar()
        search_entry = ttk.Entry(toolbar, textvariable=search_var, width=20)
        search_entry.pack(side=tk.LEFT)

        body = ttk.Frame(outer)
        body.pack(fill=tk.BOTH, expand=True)
        sidebar = ttk.Frame(body, padding=(4, 4), width=165)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        sidebar.pack_propagate(False)
        ttk.Label(sidebar, text="QUICK ACCESS").pack(anchor=tk.W, padx=6, pady=(4, 8))
        desktop = self._desktop_path()
        shortcuts = [
            ("Home", Path.home()),
            ("Desktop", desktop),
            ("Downloads", Path.home() / "Downloads"),
            ("Documents", Path.home() / "Documents"),
            ("This PC", Path(Path.home().anchor)),
        ]
        for label, shortcut_path in shortcuts:
            ttk.Button(
                sidebar,
                text=f"  {label}",
                style="Picker.TButton",
                command=lambda target=shortcut_path: navigate(target),
            ).pack(fill=tk.X, pady=2)
        ttk.Separator(sidebar, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        ttk.Label(
            sidebar,
            text="GRAVEL\nPIXEL PICKER",
            justify=tk.LEFT,
            foreground=palette["muted"],
            font=("Consolas", 9, "bold"),
        ).pack(anchor=tk.W, padx=6)

        content = ttk.Frame(body)
        content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        content.rowconfigure(1, weight=1)
        content.columnconfigure(0, weight=1)
        ttk.Label(content, text="FILES", padding=(8, 6)).grid(
            row=0, column=0, sticky="ew"
        )
        listing = ttk.Treeview(
            content,
            columns=("type", "size"),
            show="tree headings",
            selectmode="browse",
            style="Picker.Treeview",
        )
        listing.heading("#0", text="Name", anchor=tk.W)
        listing.heading("type", text="Type", anchor=tk.W)
        listing.heading("size", text="Size", anchor=tk.E)
        listing.column("#0", width=360, minwidth=160, stretch=True)
        listing.column("type", width=100, minwidth=70, stretch=False)
        listing.column("size", width=90, minwidth=60, stretch=False, anchor=tk.E)
        listing.grid(row=1, column=0, sticky="nsew")
        listing_scroll = ttk.Scrollbar(
            content, orient=tk.VERTICAL, command=listing.yview
        )
        listing_scroll.grid(row=1, column=1, sticky="ns")
        listing.configure(yscrollcommand=listing_scroll.set)
        entries_by_item: dict[str, Path] = {}
        history: list[Path] = []
        status_var = tk.StringVar()
        ttk.Label(outer, textvariable=status_var, anchor=tk.W, padding=(6, 5)).pack(
            fill=tk.X
        )

        filter_var = tk.StringVar(value=self.SUPPORTED_FILETYPES[0][0])
        filter_patterns = {
            label: patterns.split()
            for label, patterns in self.SUPPORTED_FILETYPES
        }
        if mode == "open_file":
            filter_box = ttk.Combobox(
                toolbar,
                textvariable=filter_var,
                values=tuple(filter_patterns),
                state="readonly",
                width=20,
            )
            filter_box.pack(side=tk.RIGHT, padx=(8, 0))

        filename_var = tk.StringVar(value=default_name)
        if mode == "save":
            filename_row = ttk.Frame(outer)
            filename_row.pack(fill=tk.X, pady=(5, 0))
            ttk.Label(filename_row, text="File name:").pack(side=tk.LEFT, padx=(0, 8))
            filename_entry = ttk.Entry(filename_row, textvariable=filename_var)
            filename_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        def refresh_listing(directory: Path) -> None:
            nonlocal current_dir
            try:
                entries = sorted(
                    directory.iterdir(),
                    key=lambda entry: (not entry.is_dir(), entry.name.casefold()),
                )
            except OSError as error:
                status_var.set(f"Cannot read folder: {error}")
                return

            current_dir = directory
            listing.delete(*listing.get_children())
            entries_by_item.clear()

            patterns = filter_patterns.get(filter_var.get(), ["*"])
            search_text = search_var.get().strip().casefold()
            if search_text == "search this folder":
                search_text = ""
            for entry in entries:
                try:
                    is_dir = entry.is_dir()
                except OSError:
                    continue
                if mode == "open_folder" and not is_dir:
                    continue
                if search_text and search_text not in entry.name.casefold():
                    continue
                if mode == "open_file" and not is_dir and not any(
                    fnmatch.fnmatchcase(entry.name.casefold(), pattern.casefold())
                    for pattern in patterns
                ):
                    continue
                item_type = "Folder" if is_dir else f"{entry.suffix[1:].upper() or 'File'} file"
                try:
                    size = "" if is_dir else f"{entry.stat().st_size:,} B"
                except OSError:
                    size = ""
                item = listing.insert(
                    "",
                    tk.END,
                    text=f"[+] {entry.name}" if is_dir else entry.name,
                    values=(item_type, size),
                )
                entries_by_item[item] = entry
            location_var.set(str(directory))
            status_var.set(f"{len(entries_by_item)} items   |   {directory}")

        def navigate(directory: Path) -> None:
            if not directory.is_dir():
                status_var.set(f"Folder not found: {directory}")
                return
            if directory != current_dir:
                history.append(current_dir)
            refresh_listing(directory)

        def go_back() -> None:
            if history:
                refresh_listing(history.pop())

        def navigate_to_location(_event: tk.Event | None = None) -> None:
            candidate = Path(location_var.get().strip()).expanduser()
            if not candidate.is_dir():
                status_var.set("That location is not a folder.")
                return
            navigate(candidate)

        def selected_path() -> Path | None:
            selected = listing.selection()
            if not selected:
                return None
            return entries_by_item.get(selected[0])

        def activate_selection(_event: tk.Event | None = None) -> None:
            nonlocal result
            path = selected_path()
            if path is None:
                return
            if path.is_dir():
                refresh_listing(path)
            elif mode == "open_file" and path.is_file():
                result = str(path)
                dialog.destroy()
            elif mode == "save":
                filename_var.set(path.name)

        def choose_folder() -> None:
            nonlocal result
            result = str(current_dir)
            dialog.destroy()

        def accept() -> None:
            nonlocal result
            if mode == "open_folder":
                choose_folder()
                return
            if mode == "open_file":
                path = selected_path()
                if path is None or not path.is_file():
                    status_var.set("Select a file to open.")
                    return
                result = str(path)
                dialog.destroy()
                return

            name = filename_var.get().strip()
            if not name or name in {".", ".."} or Path(name).name != name:
                status_var.set("Enter a valid file name.")
                return
            path = current_dir / name
            if path.exists() and not messagebox.askyesno(
                "Replace File",
                f"{path.name} already exists. Replace it?",
                parent=dialog,
            ):
                return
            result = str(path)
            dialog.destroy()

        def select_item(_event: tk.Event | None = None) -> None:
            path = selected_path()
            if mode == "save" and path is not None and path.is_file():
                filename_var.set(path.name)

        listing.bind("<Double-Button-1>", activate_selection)
        listing.bind("<Return>", activate_selection)
        listing.bind("<<TreeviewSelect>>", select_item)
        location_entry.bind("<Return>", navigate_to_location)
        search_var.trace_add("write", lambda *_args: refresh_listing(current_dir))
        if mode == "open_file":
            filter_var.trace_add(
                "write", lambda *_args: refresh_listing(current_dir)
            )
        refresh_listing(current_dir)

        button_row = ttk.Frame(outer)
        button_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(
            button_row,
            text="OPEN" if mode == "open_file" else "SAVE" if mode == "save" else "USE FOLDER",
            command=accept,
            style="Accent.TButton",
        ).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(
            button_row, text="CANCEL", command=dialog.destroy, style="Picker.TButton"
        ).pack(side=tk.RIGHT)

        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        if mode == "open_file":
            listing.focus_set()
        elif mode == "save":
            filename_entry.focus_set()
        dialog.wait_window()
        return result

    def open_file(self) -> None:
        if not self._save_pending_changes():
            return
        filename = self._show_file_picker(
            "Open File",
            mode="open_file",
        )
        if filename:
            self._load_file(Path(filename))

    def _load_file(self, path: Path) -> None:
        try:
            with tokenize.open(path) as source:
                text = source.read()
        except (OSError, SyntaxError, UnicodeError) as error:
            messagebox.showerror("Could Not Open File", str(error), parent=self.root)
            return
        if self.project_folder is None:
            self._set_project_folder(path.parent)
        self.current_file = path
        self._add_recent_path(path)
        self._set_editor_text(text)
        self.status.set(f"Opened {path}")

    def open_folder(self) -> None:
        if not self._save_pending_changes():
            return
        folder = self._show_file_picker(
            "Open Project Folder",
            mode="open_folder",
        )
        if folder:
            self._set_project_folder(Path(folder))

    def _set_project_folder(self, folder: Path) -> None:
        self.project_folder = folder
        self.tree.delete(*self.tree.get_children())
        root_item = self.tree.insert("", tk.END, text=folder.name or str(folder), values=(str(folder),))
        self._add_folder_placeholder(root_item, folder)
        self.tree.item(root_item, open=True)
        self._populate_folder(root_item, folder)
        self.welcome.pack_forget()
        self.workspace.pack(fill=tk.BOTH, expand=True)
        if self.tree.get_children(root_item):
            self.status.set(f"Project: {folder}")
        else:
            self.status.set("Empty project — use New File or New Folder to get started")
        self._set_title()

    def _add_folder_placeholder(self, item: str, folder: Path) -> None:
        try:
            has_children = any(folder.iterdir())
        except OSError:
            has_children = False
        if has_children:
            self.tree.insert(item, tk.END, text="…", values=("__placeholder__",))

    def _populate_folder_item(self, item: str, folder: Path) -> bool:
        children = self.tree.get_children(item)
        if children:
            child_values = self.tree.item(children[0], "values")
            if not child_values or child_values[0] != "__placeholder__":
                return True
            self.tree.delete(*children)
        return self._populate_folder(item, folder)

    def _refresh_folder_item(self, item: str, folder: Path) -> bool:
        self.tree.delete(*self.tree.get_children(item))
        return self._populate_folder(item, folder)

    def _populate_folder(self, item: str, folder: Path) -> bool:
        try:
            entries = sorted(folder.iterdir(), key=lambda entry: (not entry.is_dir(), entry.name.lower()))
        except OSError as error:
            self.status.set(f"Cannot read folder {folder}: {error}")
            return False
        for entry in entries:
            try:
                is_folder = entry.is_dir()
            except OSError:
                continue
            icon_name = None if is_folder else self.FILE_ICONS.get(entry.suffix.lower())
            child = self.tree.insert(
                item,
                tk.END,
                text=entry.name,
                image=self.file_icon_images.get(icon_name) if icon_name else "",
                values=(str(entry),),
            )
            if is_folder:
                self._add_folder_placeholder(child, entry)
        return True

    def _expand_tree_item(self, _event: tk.Event) -> None:
        item = self.tree.focus()
        values = self.tree.item(item, "values")
        if values:
            self._populate_folder_item(item, Path(values[0]))

    def _tree_click(self, event: tk.Event) -> None:
        item = self.tree.identify_row(event.y)
        if not item:
            return
        element = self.tree.identify_element(event.x, event.y)
        self.root.after_idle(lambda: self._activate_tree_item(item, element))

    def _activate_tree_item(self, item: str, element: str) -> None:
        if not self.tree.exists(item):
            return
        values = self.tree.item(item, "values")
        if not values or values[0] == "__placeholder__":
            return
        path = Path(values[0])
        if path.is_file():
            if self._save_pending_changes():
                self._load_file(path)
        elif path.is_dir():
            if element != "Treeitem.indicator":
                self.tree.item(item, open=not self.tree.item(item, "open"))
            if self.tree.item(item, "open"):
                self._populate_folder_item(item, path)

    def _tree_context_menu(self, event: tk.Event) -> None:
        item = self.tree.identify_row(event.y)
        self.context_item = item or None
        if item:
            self.tree.selection_set(item)
            self.tree.focus(item)
        is_project_root = bool(item and not self.tree.parent(item))
        self.tree_menu.entryconfigure("Rename", state=tk.NORMAL if item else tk.DISABLED)
        self.tree_menu.entryconfigure(
            "Delete",
            state=tk.NORMAL if item and not is_project_root else tk.DISABLED,
        )
        try:
            self.tree_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.tree_menu.grab_release()

    def _context_path(self) -> tuple[str, Path] | None:
        item = self.context_item
        if not item or not self.tree.exists(item):
            return None
        values = self.tree.item(item, "values")
        if not values or values[0] == "__placeholder__":
            return None
        return item, Path(values[0])

    def _refresh_parent_after_change(self, item: str, parent_folder: Path) -> bool:
        parent_item = self.tree.parent(item)
        if not parent_item:
            self._set_project_folder(parent_folder)
            return True
        return self._refresh_folder_item(parent_item, parent_folder)

    def _rename_project_item(self) -> None:
        context = self._context_path()
        if context is None:
            return
        item, path = context
        if not self._save_pending_changes():
            return
        new_name = simpledialog.askstring(
            "Rename",
            "Enter a new name:",
            initialvalue=path.name,
            parent=self.root,
        )
        if new_name is None:
            return
        new_name = new_name.strip()
        if (
            not new_name
            or new_name in {".", ".."}
            or "/" in new_name
            or "\\" in new_name
        ):
            messagebox.showerror(
                "Invalid Name",
                "Enter a valid name without folder separators.",
                parent=self.root,
            )
            return
        new_path = path.with_name(new_name)
        if new_path == path:
            return
        if new_path.exists():
            messagebox.showerror(
                "Cannot Rename",
                f"An item named {new_name!r} already exists.",
                parent=self.root,
            )
            return

        parent_folder = path.parent
        try:
            path.rename(new_path)
        except OSError as error:
            messagebox.showerror("Cannot Rename", str(error), parent=self.root)
            return

        if self.current_file is not None:
            try:
                relative_file = self.current_file.relative_to(path)
            except ValueError:
                pass
            else:
                self.current_file = new_path / relative_file
        if self.project_folder == path:
            self.project_folder = new_path

        parent_item = self.tree.parent(item)
        if not parent_item:
            self._set_project_folder(new_path)
        else:
            refreshed = self._refresh_folder_item(parent_item, parent_folder)
            if refreshed:
                for child in self.tree.get_children(parent_item):
                    values = self.tree.item(child, "values")
                    if values and Path(values[0]) == new_path:
                        self.tree.selection_set(child)
                        self.tree.focus(child)
                        self.tree.see(child)
                        break
        self._set_title()
        self.status.set(f"Renamed {path.name} to {new_name}")

    def _delete_project_item(self) -> None:
        context = self._context_path()
        if context is None:
            return
        item, path = context
        if not self.tree.parent(item):
            return
        if not self._save_pending_changes():
            return

        is_directory = path.is_dir()
        description = (
            f"Delete the folder {path.name!r} and all its contents?"
            if is_directory
            else f"Delete the file {path.name!r}?"
        )
        if not messagebox.askyesno("Confirm Delete", description, parent=self.root):
            return

        parent_folder = path.parent
        try:
            if is_directory:
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError as error:
            messagebox.showerror("Cannot Delete", str(error), parent=self.root)
            return

        if self.current_file is not None:
            try:
                self.current_file.relative_to(path)
            except ValueError:
                pass
            else:
                self.current_file = None
                self._set_editor_text("")
        refreshed = self._refresh_parent_after_change(item, parent_folder)
        self._set_title()
        if refreshed:
            self.status.set(f"Deleted {path}")

    def _project_creation_location(self) -> tuple[str, Path] | None:
        selection = self.tree.selection()
        root_items = self.tree.get_children("")
        if not selection and not root_items:
            return None
        item = selection[0] if selection else root_items[0]
        values = self.tree.item(item, "values")
        if not values or values[0] == "__placeholder__":
            return None
        path = Path(values[0])
        if path.is_dir():
            return item, path
        parent_item = self.tree.parent(item)
        return parent_item, path.parent

    def _new_project_item(self, is_folder: bool) -> None:
        if not self._save_pending_changes():
            return
        location = self._project_creation_location()
        if location is None:
            messagebox.showerror(
                "Cannot Create Item", "Select a project folder first.", parent=self.root
            )
            return
        parent_item, parent_folder = location
        item_type = "folder" if is_folder else "file"
        name = simpledialog.askstring(
            f"New {item_type.title()}",
            f"{item_type.title()} name:",
            parent=self.root,
        )
        if name is None:
            return
        name = name.strip()
        if not name or name in {".", ".."} or "/" in name or "\\" in name:
            messagebox.showerror(
                "Invalid Name", "Enter a valid name without folder separators.", parent=self.root
            )
            return

        new_path = parent_folder / name
        try:
            if is_folder:
                new_path.mkdir()
            else:
                new_path.touch(exist_ok=False)
        except FileExistsError:
            messagebox.showerror(
                "Cannot Create Item",
                f"An item named {name!r} already exists.",
                parent=self.root,
            )
            return
        except OSError as error:
            messagebox.showerror("Cannot Create Item", str(error), parent=self.root)
            return

        self.tree.item(parent_item, open=True)
        refreshed = self._refresh_folder_item(parent_item, parent_folder)
        for child in self.tree.get_children(parent_item):
            child_values = self.tree.item(child, "values")
            if child_values and child_values[0] == str(new_path):
                self.tree.selection_set(child)
                self.tree.focus(child)
                self.tree.see(child)
                if is_folder:
                    self.tree.item(child, open=True)
                    self._populate_folder_item(child, new_path)
                else:
                    self._load_file(new_path)
                break
        if refreshed:
            self.status.set(f"Created {new_path}")

    def new_project_file(self) -> None:
        self._new_project_item(is_folder=False)

    def new_project_folder(self) -> None:
        self._new_project_item(is_folder=True)

    def save_file(self) -> bool:
        if self.current_file is None:
            if self.project_folder is None:
                messagebox.showinfo(
                    "Select a Folder First",
                    "Select a project folder before saving a new file.",
                    parent=self.root,
                )
                return False
            for suffix in range(10000):
                name = "untitled.py" if suffix == 0 else f"untitled{suffix}.py"
                path = self.project_folder / name
                try:
                    with path.open("x", encoding="utf-8"):
                        pass
                except FileExistsError:
                    continue
                except OSError as error:
                    messagebox.showerror("Could Not Save File", str(error), parent=self.root)
                    return False
                self.current_file = path
                break
            else:
                messagebox.showerror(
                    "Could Not Save File",
                    "Could not find an available untitled file name.",
                    parent=self.root,
                )
                return False
        return self._write_file(self.current_file)

    def save_file_as(self) -> bool:
        filename = self._show_file_picker(
            "Save File",
            mode="save",
            default_name=self.current_file.name if self.current_file else "untitled.py",
        )
        if not filename:
            return False
        self.current_file = Path(filename)
        return self._write_file(self.current_file)

    def _write_file(self, path: Path) -> bool:
        text = self.editor.get("1.0", "end-1c")
        try:
            path.write_text(text, encoding="utf-8", newline="")
        except OSError as error:
            messagebox.showerror("Could Not Save File", str(error), parent=self.root)
            return False
        if self.project_folder is None:
            self._set_project_folder(path.parent)
        self.dirty = False
        self.editor.edit_modified(False)
        self._set_title()
        self.status.set(f"Saved {path}")
        return True

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
            command = ["node", str(path)]
        elif extension == ".java":
            self._append_output("Running Java source file...\n\n")
            command = ["java", str(path)]
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


def main() -> None:
    root = tk.Tk()
    PythonEditor(root)
    root.mainloop()


if __name__ == "__main__":
    main()
# https://github.com/branson325/GRAVEL-ENGINE/
