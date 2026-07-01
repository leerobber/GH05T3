import json
from tqdm import tqdm
from llama_index.core import Document
from .file_classifier import scan_data_dir, FileInfo

MAX_CHARS_PER_CHUNK = 2000

def chunk_text(text: str, max_chars: int = MAX_CHARS_PER_CHUNK):
    chunks = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + max_chars, length)
        chunks.append(text[start:end])
        start = end
    return chunks

def ingest_text_file(file: FileInfo):
    docs = []
    with open(file.path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    for i, chunk in enumerate(chunk_text(content)):
        docs.append(Document(
            text=chunk,
            metadata={
                "source_file": file.name,
                "source_path": file.path,
                "chunk_index": i,
                "file_type": "text",
            },
        ))
    return docs

def ingest_log_file(file: FileInfo):
    docs = []
    with open(file.path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    buffer = []
    current_len = 0
    chunk_index = 0

    for line in lines:
        if current_len + len(line) > MAX_CHARS_PER_CHUNK:
            docs.append(Document(
                text="".join(buffer),
                metadata={
                    "source_file": file.name,
                    "source_path": file.path,
                    "chunk_index": chunk_index,
                    "file_type": "log",
                },
            ))
            buffer = []
            current_len = 0
            chunk_index += 1

        buffer.append(line)
        current_len += len(line)

    if buffer:
        docs.append(Document(
            text="".join(buffer),
            metadata={
                "source_file": file.name,
                "source_path": file.path,
                "chunk_index": chunk_index,
                "file_type": "log",
            },
        ))

    return docs

def ingest_json_file(file: FileInfo):
    docs = []
    with open(file.path, "r", encoding="utf-8", errors="ignore") as f:
        raw = f.read()

    try:
        data = json.loads(raw)
        pretty = json.dumps(data, indent=2)
    except Exception:
        pretty = raw

    for i, chunk in enumerate(chunk_text(pretty)):
        docs.append(Document(
            text=chunk,
            metadata={
                "source_file": file.name,
                "source_path": file.path,
                "chunk_index": i,
                "file_type": "json",
            },
        ))
    return docs

def ingest_jsonl_file(file: FileInfo):
    docs = []
    with open(file.path, "r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            docs.append(Document(
                text=line,
                metadata={
                    "source_file": file.name,
                    "source_path": file.path,
                    "line_index": i,
                    "file_type": "jsonl",
                },
            ))
    return docs

def ingest_file(file: FileInfo):
    if not file.is_text_like:
        return []

    if file.ext == ".log":
        return ingest_log_file(file)
    elif file.ext == ".json":
        return ingest_json_file(file)
    elif file.ext == ".jsonl":
        return ingest_jsonl_file(file)
    else:
        return ingest_text_file(file)

def load_documents():
    all_docs = []
    files = scan_data_dir()

    print("=== GH05T3 Ingestion Engine ===")
    print(f"Found {len(files)} files in data/")

    usable = [f for f in files if not f.is_skipped and f.is_text_like]
    skipped = [f for f in files if f.is_skipped or not f.is_text_like]

    print(f"Usable files: {len(usable)}")
    print(f"Skipped files: {len(skipped)}")

    for f in skipped:
        reason = []
        if f.ext not in {".txt", ".md", ".log", ".json", ".jsonl"}:
            reason.append(f"ext={f.ext}")
        if f.size > 20 * 1024 * 1024:
            reason.append(f"size={f.size} bytes")
        print(f"  [SKIP] {f.path} ({', '.join(reason)})")

    for f in tqdm(usable, desc="Ingesting files"):
        docs = ingest_file(f)
        all_docs.extend(docs)

    print(f"Total document chunks: {len(all_docs)}")
    return all_docs
