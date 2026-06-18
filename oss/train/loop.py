"""Sovereign training loop — pure PyTorch step, no SFTTrainer."""
from __future__ import annotations

import logging
import math
import random
from typing import Any

from oss.train.constitution import assert_loss_healthy
from oss.train.tokenize import TokenizedExample, collate_batch

LOG = logging.getLogger("oss.train.loop")


def _cosine_lr(step: int, warmup: int, total: int, base_lr: float) -> float:
    if step < warmup:
        return base_lr * (step + 1) / max(1, warmup)
    progress = (step - warmup) / max(1, total - warmup)
    return base_lr * 0.5 * (1.0 + math.cos(math.pi * progress))


class SovereignLoop:
    """Micro-batch training with gradient accumulation."""

    def __init__(
        self,
        model,
        tokenizer,
        tokenized: list[TokenizedExample],
        *,
        max_steps: int,
        learning_rate: float,
        max_grad_norm: float,
        batch_size: int,
        grad_accum: int,
        warmup_steps: int,
        use_bf16: bool,
        log_every: int = 10,
        seed: int = 42,
    ) -> None:
        self.model = model
        self.tokenizer = tokenizer
        self.tokenized = tokenized
        self.max_steps = max_steps
        self.lr = learning_rate
        self.max_grad_norm = max_grad_norm
        self.batch_size = max(1, batch_size)
        self.grad_accum = max(1, grad_accum)
        self.warmup = warmup_steps
        self.use_bf16 = use_bf16
        self.log_every = log_every
        self.rng = random.Random(seed)

        import torch
        self.torch = torch
        trainable = [p for p in model.parameters() if p.requires_grad]
        self.optimizer = torch.optim.AdamW(trainable, lr=learning_rate, weight_decay=0.01)
        self.scaler = None if use_bf16 else torch.cuda.amp.GradScaler()

    def _sample_batch(self) -> list[TokenizedExample]:
        return self.rng.choices(self.tokenized, k=self.batch_size)

    def run(self) -> dict[str, Any]:
        torch = self.torch
        self.model.train()
        loss_history: list[float] = []
        running = 0.0
        accum_count = 0
        global_loss = 0.0

        for step in range(1, self.max_steps + 1):
            lr = _cosine_lr(step, self.warmup, self.max_steps, self.lr)
            for pg in self.optimizer.param_groups:
                pg["lr"] = lr

            batch = collate_batch(self.tokenizer, self._sample_batch())
            device = next(self.model.parameters()).device
            batch = {k: v.to(device) for k, v in batch.items()}

            amp_dtype = torch.bfloat16 if self.use_bf16 else torch.float16
            with torch.amp.autocast("cuda", enabled=True, dtype=amp_dtype):
                outputs = self.model(**batch)
                micro_loss = outputs.loss

            assert_loss_healthy(micro_loss.item(), step=step)
            scaled = micro_loss / self.grad_accum

            if self.scaler:
                self.scaler.scale(scaled).backward()
            else:
                scaled.backward()

            running += micro_loss.item()
            accum_count += 1

            if accum_count >= self.grad_accum:
                if self.scaler:
                    self.scaler.unscale_(self.optimizer)
                torch.nn.utils.clip_grad_norm_(
                    [p for p in self.model.parameters() if p.requires_grad],
                    self.max_grad_norm,
                )
                if self.scaler:
                    self.scaler.step(self.optimizer)
                    self.scaler.update()
                else:
                    self.optimizer.step()
                self.optimizer.zero_grad(set_to_none=True)
                global_loss = running / accum_count
                loss_history.append(global_loss)
                running = 0.0
                accum_count = 0

                if step % self.log_every == 0 or step == 1:
                    LOG.info("step %d/%d  loss=%.4f  lr=%.2e", step, self.max_steps, global_loss, lr)

        if accum_count > 0:
            # Flush partial accumulation — same formula as optimizer steps
            if self.scaler:
                self.scaler.unscale_(self.optimizer)
            self.torch.nn.utils.clip_grad_norm_(
                [p for p in self.model.parameters() if p.requires_grad],
                self.max_grad_norm,
            )
            if self.scaler:
                self.scaler.step(self.optimizer)
                self.scaler.update()
            else:
                self.optimizer.step()
            self.optimizer.zero_grad(set_to_none=True)
            loss_history.append(running / accum_count)

        # Use rolling mean — last partial micro-batch must not dominate final verdict
        tail = loss_history[-10:] if loss_history else [0.0]
        final = sum(tail) / len(tail)
        return {"final_loss": final, "steps": self.max_steps, "loss_history": loss_history}