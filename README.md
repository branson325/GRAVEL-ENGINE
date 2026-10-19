<p>
    <img src="images/logo.png" alt="gravel logo icon" width="48">
<p>

windows executable file (exe) still dosent work
### **G**eneral **R**untime for **A**gile **V**isual **E**dition & **L**inking

> A colorful, lightweight desktop coding workspace for editing projects, running code, and getting optional AI help.

| 🐍 Python | 🌐 HTML & CSS | ⚡ JavaScript | ☕ Java | 🧩 JSON | 🖥️ Tkinter |
|:---:|:---:|:---:|:---:|:---:|:---:|
| Edit & run | Preview in browser | Run with Node.js | Run with Java | Validate & format | Desktop app |

GRAVEL is a small editor built with Python's standard-library **Tkinter** GUI toolkit. It brings a project explorer, code editor, terminal output, and optional Ollama-powered assistant together in one window.

## ✨ Features

- **Project workspace** — open a folder, browse its files, and create, rename, or delete files and folders from the project tree.
- **Editor basics** — open and save files, create new files, undo edits, and choose between 2-, 4-, or 8-space tabs.
- **Python syntax highlighting and themes** — highlights Python keywords, strings, comments, numbers, constants, and operators; choose a **Light**, **Dark**, or **Forest** application theme. Dark mode uses dark surfaces throughout the workspace with red accents.
- **Run and preview** — run supported code or preview web content, with output and errors shown in the built-in terminal.
- **Interactive terminal input** — send input to a running program, then stop it when needed.
- **Optional AI assistant** — chat about the open file, request a code completion, explain the last run, or ask AI to edit the open file. AI edits are checked for valid Python or JSON where applicable, can be undone with `Ctrl+Z`, and are autosaved.
- **Autosave** — changes to a named file are saved after a short pause. Unsaved changes are also saved before switching files or closing the app.

## 🚀 Run GRAVEL

### Requirements

- **Python 3.10 or newer**
- **Tkinter**, included with most standard Python installations

No Python packages need to be installed for the editor itself.

### Start it [windows executable (exe)]
### [BROKEN (FIXING)]

1. Open the GRAVEL ENGINE INSTALL folder.
2. Open the extracted folder's `dist` folder.
3. Open the `main` folder.
4. Double-click `main.exe` to launch GRAVEL.
5. Microsoft Defender will open and stop the file from opening because it is no signed
6. Click `More info` then click `Run anyway`
Do not move any files (it will not work if you do)

### Start it [Powershell]

Open a terminal in the GRAVEL folder and run:

```powershell
py main.py
```

If the `py` command is unavailable, try:

```powershell
python main.py
```

On macOS or Linux, use `python3 main.py` if `python` does not point to Python 3.

The welcome screen has a **Select Folder** button to open a project. You can also start with **File → Open File...** or create a file with **File → New File**.



## ▶️ What “Run” does

Save the file, then click **Run ▶** or press **F5**. The action depends on the current file type:

| File type | Run behavior | Additional requirement |
|---|---|---|
| `.py` | Checks Python syntax, then runs the file using the same Python interpreter as GRAVEL. | Python |
| `.js`, `.mjs`, `.cjs`, `.javascript` | Runs the file with Node.js. | Node.js available as `node` on `PATH` |
| `.java` | Launches the Java source file. | Java 11 or newer available as `java` on `PATH` |
| `.html`, `.htm` | Opens the saved page in your default browser. | A browser |
| `.css` | Opens a matching `.html`/`.htm` page, or `index.html`/`index.htm` in the same folder, in your browser. | A matching HTML page and a browser |
| `.json` | Validates the JSON and prints a readable, indented version in the terminal. | — |

JavaScript and Java are optional: only install a runtime if you want to run those file types. **Stop ■** terminates a running script; programs that request input can receive it through the terminal's input box.

## 📜 License

GRAVEL is available under the custom noncommercial attribution terms in [LICENSE](./LICENSE). You may use, modify, and share it for noncommercial purposes, but any use or posting must include the credit **"Created by QuantumNight101 | Branson325"**. Commercial use requires prior written permission from the copyright holder.

## 🤖 Optional AI assistant

The editor works without AI. To use the assistant:

1. Install [Ollama](https://ollama.com/) and start its local service.
2. Open a project or file, then click **AI Assistant**.
3. Select an available model and use **Refresh** to check the model list. If needed, enter a model name and select **Pull Model** to download it.
4. Enter a prompt and press **Enter** or **Send**. With **Apply code changes to the open file** checked, the prompt asks the model to edit the file; uncheck it to chat without applying edits.

GRAVEL connects to Ollama at `http://localhost:11434`. The default model name is `gemma4:cloud`; using an Ollama cloud model may send prompts and included code to that model's cloud provider. For local-only processing, choose a model that runs locally and confirm the model's behavior in Ollama.

AI options include:

- **Complete (Ctrl+Space)** — ask for a Python code completion at the cursor.
- **Explain Last Run** — ask for an explanation of the most recent output or error.
- **Edit Open Script with AI** — request a full-file edit for Python, HTML, CSS, JSON, JavaScript, or Java. The assistant response must contain the replacement file in a code block.

## ⌨️ Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+N` | New file |
| `Ctrl+O` | Open file |
| `Ctrl+Shift+O` | Open project folder |
| `Ctrl+S` | Save |
| `F5` | Run current file |
| `Ctrl+Space` | Request AI completion |
| `Ctrl+Z` | Undo an edit, including an applied AI edit |

## 🗂️ Project contents

```text
GRAVEL/
├── main.py          # Application and editor implementation
├── README.md        # Project guide
├── LICENSE          # Custom noncommercial attribution terms
└── images/          # File-type icons used in the project explorer
    ├── css.png
    ├── html.png
    ├── java.png
    ├── javascript.png
    ├── json.png
    └── python.png
```

Keep the `images` folder beside `main.py`; the application loads its file icons from there at startup.

## 🛠️ Troubleshooting

- **The window does not start:** Confirm Python 3.10+ is installed with Tkinter. On Windows, install Python from the official installer and ensure the **tcl/tk and IDLE** feature is enabled.
- **A language runtime is not found:** Install Node.js or Java as appropriate, then make sure `node` or `java` is available on your `PATH`.
- **AI says Ollama is unavailable:** Start Ollama and use **Refresh** in the AI panel.
- **CSS does not preview:** Put a matching HTML file (for example, `style.css` beside `style.html`) or an `index.html` in the same folder.
- **An edited file is not in the project tree:** Open its containing folder to use the project explorer.

## 🖼️ Included file icons

<p>
  <img src="images/python.png" alt="Python file icon" width="48">
  <img src="images/html.png" alt="HTML file icon" width="48">
  <img src="images/css.png" alt="CSS file icon" width="48">
  <img src="images/javascript.png" alt="JavaScript file icon" width="48">
  <img src="images/java.png" alt="Java file icon" width="48">
  <img src="images/json.png" alt="JSON file icon" width="48">
</p>
