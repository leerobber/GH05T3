"""OmniCode — structured training turn language for genome-aligned SFT."""
from __future__ import annotations

import re
from typing import Any

from oss.forge.schemas import ForgeDomain, TrainingShard

_HEADER = re.compile(
    r"^@genome\[([^\]]+)\]\s*@domain\[([^\]]+)\]\s*@signal\[([0-9.]+)\]\s*$",
    re.MULTILINE,
)
_USER = re.compile(r"<<user>>(.*?)<<agent>>", re.DOTALL)
_AGENT = re.compile(r"<<agent>>(.*?)(?:<<end>>|$)", re.DOTALL)


def encode_turn(
    *,
    genome_id: str,
    domain: ForgeDomain,
    signal: float,
    system: str,
    user: str,
    assistant: str,
) -> str:
    """Serialize a training turn into OmniCode wire format."""
    return (
        f"@genome[{genome_id}] @domain[{domain.value}] @signal[{signal:.3f}]\n"
        f"<<user>>\n{user.strip()}\n"
        f"<<agent>>\n{assistant.strip()}\n"
        f"<<end>>\n"
    )


def decode_turn(text: str, system: str = "", source: str = "omni_lex") -> TrainingShard | None:
    """Parse OmniCode into a TrainingShard."""
    header = _HEADER.search(text)
    if not header:
        return None
    genome_id, domain_raw, _signal = header.groups()
    try:
        domain = ForgeDomain(domain_raw)
    except ValueError:
        domain = ForgeDomain.DEFAULT

    user_m = _USER.search(text)
    agent_m = _AGENT.search(text)
    if not user_m or not agent_m:
        return None

    import hashlib
    body = user_m.group(1).strip() + agent_m.group(1).strip()
    shard_id = hashlib.sha256(body.encode()).hexdigest()[:16]

    return TrainingShard(
        shard_id=shard_id,
        domain=domain,
        system=system,
        user=user_m.group(1).strip(),
        assistant=agent_m.group(1).strip(),
        source=source,
        genome_id=genome_id,
        tags=["omni_lex"],
    )


def shard_to_chatml(shard: TrainingShard) -> str:
    """Convert shard to Qwen ChatML for train_local."""
    parts = []
    if shard.system:
        parts.append(f"<|im_start|>system\n{shard.system}<|im_end|>")
    parts.append(f"<|im_start|>user\n{shard.user}<|im_end|>")
    parts.append(f"<|im_start|>assistant\n{shard.assistant}<|im_end|>")
    return "\n".join(parts)


def shard_to_omni_record(shard: TrainingShard, signal: float = 0.85) -> dict[str, Any]:
    return {
        "omni_code": encode_turn(
            genome_id=shard.genome_id or "gh05t3",
            domain=shard.domain,
            signal=signal,
            system=shard.system,
            user=shard.user,
            assistant=shard.assistant,
        ),
        "chatml": shard_to_chatml(shard),
        **shard.to_dict(),
    }