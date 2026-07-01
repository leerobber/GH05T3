import os

DATA_DIR = "data"

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB

TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".log",
    ".json",
    ".jsonl",
}

SKIP_EXTENSIONS = {
    ".bin",
    ".db",
    ".zip",
    ".pid",
    ".flag",
    ".sh",
}

def get_extension(path: str) -> str:
    return os.path.splitext(path)[1].lower()
