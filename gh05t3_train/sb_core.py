import torch
import hashlib

def text_to_binary_embedding(text: str, max_bits: int = 128):
    """
    Convert text into a deterministic binary fingerprint.

    Steps:
    - Hash the text with SHA-256
    - Convert the hash bytes into bits
    - Truncate or pad to max_bits
    - Return a float tensor of 0.0/1.0 values

    This gives the model a stable structural signal
    that complements the text embeddings.
    """
    if not text:
        return torch.zeros(max_bits, dtype=torch.float32)

    # SHA-256 hash of the text
    h = hashlib.sha256(text.encode("utf-8")).digest()

    # Convert bytes to bits
    bits = []
    for b in h:
        for i in range(8):
            bits.append((b >> (7 - i)) & 1)

    # Truncate or pad
    if len(bits) < max_bits:
        bits = bits + [0] * (max_bits - len(bits))
    else:
        bits = bits[:max_bits]

    return torch.tensor(bits, dtype=torch.float32)
