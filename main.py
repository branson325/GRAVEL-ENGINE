import ctypes
import sys
from tkinter import Tk

from ui.window import PythonEditor


def _set_windows_app_id() -> None:
    if sys.platform == "win32":
        result = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "QuantumNight101.GRAVEL"
        )
        if result != 0:
            raise OSError(f"Could not set the GRAVEL Windows app ID: {result}")


def main() -> None:
    _set_windows_app_id()
    root = Tk()
    PythonEditor(root)
    root.mainloop()


if __name__ == "__main__":
    main()
