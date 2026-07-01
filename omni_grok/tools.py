import subprocess
from pathlib import Path

def read_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")

def write_file(path: str, content: str) -> None:
    Path(path).write_text(content, encoding="utf-8")

def list_files(pattern: str = "**/*.py"):
    return [str(p) for p in Path(".").glob(pattern)]

def run_command(cmd: str) -> str:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout + ("\n" + result.stderr if result.stderr else "")
