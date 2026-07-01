import json
import torch
import torch.nn.functional as F
from gh05t3_train.config import *
from gh05t3_train.tokenizer import HybridTokenizer
from gh05t3_train.model_core import GH05T3MiniHybrid

def load_vocab_file():
    vocab_path = f"{CHECKPOINT_DIR}/vocab.json"
    with open(vocab_path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_model_and_tokenizer():
    vocab = load_vocab_file()
    tokenizer = HybridTokenizer(vocab=vocab)
    vocab_size = len(tokenizer.vocab)

    model = GH05T3MiniHybrid(vocab_size=vocab_size).to(DEVICE)
    checkpoint_path = f"{CHECKPOINT_DIR}/{MODEL_NAME}-hybrid.pt"
    state = torch.load(checkpoint_path, map_location=DEVICE)
    model.load_state_dict(state)
    model.eval()

    return model, tokenizer

def sample_next_token(logits, tokenizer, temperature=0.8, top_k=20):
    pad_id = tokenizer.vocab.get("<PAD>", 0)
    unk_id = tokenizer.vocab.get("<UNK>", 1)

    logits[pad_id] = -1e9
    logits[unk_id] = -1e9

    if top_k is not None and top_k > 0:
        values, indices = torch.topk(logits, k=min(top_k, logits.size(-1)))
        mask = torch.full_like(logits, -1e9)
        mask[indices] = values
        logits = mask

    logits = logits / max(temperature, 1e-3)
    probs = F.softmax(logits, dim=-1)
    next_id = torch.multinomial(probs, num_samples=1).item()
    return next_id

def generate_response(model, tokenizer, prompt, max_new_tokens=20):
    token_ids = tokenizer.encode(prompt)
    token_ids = token_ids[:MAX_SEQ_LEN]
    pad_len = MAX_SEQ_LEN - len(token_ids)
    if pad_len > 0:
        token_ids = token_ids + [tokenizer.vocab.get("<PAD>", 0)] * pad_len

    token_tensor = torch.tensor([token_ids], dtype=torch.long).to(DEVICE)
    raw_texts = [prompt]

    generated_ids = []

    with torch.no_grad():
        for _ in range(max_new_tokens):
            logits = model(token_tensor, raw_texts)
            last_logits = logits[0, -1]
            next_id = sample_next_token(last_logits, tokenizer)
            generated_ids.append(next_id)

            token_tensor = torch.roll(token_tensor, shifts=-1, dims=1)
            token_tensor[0, -1] = next_id

    decoded = tokenizer.decode(generated_ids)
    print(f"[DEBUG] generated_ids={generated_ids}, decoded={decoded}")
    return decoded

def main():
    print("[GH05T3 CONFIG] Using device:", DEVICE)

    model, tokenizer = load_model_and_tokenizer()

    print("=== GH05T3 English Hybrid Autoregressive Inference ===")
    print("Type 'exit' to quit.")

    while True:
        prompt = input("\nYou: ")
        if prompt.lower() == "exit":
            break

        response = generate_response(model, tokenizer, prompt, max_new_tokens=20)
        print("GH05T3:", response)

if __name__ == "__main__":
    main()
