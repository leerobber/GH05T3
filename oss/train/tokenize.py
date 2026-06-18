"""Supervised tokenization — assistant-only loss (RULE 5)."""
from __future__ import annotations

import logging
from dataclasses import dataclass

LOG = logging.getLogger("oss.train.tokenize")

ASSISTANT_MARK = "<|im_start|>assistant"
_USER_MARK = "<|im_start|>user"
_END_MARK = "<|im_end|>"


@dataclass
class TokenizedExample:
    input_ids: list[int]
    labels: list[int]
    source: str = ""


def _fit_chatml(text: str, tokenizer, max_seq_len: int) -> str:
    """Shrink oversized ChatML — trim user body first, always keep assistant tail."""
    n = len(tokenizer.encode(text, add_special_tokens=False, truncation=True, max_length=max_seq_len))
    if n <= max_seq_len:
        return text

    a_idx = text.rfind(ASSISTANT_MARK)
    if a_idx < 0:
        return text[: max_seq_len * 3]

    prefix = text[:a_idx]
    assistant_part = text[a_idx:]
    u_idx = prefix.rfind(_USER_MARK)
    if u_idx < 0:
        return assistant_part[: max_seq_len * 3]

    head = prefix[: u_idx + len(_USER_MARK)]
    user_body = prefix[u_idx + len(_USER_MARK) :]
    lo, hi = 0, len(user_body)
    best = assistant_part
    while lo <= hi:
        mid = (lo + hi) // 2
        candidate = head + "\n" + user_body[mid:] + "\n" + _END_MARK + "\n" + assistant_part
        cnt = len(tokenizer.encode(candidate, add_special_tokens=False, truncation=True, max_length=max_seq_len))
        if cnt <= max_seq_len:
            best = candidate
            hi = mid - 1
        else:
            lo = mid + 1
    return best


def tokenize_supervised(
    tokenizer,
    text: str,
    *,
    max_seq_len: int,
    source: str = "",
) -> TokenizedExample | None:
    """Tokenize ChatML; mask prompt tokens so loss applies only to assistant reply."""
    if not text or ASSISTANT_MARK not in text:
        return None

    text = _fit_chatml(text, tokenizer, max_seq_len)
    assistant_char = text.rfind(ASSISTANT_MARK)
    prefix = text[:assistant_char]

    full_ids = tokenizer.encode(
        text, add_special_tokens=False, truncation=True, max_length=max_seq_len,
    )
    if not full_ids:
        return None

    prefix_ids = tokenizer.encode(
        prefix, add_special_tokens=False, truncation=True, max_length=max_seq_len,
    )
    prompt_len = min(len(prefix_ids), len(full_ids))

    labels = [-100] * len(full_ids)
    for i in range(prompt_len, len(full_ids)):
        labels[i] = full_ids[i]

    if not any(l != -100 for l in labels):
        return None

    return TokenizedExample(input_ids=full_ids, labels=labels, source=source)


def build_tokenized_dataset(tokenizer, examples, *, max_seq_len: int) -> list[TokenizedExample]:
    out: list[TokenizedExample] = []
    skipped = 0
    for ex in examples:
        tok = tokenize_supervised(
            tokenizer, ex.text, max_seq_len=max_seq_len, source=ex.source,
        )
        if tok:
            out.append(tok)
        else:
            skipped += 1
    if not out:
        raise ValueError("All examples failed tokenization — check ChatML format")
    LOG.info(
        "Tokenized %d / %d examples (skipped=%d, max_seq=%d)",
        len(out), len(examples), skipped, max_seq_len,
    )
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