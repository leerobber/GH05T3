import torch
import torch.nn as nn

from gh05t3_train.sb_core import text_to_binary_embedding
from gh05t3_train.config import DEVICE


class GH05T3MiniHybrid(nn.Module):
    def __init__(self, vocab_size: int, embed_dim: int = 128, num_heads: int = 4, num_layers: int = 2):
        super().__init__()

        self.vocab_size = vocab_size
        self.embed_dim = embed_dim

        self.embed = nn.Embedding(vocab_size, embed_dim)

        # Large positional embedding table to avoid index errors
        self.pos_embed = nn.Embedding(2048, embed_dim)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=num_heads,
            dim_feedforward=embed_dim * 4,
            batch_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        self.binary_fc = nn.Linear(128, embed_dim)

        self.ln = nn.LayerNorm(embed_dim)
        self.fc_answer = nn.Linear(embed_dim, vocab_size)
        self.fc_reason = nn.Linear(embed_dim, vocab_size)

    def forward(self, token_ids: torch.Tensor, raw_texts):
        token_ids = token_ids.to(DEVICE)
        batch_size, seq_len = token_ids.shape

        x = self.embed(token_ids)

        binary_vecs = []
        for t in raw_texts:
            binary_vecs.append(text_to_binary_embedding(t, max_bits=128))

        binary_tensor = torch.stack(binary_vecs).to(x.device)
        binary_emb = self.binary_fc(binary_tensor)
        binary_token = binary_emb.unsqueeze(1)

        x = torch.cat([binary_token, x], dim=1)

        total_len = x.size(1)
        positions = torch.arange(total_len, device=x.device).unsqueeze(0).expand(batch_size, total_len)
        pos = self.pos_embed(positions)

        x = x + pos

        x = self.encoder(x)

        summary = x[:, -1, :]
        summary = self.ln(summary)

        logits_answer = self.fc_answer(summary)
        logits_reason = self.fc_reason(summary)

        return logits_answer, logits_reason
