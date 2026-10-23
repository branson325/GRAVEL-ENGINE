# FIRE GRAVEL BETA (1.0.7) - Smarter Editor, Safer Workflow, More Control

- Refined the editor layout with improved spacing, contrast, and visual separation.
- Added active-line highlighting and a theme-aware line-number gutter that emphasizes the cursor line.
- Added Light, Dark, and Forest themes, with saved theme selection and persistent custom colors.
- Made the welcome screen and editor controls follow the selected theme.
- Added editor font-family and font-size controls, with persistent preferences.
- Redesigned AI chat output as distinct, streaming message cards.
- Made AI chat include the open file's actual language instead of always labeling it as Python.
- Tightened AI file edits: responses must contain one full-file code block in the expected language; Python and JSON replacements are validated before applying.
- Improved project navigation and file management, including unsaved-change protection when opening recent files.
- Clarified save state and safer handling of unsaved files: named files autosave, while new untitled files prompt for a save location instead of being silently created.
- Improved syntax highlighting responsiveness and editor display updates.
- Preserved the existing multi-language runners, optional Ollama assistant, and undo support for AI edits.
- Added lava theme (TRY IT OUT)
