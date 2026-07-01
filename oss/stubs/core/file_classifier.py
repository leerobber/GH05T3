import os
from .config import DATA_DIR, MAX_FILE_SIZE_BYTES, TEXT_EXTENSIONS, SKIP_EXTENSIONS, get_extension

class FileInfo:
    def __init__(self, path: str):
        self.path = path
        self.name = os.path.basename(path)
        self.ext = get_extension(path)
        self.size = os.path.getsize(path)

    @property
    def is_text_like(self) -> bool:
        return self.ext in TEXT_EXTENSIONS

    @property
    def is_skipped(self) -> bool:
        return self.ext in SKIP_EXTENSIONS or self.size > MAX_FILE_SIZE_BYTES

def scan_data_dir():
    files = []
    for root, _, filenames in os.walk(DATA_DIR):
        for fname in filenames:
            full_path = os.path.join(root, fname)
            files.append(FileInfo(full_path))
    return files
