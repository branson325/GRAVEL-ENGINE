from pathlib import Path

def javascript_command(path: Path) -> list[str]:
    return ["node", str(path)]
