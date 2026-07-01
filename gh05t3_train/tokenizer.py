import re
import json
from collections import Counter

class HybridTokenizer:
    def __init__(self, vocab=None, unk_token="<UNK>"):
        self.vocab = vocab or {}
        self.inv_vocab = {v: k for k, v in self.vocab.items()}
        self.unk_token = unk_token

    def basic_tokenize(self, text):
        text = text.strip()
        if not text:
            return []
        return re.findall(r"[A-Za-z0-9]+|[^A-Za-z0-9\s]", text)

    def encode(self, text):
        tokens = self.basic_tokenize(text)
        ids = []
        for tok in tokens:
            if tok in self.vocab:
                ids.append(self.vocab[tok])
            else:
                ids.append(self.vocab[self.unk_token])
        return ids

    def decode(self, ids):
        out = []
        for i in ids:
            tok = self.inv_vocab.get(i, self.unk_token)
            if tok not in ["<PAD>", "<UNK>"]:
                out.append(tok)
        return " ".join(out) if out else "<UNK>"

    @staticmethod
    def build_vocab_from_corpus(corpus_text, max_vocab_size=10000):
        tokens = []
        for line in corpus_text.splitlines():
            line = line.strip()
            if not line:
                continue
            tokens.extend(re.findall(r"[A-Za-z0-9]+|[^A-Za-z0-9\s]", line))

        counter = Counter(tokens)

        vocab = {}
        idx = 0
        vocab["<PAD>"] = idx; idx += 1
        vocab["<UNK>"] = idx; idx += 1

        for tok, _ in counter.most_common(max_vocab_size - idx):
            vocab[tok] = idx
            idx += 1

        return vocab
