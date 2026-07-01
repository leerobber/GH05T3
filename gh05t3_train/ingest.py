import os
import torch
from transformers import AutoTokenizer
from gh05t3_train.config import MAX_SEQ_LEN, DEVICE


def load_text_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf8", errors="ignore") as f:
            return f.read()
    except:
        return ""


def chunk_text(text: str, max_tokens: int = 256):
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_tokens):
        chunk = " ".join(words[i:i + max_tokens])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def ingest_corpus():
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    data_dir = os.path.abspath(data_dir)

    tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")

    raw_texts = []
    token_ids = []

    for root, _, files in os.walk(data_dir):
        for fname in files:
            path = os.path.join(root, fname)
            ext = os.path.splitext(fname)[1].lower()

            if ext not in [".txt", ".md", ".log", ".json", ".py"]:
                continue

            text = load_text_file(path)
            if not text.strip():
                continue

            chunks = chunk_text(text, max_tokens=256)

            for chunk in chunks:
                raw_texts.append(chunk)

                ids = tokenizer.encode(chunk, add_special_tokens=False)
                ids = ids[:MAX_SEQ_LEN]   # HARD CLAMP
                token_ids.append(ids)

    if not raw_texts:
        raise RuntimeError("No usable text found in data/ directory.")

    max_len = max(len(ids) for ids in token_ids)

    padded = []
    for ids in token_ids:
        pad_len = max_len - len(ids)
        padded.append(ids + [0] * pad_len)

    token_tensor = torch.tensor(padded, dtype=torch.long, device=DEVICE)

    return {
        "tokenizer": tokenizer,
        "token_ids": token_tensor,
        "raw_texts": raw_texts,
    }
