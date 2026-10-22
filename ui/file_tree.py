from __future__ import annotations
import fnmatch
import shutil
import tkinter as tk
import tokenize
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

class FileTreeMixin:
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
