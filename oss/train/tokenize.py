"""Supervised tokenization — assistant-only loss (RULE 5)."""
from __future__ import annotations

import logging
from dataclasses import dataclass

LOG = logging.getLogger("oss.train.tokenize")

ASSISTANT_MARK = "<|im_start|>assistant"


@dataclass
class TokenizedExample:
    input_ids: list[int]
    labels: list[int]
    source: str = ""


def _find_assistant_start(text: str) -> int:
    idx = text.rfind(ASSISTANT_MARK)
    return idx if idx >= 0 else 0


def tokenize_supervised(
    tokenizer,
    text: str,
    *,
    max_seq_len: int,
    source: str = "",
) -> TokenizedExample | None:
    """Tokenize ChatML; mask prompt tokens so loss applies only to assistant reply."""
    assistant_char = _find_assistant_start(text)
    prefix = text[:assistant_char]
    # Include the assistant header in the trained region
    full_ids = tokenizer.encode(text, add_special_tokens=False)
    if not full_ids:
        return None

    if len(full_ids) > max_seq_len:
        full_ids = full_ids[:max_seq_len]

    prefix_ids = tokenizer.encode(prefix, add_special_tokens=False)
    prompt_len = min(len(prefix_ids), len(full_ids))

    labels = [-100] * len(full_ids)
    for i in range(prompt_len, len(full_ids)):
        labels[i] = full_ids[i]

    return TokenizedExample(input_ids=full_ids, labels=labels, source=source)


def build_tokenized_dataset(tokenizer, examples, *, max_seq_len: int) -> list[TokenizedExample]:
    out: list[TokenizedExample] = []
    for ex in examples:
        tok = tokenize_supervised(
            tokenizer, ex.text, max_seq_len=max_seq_len, source=ex.source,
        )
        if tok and any(l != -100 for l in tok.labels):
            out.append(tok)
    if not out:
        raise ValueError("All examples failed tokenization — check ChatML format")
    LOG.info("Tokenized %d / %d examples (max_seq=%d)", len(out), len(examples), max_seq_len)
    return out


def collate_batch(tokenizer, batch: list[TokenizedExample]) -> dict:
    import torch

    pad_id = tokenizer.pad_token_id or tokenizer.eos_token_id
    max_len = max(len(b.input_ids) for b in batch)

    input_ids, labels, attention_mask = [], [], []
    for item in batch:
        pad_count = max_len - len(item.input_ids)
        input_ids.append(item.input_ids + [pad_id] * pad_count)
        labels.append(item.labels + [-100] * pad_count)
        attention_mask.append([1] * len(item.input_ids) + [0] * pad_count)

    return {
        "input_ids": torch.tensor(input_ids, dtype=torch.long),
        "labels": torch.tensor(labels, dtype=torch.long),
        "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
    }