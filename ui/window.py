from __future__ import annotations
import json
import keyword
import queue
import re
import subprocess
import tempfile
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from ai.assistant import AIAssistantMixin
from runners import RunnerMixin
from ui.file_tree import FileTreeMixin

class PythonEditor(AIAssistantMixin, FileTreeMixin, RunnerMixin):
    VERSION = "1.0.7"
    SUPPORTED_FILETYPES = (
        ("Supported files", "*.py *.html *.htm *.css *.json *.js *.mjs *.cjs *.javascript *.java *.c *.cc *.cpp *.cxx"),
        ("Python files", "*.py"),
        ("HTML files", "*.html *.htm"),
        ("CSS files", "*.css"),
        ("JSON files", "*.json"),
        ("JavaScript files", "*.js *.mjs *.cjs *.javascript"),
        ("Java files", "*.java"),
        ("C/C++ files", "*.c *.cc *.cpp *.cxx"),
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
    LANGUAGE_KEYWORDS = {
        "javascript": set(
            "as async await break case catch class const continue debugger default delete do "
            "else export extends finally for from function if import in instanceof let new "
            "of return static super switch this throw try typeof var void while with yield"
        .split()),
        "java": set(
            "abstract assert boolean break byte case catch char class const continue default "
            "do double else enum extends final finally float for if implements import instanceof "
            "int interface long native new package private protected public return short static "
            "strictfp super switch synchronized this throw throws transient try void volatile while"
        .split()),
        "cpp": set(
            "alignas alignof and asm auto bool break case catch char class const constexpr "
            "continue decltype default delete do double else enum explicit extern false float "
            "for friend goto if inline int long namespace new noexcept not nullptr operator "
            "private protected public register reinterpret_cast return short signed sizeof static "
            "struct switch template this throw true try typedef typeid typename union unsigned "
            "using virtual void volatile wchar_t while"
        .split()),
    }
    PYTHON_SYNTAX_PATTERN = re.compile(
        r"(?P<comment>\#[^\n]*)"
        r"|(?P<string>\"\"\"[\s\S]*?\"\"\"|'''[\s\S]*?'''|"
        r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')"
        r"|(?P<number>\b(?:0[xX][0-9a-fA-F]+|0[bB][01]+|"
        r"(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)[jJ]?)"
        r"|(?P<identifier>[A-Za-z_][A-Za-z0-9_]*)"
        r"|(?P<operator>==|!=|<=|>=|//|\*\*|:=|->|"
        r"[+\-*/%=&|^~!<>?:.]|[(){}\[\],;@])"
    )
    SYNTAX_PATTERN = re.compile(
        r"(?P<comment>//[^\n]*|/\*[\s\S]*?\*/)"
        r"|(?P<string>\"\"\"[\s\S]*?\"\"\"|'''[\s\S]*?'''|"
        r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)"
        r"|(?P<number>\b(?:0[xX][0-9a-fA-F]+|0[bB][01]+|"
        r"(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)[uUlLfF]*)"
        r"|(?P<identifier>[A-Za-z_$][A-Za-z0-9_$]*)"
        r"|(?P<operator>==|!=|<=|>=|&&|\|\||\+\+|--|->|=>|"
        r"[+\-*/%=&|^~!<>?:.]|[(){}\[\],;])"
    )
    THEMES = {
        "Light": {
            "background": "#ffffff", "foreground": "#202124", "selection": "#cde8ff",
            "keyword": "#7b2cbf", "constant": "#b42318", "string": "#18794e",
            "comment": "#777f8b", "number": "#a04b00", "operator": "#405a78",
            "panel": "#f3f4f6", "field": "#ffffff", "surface": "#f3f4f6",
            "border": "#c9cdd3", "muted": "#68707c", "accent": "#0078d4",
            "accent_hover": "#005a9e", "accent_foreground": "#ffffff",
        },
        "Dark": {
            "background": "#17181b", "foreground": "#e2e4e9", "selection": "#702b31",
            "keyword": "#cf8ef4", "constant": "#ff7b72", "string": "#a5d6a7",
            "comment": "#89929e", "number": "#f2b880", "operator": "#91b9e8",
            "panel": "#1e2024", "field": "#191a1e", "surface": "#292b30",
            "border": "#393c43", "muted": "#a0a5af", "accent": "#0078d4",
            "accent_hover": "#2b88ff", "accent_foreground": "#ffffff",
        },
        "Fire": {
            "background": "#4a0000", "foreground": "#ffebeb", "selection": "#ff4d4d",
            "keyword": "#ff8080", "constant": "#ffc0c0", "string": "#ffa080",
            "comment": "#8a5d5d", "number": "#ffda80", "operator": "#ff6060",
            "panel": "#5a0000", "field": "#2a0000", "surface": "#6a0000",
            "border": "#8a0000", "muted": "#b38b8b", "accent": "#ff0000",
            "accent_hover": "#ff4d4d", "accent_foreground": "#ffffff",
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
    AI_RESPONSE_RED = "#c9363e"
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
        self.last_run_error = ""
        self._run_temp_dir: tempfile.TemporaryDirectory | None = None
        self._compile_in_progress = False

        self.dirty = False

        self._stop_requested = False

        self._autosave_after_id: str | None = None

        self._syntax_after_id: str | None = None

        self._closing = False

        self.settings_path = Path.home() / ".gravel" / "settings.json"

        (
            initial_theme,
            self.custom_theme_colors,
            self.recent_paths,
            self.editor_font_family,
            self.editor_font_size,
            saved_ai_system_prompt,
            saved_ai_temperature,
            saved_ai_history,
        ) = self._load_settings()

        self.theme_var = tk.StringVar(value=initial_theme)

        self.ai_system_prompt_var = tk.StringVar(value=saved_ai_system_prompt)
        self.ai_temperature_var = tk.DoubleVar(value=saved_ai_temperature)
        self.ai_history: list[tuple[str, str]] = []
        if saved_ai_history:
            self.ai_history = [(str(speaker), str(text)) for speaker, text in saved_ai_history]
        self._ai_chat_cards: list[tuple[tk.Frame, tk.Label, tk.Text, str]] = []
        self._ai_stream_label: tk.Text | None = None

        self.tab_size_var = tk.IntVar(value=4)

        self.ai_apply_edits_var = tk.BooleanVar(value=True)
        self._active_palette = {
            **self.THEMES[initial_theme],
            **self.custom_theme_colors.get(initial_theme, {}),
        }

        images_folder = Path(__file__).resolve().parent.parent / "images"

        self.file_icon_images = {

            icon_name: tk.PhotoImage(

                file=str(images_folder / f"{icon_name}.png")

            ).subsample(2, 2)

            for icon_name in set(self.FILE_ICONS.values())

        }

        welcome_logo = tk.PhotoImage(file=str(images_folder / "fire_logo.png"))

        self.welcome_logo_large = welcome_logo.subsample(3, 3)

        self.welcome_logo_small = welcome_logo.subsample(4, 4)

        self.ai_model_var = tk.StringVar(value="gemma4:cloud")

        self.ai_status = tk.StringVar(value="Local Ollama model not checked")

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
        settings_menu.add_command(label="Editor Font...", command=self._edit_font_settings)

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

    def _load_settings(
        self,
    ) -> tuple[str, dict[str, dict[str, str]], list[str], str, int]:

        try:

            with self.settings_path.open(encoding="utf-8") as settings_file:

                settings = json.load(settings_file)

        except FileNotFoundError:

            return "Light", {}, [], "Consolas", 11

        except (json.JSONDecodeError, UnicodeError) as error:

            messagebox.showwarning(

                "Settings", f"Could not read settings file:\n{error}", parent=self.root

            )

            return "Light", {}, [], "Consolas", 11

        except OSError as error:

            messagebox.showwarning(

                "Settings", f"Could not read settings file:\n{error}", parent=self.root

            )

            return "Light", {}, [], "Consolas", 11

        if not isinstance(settings, dict):

            messagebox.showwarning(

                "Settings",

                "Settings file has an invalid format. Using default settings.",

                parent=self.root,

            )

            return "Light", {}, [], "Consolas", 11

        theme = settings.get("theme", "Fire")
        if not isinstance(theme, str) or theme not in self.THEMES:
            theme = "Fire"

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

        font_family = settings.get("editor_font_family", "Consolas")
        if not isinstance(font_family, str) or not font_family.strip():
            font_family = "Consolas"
        font_size = settings.get("editor_font_size", 11)
        if not isinstance(font_size, int) or isinstance(font_size, bool):
            font_size = 11
        font_size = min(max(font_size, 6), 48)
        ai_system_prompt = settings.get(
            "ai_system_prompt",
            "You are a helpful coding assistant. Answer clearly and provide code when useful.",
        )
        if not isinstance(ai_system_prompt, str) or not ai_system_prompt.strip():
            ai_system_prompt = (
                "You are a helpful coding assistant. Answer clearly and provide code when useful."
            )
        ai_temperature = settings.get("ai_temperature", 0.7)
        if not isinstance(ai_temperature, (int, float)) or isinstance(ai_temperature, bool):
            ai_temperature = 0.7
        ai_temperature = min(max(float(ai_temperature), 0.0), 2.0)
        saved_ai_history = settings.get("ai_history", [])
        if not isinstance(saved_ai_history, list):
            saved_ai_history = []
        return (
            theme,
            custom_colors,
            recent_paths,
            font_family,
            font_size,
            ai_system_prompt,
            ai_temperature,
            saved_ai_history,
        )

    def _save_settings(self) -> bool:

        settings = {

            "theme": self.theme_var.get(),

            "custom_colors": self.custom_theme_colors,

            "recent_files": self.recent_paths,
            "editor_font_family": self.editor_font_family,
            "editor_font_size": self.editor_font_size,
            "ai_system_prompt": self.ai_system_prompt_var.get(),
            "ai_temperature": self.ai_temperature_var.get(),
            "ai_history": self.ai_history,
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

        self.fix_run_button = ttk.Button(
            toolbar,
            text="Fix with GRAVEL AI",
            command=self._fix_last_run_with_ai,
            style="Accent.TButton",
        )
        self.fix_run_button.pack(side=tk.LEFT, padx=5)
        self.fix_run_button.pack_forget()

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

        editor_frame.columnconfigure(1, weight=1)

        self.editor = tk.Text(

            editor_frame,

            wrap=tk.NONE,

            undo=True,

            font=(self.editor_font_family, self.editor_font_size),

            padx=12,

            pady=8,

            borderwidth=0,

            highlightthickness=1,

            spacing1=1,

            spacing3=1,

        )

        self._apply_tab_size()

        self.line_numbers = tk.Canvas(
            editor_frame,
            width=42,
            bd=0,
            highlightthickness=0,
            background="#f3f4f6",
        )
        self.line_numbers.grid(row=0, column=0, sticky="ns")
        self.editor.grid(row=0, column=1, sticky="nsew")

        self.editor.bind("<Tab>", self._insert_tab_spaces)
        self.editor.bind("<KeyPress>", self._auto_close_pair)
        self.editor.bind("<KeyRelease>", self._update_current_line)
        self.editor.bind("<ButtonRelease-1>", self._update_current_line)

        self.editor_y = ttk.Scrollbar(
            editor_frame, orient=tk.VERTICAL, command=self.editor.yview
        )
        self.editor_y.grid(row=0, column=2, sticky="ns")

        editor_x = ttk.Scrollbar(editor_frame, orient=tk.HORIZONTAL, command=self.editor.xview)
        editor_x.grid(row=1, column=1, sticky="ew")

        self.editor.configure(
            yscrollcommand=self._editor_scroll_changed,
            xscrollcommand=editor_x.set,
        )
        editor_frame.columnconfigure(1, weight=1)
        editor_frame.bind("<Configure>", lambda _event: self._redraw_line_numbers())
        self.editor.bind("<Configure>", lambda _event: self._redraw_line_numbers())

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

        self.ai_panel.rowconfigure(8, weight=1)

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

        system_prompt_row = ttk.Frame(self.ai_panel)

        system_prompt_row.grid(row=2, column=0, sticky="ew", pady=(0, 4))

        system_prompt_row.columnconfigure(0, weight=1)

        ttk.Button(

            system_prompt_row,

            text="System Prompt...",

            command=self._edit_system_prompt,

        ).grid(row=0, column=0, sticky="ew")

        temperature_row = ttk.Frame(self.ai_panel)

        temperature_row.grid(row=3, column=0, sticky="ew", pady=(0, 4))

        temperature_row.columnconfigure(1, weight=1)

        ttk.Label(temperature_row, text="Temperature:").grid(row=0, column=0, sticky=tk.W)

        self.ai_temperature_scale = tk.Scale(

            temperature_row,

            from_=0.0,

            to=2.0,

            resolution=0.1,

            orient=tk.HORIZONTAL,

            variable=self.ai_temperature_var,

            showvalue=False,

            length=150,

        )

        self.ai_temperature_scale.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        self.ai_temperature_value_label = ttk.Label(

            temperature_row, text="0.7", width=4

        )

        self.ai_temperature_value_label.grid(row=0, column=2, padx=(4, 0))

        def _update_temperature_label(*_args) -> None:

            self.ai_temperature_value_label.configure(

                text=f"{self.ai_temperature_var.get():.1f}"

            )

        self.ai_temperature_var.trace_add("write", _update_temperature_label)

        _update_temperature_label()

        ttk.Label(

            self.ai_panel,

            textvariable=self.ai_status,

            wraplength=310,

            justify=tk.LEFT,

        ).grid(row=4, column=0, sticky="ew", pady=(0, 6))

        ai_actions = ttk.Frame(self.ai_panel)

        ai_actions.grid(row=5, column=0, sticky="ew", pady=(0, 6))

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

        self.ai_edit_button.grid(row=6, column=0, sticky="ew", pady=(0, 6))

        ttk.Button(

            self.ai_panel,

            text="Clear History",

            command=self._clear_ai_history,

        ).grid(row=7, column=0, sticky="ew", pady=(0, 6))

        self.ai_chat = tk.Text(
            self.ai_panel,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Segoe UI", 10),
            padx=7,
            pady=7,
            borderwidth=0,
            highlightthickness=1,
        )
        self.ai_chat.grid(row=8, column=0, sticky="nsew")

        ai_chat_scroll = ttk.Scrollbar(
            self.ai_panel, orient=tk.VERTICAL, command=self.ai_chat.yview
        )
        ai_chat_scroll.grid(row=8, column=1, sticky="ns")
        self.ai_chat.configure(yscrollcommand=ai_chat_scroll.set)

        ai_prompt_row = ttk.Frame(self.ai_panel)

        ai_prompt_row.grid(row=9, column=0, sticky="ew")

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

            if self._save_pending_changes():

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

    def _editor_scroll_changed(self, first: str, last: str) -> None:
        self.editor_y.set(first, last)
        self._redraw_line_numbers()

    def _update_current_line(self, _event: tk.Event | None = None) -> None:
        if not hasattr(self, "editor"):
            return
        self.editor.tag_remove("current_line", "1.0", tk.END)
        self.editor.tag_add(
            "current_line",
            self.editor.index("insert linestart"),
            self.editor.index("insert lineend +1c"),
        )
        self.editor.tag_lower("current_line")
        self._redraw_line_numbers()

    def _redraw_line_numbers(self) -> None:
        if not hasattr(self, "line_numbers") or not self.line_numbers.winfo_exists():
            return
        self.line_numbers.delete("all")
        line_count = int(self.editor.index("end-1c").split(".")[0])
        number_font = tkfont.Font(root=self.root, font=self.editor.cget("font"))
        active_number_font = tkfont.Font(root=self.root, font=self.editor.cget("font"))
        active_number_font.configure(weight="bold")
        active_line = int(self.editor.index("insert").split(".")[0])
        palette = self._active_palette
        self.line_numbers.configure(
            width=max(42, number_font.measure("9" * len(str(line_count))) + 12)
        )
        line_number = int(self.editor.index("@0,0").split(".")[0])
        height = self.editor.winfo_height()
        while True:
            position = self.editor.dlineinfo(f"{line_number}.0")
            if position is None or position[1] >= height:
                break
            self.line_numbers.create_text(
                self.line_numbers.winfo_width() - 6,
                position[1] + position[3] / 2,
                anchor=tk.E,
                text=str(line_number),
                fill=palette["accent"] if line_number == active_line else palette["muted"],
                font=active_number_font if line_number == active_line else number_font,
            )
            line_number += 1
        self.line_numbers.create_line(
            self.line_numbers.winfo_width() - 1,
            0,
            self.line_numbers.winfo_width() - 1,
            height,
            fill=palette["border"],
        )

    def _auto_close_pair(self, event: tk.Event) -> str | None:
        pairs = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'"}
        closing = pairs.get(event.char)
        if closing is None:
            return None
        next_character = self.editor.get(tk.INSERT, f"{tk.INSERT} + 1 chars")
        if event.char in {'"', "'"} and next_character == closing:
            self.editor.mark_set(tk.INSERT, f"{tk.INSERT} + 1 chars")
            return "break"
        selection = self.editor.tag_ranges(tk.SEL)
        if selection:
            start, end = selection[0], selection[1]
            selected_text = self.editor.get(start, end)
            self.editor.delete(start, end)
            self.editor.insert(start, event.char + selected_text + closing)
            self.editor.mark_set(tk.INSERT, f"{start} + {len(selected_text) + 1} chars")
        else:
            self.editor.insert(tk.INSERT, event.char + closing)
            self.editor.mark_set(tk.INSERT, f"{tk.INSERT} - 1 chars")
        return "break"

    def _edit_font_settings(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Editor Font")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.columnconfigure(1, weight=1)

        family_var = tk.StringVar(value=self.editor_font_family)
        size_var = tk.IntVar(value=self.editor_font_size)
        ttk.Label(dialog, text="Font family").grid(
            row=0, column=0, padx=(12, 6), pady=(12, 6), sticky=tk.W
        )
        family_box = ttk.Combobox(
            dialog,
            textvariable=family_var,
            values=sorted(tkfont.families(self.root)),
            width=28,
        )
        family_box.grid(row=0, column=1, padx=(6, 12), pady=(12, 6), sticky="ew")
        ttk.Label(dialog, text="Font size").grid(
            row=1, column=0, padx=(12, 6), pady=6, sticky=tk.W
        )
        ttk.Spinbox(dialog, from_=6, to=48, textvariable=size_var, width=8).grid(
            row=1, column=1, padx=(6, 12), pady=6, sticky=tk.W
        )

        def apply_font() -> None:
            family = family_var.get().strip()
            try:
                size = int(size_var.get())
            except (tk.TclError, ValueError):
                messagebox.showerror(
                    "Editor Font", "Font size must be a number from 6 to 48.", parent=dialog
                )
                return
            if not family or not 6 <= size <= 48:
                messagebox.showerror(
                    "Editor Font",
                    "Choose a font family and a font size from 6 to 48.",
                    parent=dialog,
                )
                return
            previous_family = self.editor_font_family
            previous_size = self.editor_font_size
            self.editor_font_family = family
            self.editor_font_size = size
            self.editor.configure(font=(family, size))
            self._apply_tab_size()
            self._redraw_line_numbers()
            if not self._save_settings():
                self.editor_font_family = previous_family
                self.editor_font_size = previous_size
                self.editor.configure(font=(previous_family, previous_size))
                self._apply_tab_size()
                self._redraw_line_numbers()
                return
            dialog.destroy()

        buttons = ttk.Frame(dialog)
        buttons.grid(row=2, column=0, columnspan=2, pady=(6, 12))
        ttk.Button(buttons, text="Apply", command=apply_font).pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=4)
        dialog.bind("<Return>", lambda _event: apply_font())
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.grab_set()
        family_box.focus_set()

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
            self._redraw_line_numbers()

            if self._autosave_after_id is not None:

                self.root.after_cancel(self._autosave_after_id)

            self._autosave_after_id = self.root.after(500, self._autosave)

    def _autosave(self) -> None:

        self._autosave_after_id = None

        if self.dirty and self.current_file is not None:

            self.save_file()

    def _set_editor_text(self, text: str) -> None:

        self.editor.delete("1.0", tk.END)

        self.editor.insert("1.0", text)

        self.editor.edit_modified(False)

        self._update_current_line()

        self._redraw_line_numbers()

        self.dirty = False

        self._set_title()

    def _set_theme(self, theme_name: str) -> None:

        palette = {
            **self.THEMES[theme_name],
            **self.custom_theme_colors.get(theme_name, {}),
        }
        self._active_palette = palette

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

            background=palette["accent"],

            foreground=palette["accent_foreground"],

            bordercolor=palette["accent"],

            padding=(16, 9),

            font=("Segoe UI", 10, "bold"),

        )

        style.map(

            "Welcome.TButton",

            background=[
                ("pressed", palette["accent_hover"]),
                ("active", palette["accent_hover"]),
            ],

            foreground=[
                ("pressed", palette["accent_foreground"]),
                ("active", palette["accent_foreground"]),
            ],

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

        for widget in (self.editor, self.output):

            widget.configure(

                background=palette["field"],

                foreground=palette["foreground"],

                insertbackground=palette["foreground"],

                selectbackground=palette["accent"],

                selectforeground=palette["accent_foreground"],

                highlightbackground=palette["border"],

                highlightcolor=palette["accent"],

            )

        self.editor.configure(
            background=palette["background"],
            selectbackground=palette["selection"],
            highlightbackground=palette["border"],
            highlightcolor=palette["accent"],
        )
        self.welcome.configure(background=palette["background"])
        self._draw_welcome()
        self.line_numbers.configure(background=palette["panel"])
        self.ai_chat.configure(
            background=palette["background"],
            highlightbackground=palette["border"],
            highlightcolor=palette["accent"],
        )
        for card, role_label, body_label, speaker in self._ai_chat_cards:
            is_assistant = speaker == "Assistant"
            card_background = palette["panel"] if is_assistant else palette["surface"]
            card.configure(
                background=card_background,
                highlightbackground=self.AI_RESPONSE_RED if is_assistant else palette["border"],
            )
            role_label.configure(
                background=card_background,
                foreground=self.AI_RESPONSE_RED if is_assistant else palette["muted"],
            )
            body_label.configure(
                background=card_background,
                foreground=palette["foreground"],
                insertbackground=palette["foreground"],
                selectbackground=palette["accent"],
                selectforeground=palette["accent_foreground"],
            )

        self.root.option_add("*TCombobox*Listbox.background", palette["field"])

        self.root.option_add("*TCombobox*Listbox.foreground", palette["foreground"])

        self.root.option_add("*TCombobox*Listbox.selectBackground", palette["accent"])

        self.root.option_add(

            "*TCombobox*Listbox.selectForeground", palette["accent_foreground"]

        )

        for tag in self.SYNTAX_TAGS:

            self.editor.tag_configure(f"syntax_{tag}", foreground=palette[tag])

        self.editor.tag_configure("current_line", background=palette["surface"])
        self.editor.tag_lower("current_line")
        self._highlight_syntax()
        self._update_current_line()
        self._redraw_line_numbers()

    def _draw_welcome(self, event: tk.Event | None = None) -> None:

        width = event.width if event is not None else self.welcome.winfo_width()

        height = event.height if event is not None else self.welcome.winfo_height()

        if width <= 1 or height <= 1:

            return

        self.welcome.delete("welcome_background", "welcome_content")

        palette = self._active_palette
        top_color = tuple(
            int(palette["background"][index:index + 2], 16)
            for index in (1, 3, 5)
        )
        middle_color = tuple(
            int(palette["surface"][index:index + 2], 16)
            for index in (1, 3, 5)
        )
        bottom_color = tuple(
            int(palette["panel"][index:index + 2], 16)
            for index in (1, 3, 5)
        )

        band_height = max(1, height // 120)

        for y in range(0, height, band_height):
            self.welcome.create_rectangle(
                0, y, width, y + band_height, fill="#000000", outline="#000000",
                tags="welcome_background",
            )

        self.welcome.create_text(

            width - 16,

            14,

            anchor=tk.NE,

            text=f"Version {self.VERSION}",

            fill=palette["muted"],

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

            fill=palette["foreground"],

            font=("Segoe UI", 20, "bold"),

            tags="welcome_content",

        )

        subtitle_y = title_y + title_height + 8

        self.welcome.create_text(

            width // 2,

            subtitle_y + subtitle_height // 2,

            text="Open a project or file, or create a new file to get started.",

            fill=palette["muted"],

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

    def _schedule_syntax_highlighting(self) -> None:

        if self._syntax_after_id is not None:

            self.root.after_cancel(self._syntax_after_id)

        self._syntax_after_id = self.root.after(120, self._highlight_syntax)

    def _highlight_syntax(self) -> None:

        self._syntax_after_id = None

        for tag in self.SYNTAX_TAGS:

            self.editor.tag_remove(f"syntax_{tag}", "1.0", tk.END)

        source = self.editor.get("1.0", "end-1c")
        extension = self.current_file.suffix.lower() if self.current_file else ".py"
        pattern = (
            self.PYTHON_SYNTAX_PATTERN if extension == ".py" else self.SYNTAX_PATTERN
        )
        language = (
            "javascript"
            if extension in {".js", ".mjs", ".cjs", ".javascript"}
            else "java"
            if extension == ".java"
            else "cpp"
            if extension in {".c", ".cc", ".cpp", ".cxx"}
            else "python"
        )
        keywords = self.LANGUAGE_KEYWORDS.get(language, set())
        constants = {
            "python": {"True", "False", "None"},
            "javascript": {"true", "false", "null", "undefined", "NaN", "Infinity"},
            "java": {"true", "false", "null"},
            "cpp": {"true", "false", "nullptr"},
        }.get(language, set())

        for item in pattern.finditer(source):
            category = item.lastgroup
            if category == "identifier":
                word = item.group()
                if word in constants:
                    category = "constant"
                elif (
                    keyword.iskeyword(word)
                    if language == "python"
                    else word in keywords
                ):
                    category = "keyword"
                else:
                    continue
            if category in self.SYNTAX_TAGS:
                start = f"1.0 + {item.start()} chars"
                end = f"1.0 + {item.end()} chars"
                self.editor.tag_add(f"syntax_{category}", start, end)
        self._redraw_line_numbers()
