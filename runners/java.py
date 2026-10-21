from pathlib import Path

def java_command(path: Path) -> list[str]:
    return ["java", str(path)]
