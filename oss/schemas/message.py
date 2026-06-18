"""Protocol Layer — SwarmBus and orchestration message contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MessageType(str, Enum):
    CHAT = "chat"
    TASK = "task"
    RESULT = "result"
    THOUGHT = "thought"
    CRITIQUE = "critique"
    VERDICT = "verdict"
    KAIROS = "kairos"
    GITHUB = "github"
    CLAUDE = "claude"
    SYSTEM = "system"
    HEARTBEAT = "heartbeat"
    ERROR = "error"


@dataclass
class BusMessage:
    """Canonical SwarmBus message — maps to backend.swarm.bus.SwarmMessage."""

    channel: str = "#broadcast"
    msg_type: MessageType = MessageType.CHAT
    src: str = "system"
    dst: str = "*"
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    message_id: str = ""
    timestamp: float = 0.0
    seq: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.message_id,
            "channel": self.channel,
            "msg_type": self.msg_type.value,
            "src": self.src,
            "dst": self.dst,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "seq": self.seq,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BusMessage:
        raw_type = data.get("msg_type", MessageType.CHAT.value)
        try:
            msg_type = MessageType(raw_type)
        except ValueError:
            msg_type = MessageType.SYSTEM
        return cls(
            message_id=str(data.get("id", "")),
            channel=str(data.get("channel", "#broadcast")),
            msg_type=msg_type,
            src=str(data.get("src", "system")),
            dst=str(data.get("dst", "*")),
            content=str(data.get("content", "")),
            metadata=dict(data.get("metadata") or {}),
            timestamp=float(data.get("timestamp", 0.0)),
            seq=int(data.get("seq", 0)),
        )

    @classmethod
    def from_swarm_bus(cls, msg: Any) -> BusMessage:
        """Convert a backend SwarmMessage instance."""
        return cls(
            message_id=getattr(msg, "id", ""),
            channel=getattr(msg, "channel", "#broadcast"),
            msg_type=MessageType(getattr(msg.msg_type, "value", msg.msg_type)),
            src=getattr(msg, "src", "system"),
            dst=getattr(msg, "dst", "*"),
            content=getattr(msg, "content", ""),
            metadata=dict(getattr(msg, "metadata", {}) or {}),
            timestamp=float(getattr(msg, "timestamp", 0.0)),
            seq=int(getattr(msg, "seq", 0)),
        )

    def to_swarm_kwargs(self) -> dict[str, Any]:
        """Keyword args for SwarmMessage construction in backend."""
        return {
            "channel": self.channel,
            "msg_type": self.msg_type.value,
            "src": self.src,
            "dst": self.dst,
            "content": self.content,
            "metadata": self.metadata,
        }