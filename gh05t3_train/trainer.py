import torch
import torch.nn as nn

from gh05t3_train.config import DEVICE, EPOCHS, BATCH_SIZE, LEARNING_RATE, GRAD_CLIP
from gh05t3_train.model_core import GH05T3MiniHybrid


def train_model(samples):
    tokenizer = samples["tokenizer"]
    token_ids = samples["token_ids"]
    raw_texts = samples["raw_texts"]

    vocab_size = tokenizer.vocab_size
    model = GH05T3MiniHybrid(vocab_size).to(DEVICE)

    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    criterion = nn.CrossEntropyLoss()

    num_samples = token_ids.size(0)
    num_batches = num_samples // BATCH_SIZE

    for epoch in range(1, EPOCHS + 1):
        total_loss = 0.0

        for batch_idx in range(num_batches):
            batch_tokens = token_ids[batch_idx * BATCH_SIZE : (batch_idx + 1) * BATCH_SIZE]
            batch_texts = raw_texts[batch_idx * BATCH_SIZE : (batch_idx + 1) * BATCH_SIZE]

            logits_answer, logits_reason = model(batch_tokens, batch_texts)

            targets = batch_tokens[:, -1].to(DEVICE)

            loss_answer = criterion(logits_answer, targets)
            loss_reason = criterion(logits_reason, targets)

            loss = loss_answer + 0.5 * loss_reason

            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
            optimizer.step()

            total_loss += loss.item()

        print(f"Epoch {epoch} complete. Loss: {total_loss:.6f}")

    return model, tokenizer
