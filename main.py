from tkinter import Tk

from ui.window import PythonEditor


def main() -> None:
    root = Tk()
    PythonEditor(root)
    root.mainloop()


if __name__ == "__main__":
    main()

