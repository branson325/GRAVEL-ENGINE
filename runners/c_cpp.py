from __future__ import annotations

import shutil
from pathlib import Path


def cpp_compiler(path: Path) -> str:
    return "gcc" if path.suffix.lower() == ".c" else "g++"


def cpp_command(path: Path, output: Path, compiler: str) -> list[str]:
    return [compiler, str(path), "-o", str(output)]


def available_cpp_compiler(path: Path) -> str | None:
    return shutil.which(cpp_compiler(path))
