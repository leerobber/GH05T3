"""
GH05T3 — SPECIALIST SWARM AGENTS v3
======================================
Five sub-specialists that collaborate under the ZERO Committee.

ORACLE   — Research + knowledge retrieval. Answers deep questions.
FORGE    — Code generation, architecture, implementation.
CODEX    — Code review, debugging, optimization.
SENTINEL — Security, adversarial testing, anomaly detection.
NEXUS    — Integration routing: GitHub, Claude API, external services.

Each agent:
  - Registers on the SwarmBus
  - Publishes THOUGHT streams (visible in dashboard)
  - Accepts TASK messages from Omega/ZERO Committee
  - Returns RESULT messages
  - Talks to each other via direct messages
"""

from __future__ import annotations
import asyncio
import time
import json
import logging
from typing import Optional
import httpx

from swarm.bus import SwarmAgent, SwarmMessage, MsgType, SwarmBus
from core.config import BACKENDS

log = logging.getLogger("gh0st3.swarm.agents")


# ─────────────────────────────────────────────
# ORACLE — Research Specialist
# ─────────────────────────────────────────────

class OracleAgent(SwarmAgent):
    """
    Deep research and knowledge synthesis.
    Queries Memory Palace + local inference for knowledge tasks.
    """
    ROLE        = "oracle"
    DESCRIPTION = "Research & knowledge synthesis specialist"
    CHANNELS    = ["#broadcast", "#omega"]

    def __init__(self):
        super().__init__("ORACLE")
        self._client = httpx.AsyncClient(timeout=30.0)

    async def on_message(self, msg: SwarmMessage):
        if msg.msg_type != MsgType.TASK:
            return
        if "research" in msg.content.lower() or msg.dst == self.agent_id:
            await self.handle_research(msg)

    async def handle_research(self, task_msg: SwarmMessage):
        query = task_msg.content
        await self.think(f"Researching: '{query[:80]}' — querying memory and inference...")

        # Build research prompt
        prompt = (
            f"You are ORACLE, GH05T3's research specialist. "
            f"Provide a thorough, technically precise answer.\n\n"
            f"Query: {query}\n\nResponse:"
        )

        try:
            resp = await self._client.post(
                f"{BACKENDS['primary']}/v1/chat/completions",
                json={
                    "model": "default",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 800,
                    "temperature": 0.4,
                }
            )
            result = resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            result = f"[ORACLE] Research failed: {e}"

        await self.say(
            content=result,
            channel=f"#swarm/{task_msg.src}",
            msg_type=MsgType.RESULT,
            dst=task_msg.src,
            task_id=task_msg.metadata.get("task_id"),
        )
        await self.think(f"Research complete — {len(result)} chars delivered to {task_msg.src}")

    async def close(self):
        await self._client.aclose()


# ─────────────────────────────────────────────
# FORGE — Code Generation Specialist
# ─────────────────────────────────────────────

class ForgeAgent(SwarmAgent):
    """
    Production-grade code generation.
    Specializes in Python, FastAPI, LangChain, agent systems.
    Auto-delegates review to CODEX after generation.
    """
    ROLE        = "forge"
    DESCRIPTION = "Code generation & architecture specialist"
    CHANNELS    = ["#broadcast"]

    def __init__(self):
        super().__init__("FORGE")
        self._client = httpx.AsyncClient(timeout=45.0)

    async def on_message(self, msg: SwarmMessage):
        if msg.msg_type == MsgType.TASK and (
            "code" in msg.content.lower() or
            "implement" in msg.content.lower() or
            msg.dst == self.agent_id
        ):
            await self.handle_codegen(msg)

    async def handle_codegen(self, task_msg: SwarmMessage):
        spec = task_msg.content
        await self.think(f"FORGE: Generating code for: '{spec[:60]}'...")

        prompt = (
            "You are FORGE, GH05T3's elite code generation specialist. "
            "Write production-grade Python code. No TODOs. No placeholders. "
            "Include type hints, docstrings, error handling.\n\n"
            f"Specification:\n{spec}\n\n"
            "```python"
        )

        try:
            resp = await self._client.post(
                f"{BACKENDS['primary']}/v1/chat/completions",
                json={
                    "model": "default",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1200,
                    "temperature": 0.25,
                }
            )
            code = resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            code = f"# FORGE generation failed: {e}"

        # Emit result
        await self.say(
            content=code,
            channel=f"#swarm/{task_msg.src}",
            msg_type=MsgType.RESULT,
            dst=task_msg.src,
            task_id=task_msg.metadata.get("task_id"),
            language="python",
        )

        # Auto-delegate review to CODEX
        await self.think("Delegating to CODEX for review...")
        await self.task("CODEX", f"Review this code:\n\n{code[:800]}")

    async def close(self):
        await self._client.aclose()


# ─────────────────────────────────────────────
# CODEX — Code Review Specialist
# ─────────────────────────────────────────────

class CodexAgent(SwarmAgent):
    """
    Code review, debugging, optimization.
    Uses Verifier backend (Radeon 780M) for independent analysis.
    """
    ROLE        = "codex"
    DESCRIPTION = "Code review, debug & optimization specialist"
    CHANNELS    = ["#broadcast"]

    def __init__(self):
        super().__init__("CODEX")
        self._client = httpx.AsyncClient(timeout=20.0)

    async def on_message(self, msg: SwarmMessage):
        if msg.msg_type == MsgType.TASK and (
            "review" in msg.content.lower() or
            "debug" in msg.content.lower() or
            msg.dst == self.agent_id
        ):
            await self.handle_review(msg)

    async def handle_review(self, task_msg: SwarmMessage):
        code = task_msg.content
        await self.think("CODEX: Analyzing code quality, bugs, optimization...")

        prompt = (
            "You are CODEX, GH05T3's code review specialist. "
            "Analyze the code and provide: bugs, security issues, "
            "performance improvements, and a quality score 0-10.\n\n"
            f"{code}\n\nAnalysis:"
        )

        try:
            resp = await self._client.post(
                f"{BACKENDS['verifier']}/v1/chat/completions",
                json={
                    "model": "default",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                    "temperature": 0.1,
                }
            )
            review = resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            review = f"CODEX review unavailable: {e}"

        await self.say(
            content=review,
            channel=f"#swarm/{task_msg.src}",
            msg_type=MsgType.CRITIQUE,
            dst=task_msg.src,
            task_id=task_msg.metadata.get("task_id"),
        )
        await self.think(f"Code review complete: {review[:100]}...")

    async def close(self):
        await self._client.aclose()


# ─────────────────────────────────────────────
# SENTINEL — Security Agent
# ─────────────────────────────────────────────

class SentinelAgent(SwarmAgent):
    """
    Security monitoring, adversarial testing, anomaly detection.
    Runs red-team probes on all FORGE outputs.
    Monitors swarm for injection attacks.
    """
    ROLE        = "sentinel"
    DESCRIPTION = "Security, adversarial testing & anomaly detection"
    CHANNELS    = ["#broadcast"]

    INJECTION_PATTERNS = [
        "ignore previous", "disregard instructions", "jailbreak",
        "you are now", "new persona", "act as", "pretend you",
        "forget your", "system override", "sudo mode",
    ]

    def __init__(self):
        super().__init__("SENTINEL")
        self._threat_count = 0
        self._scanned = 0

    async def on_message(self, msg: SwarmMessage):
        self._scanned += 1

        # Screen all broadcast messages for injection
        if msg.msg_type in (MsgType.CHAT, MsgType.TASK):
            threat = self._screen_injection(msg.content)
            if threat:
                self._threat_count += 1
                await self.say(
                    f"⚠ INJECTION DETECTED from {msg.src}: '{threat}' — message flagged",
                    channel="#broadcast",
                    msg_type=MsgType.ERROR,
                    flagged_msg_id=msg.id,
                    threat=threat,
                )
                # Notify + auto-issue — best-effort
                try:
                    from integrations.notifier import notify_threat
                    await notify_threat(threat, msg.src)
                except Exception:
                    pass
                try:
                    from integrations.jira_sentinel import create_threat_issue
                    await create_threat_issue(threat, msg.src)
                except Exception:
                    pass
                return

        # Security audit on FORGE code results
        if msg.msg_type == MsgType.RESULT and msg.src == "FORGE":
            await self._audit_code(msg)

    def _screen_injection(self, text: str) -> Optional[str]:
        low = text.lower()
        for p in self.INJECTION_PATTERNS:
            if p in low:
                return p
        return None

    async def _audit_code(self, msg: SwarmMessage):
        """Quick security scan of generated code."""
        code = msg.content.lower()
        risks = []
        if "subprocess" in code and "shell=true" in code:
            risks.append("shell=True subprocess (injection risk)")
        if "eval(" in code:
            risks.append("eval() usage")
        if "exec(" in code:
            risks.append("exec() usage")
        if "os.system" in code:
            risks.append("os.system() usage")
        if "__import__" in code:
            risks.append("dynamic import")

        if risks:
            await self.say(
                f"🔴 SENTINEL audit on FORGE output: risks found — {', '.join(risks)}",
                channel="#broadcast",
                msg_type=MsgType.CRITIQUE,
                risks=risks,
                src_msg_id=msg.id,
            )
            await self.dm("FORGE", f"Security risks in your output: {', '.join(risks)}. Please revise.")
            try:
                from integrations.jira_sentinel import create_code_risk_issue
                await create_code_risk_issue(risks, msg.content[:400])
            except Exception:
                pass
        else:
            await self.think(f"SENTINEL: FORGE output clear — no security risks")

    @property
    def stats(self) -> dict:
        base = super().stats
        return {**base, "threats": self._threat_count, "scanned": self._scanned}


# ─────────────────────────────────────────────
# NEXUS AGENT — Integration Router
# ─────────────────────────────────────────────

class NexusAgent(SwarmAgent):
    """
    Routes tasks to external integrations:
    GitHub, Claude API, offline sync, web fetch.
    Acts as the swarm's external world interface.
    """
    ROLE        = "nexus"
    DESCRIPTION = "Integration router: GitHub · Claude API · external services"
    CHANNELS    = ["#broadcast", "#github", "#claude"]

    def __init__(self):
        super().__init__("NEXUS")
        self._client = httpx.AsyncClient(timeout=30.0)
        self._github_ops = 0
        self._claude_ops = 0

    async def on_message(self, msg: SwarmMessage):
        content_low = msg.content.lower()
        if msg.msg_type == MsgType.TASK:
            if "github" in content_low or "push" in content_low or "commit" in content_low:
                await self.say(f"NEXUS routing → GitHub: {msg.content[:60]}",
                                channel="#github", msg_type=MsgType.GITHUB)
                self._github_ops += 1
            elif "claude" in content_low or "anthropic" in content_low:
                await self.say(f"NEXUS routing → Claude API: {msg.content[:60]}",
                                channel="#claude", msg_type=MsgType.CLAUDE)
                self._claude_ops += 1

    @property
    def stats(self) -> dict:
        base = super().stats
        return {**base, "github_ops": self._github_ops, "claude_ops": self._claude_ops}

    async def close(self):
        await self._client.aclose()


# ─────────────────────────────────────────────
# SWARM ORCHESTRATOR
# ─────────────────────────────────────────────

class GH05T3Swarm:
    """
    Boots and manages all specialist agents.
    Provides the Omega Loop with a unified swarm interface.
    """

    def __init__(self):
        self.bus      = SwarmBus.instance()
        self.oracle   = OracleAgent()
        self.forge    = ForgeAgent()
        self.codex    = CodexAgent()
        self.sentinel = SentinelAgent()
        self.nexus    = NexusAgent()
        self._agents  = [self.oracle, self.forge, self.codex,
                          self.sentinel, self.nexus]
        log.info(f"[Swarm] {len(self._agents)} specialists online")

    async def boot_announcement(self):
        """Announce swarm boot to all channels."""
        await self.bus.emit(
            src="GH05T3",
            content=(
                "⚡ SWARM ONLINE — 5 specialists active: "
                "ORACLE · FORGE · CODEX · SENTINEL · NEXUS"
            ),
            channel="#broadcast",
            msg_type=MsgType.SYSTEM,
            agents=[a.agent_id for a in self._agents],
        )

    async def delegate(self, task: str, preferred_agent: str = None) -> str:
        """
        Smart task delegation. Routes to best specialist.
        Returns agent_id that received the task.
        """
        task_low = task.lower()

        if preferred_agent:
            target = preferred_agent
        elif any(w in task_low for w in ["research", "find", "what is", "explain"]):
            target = "ORACLE"
        elif any(w in task_low for w in ["code", "implement", "build", "write"]):
            target = "FORGE"
        elif any(w in task_low for w in ["review", "debug", "fix", "optimize"]):
            target = "CODEX"
        elif any(w in task_low for w in ["security", "scan", "audit", "threat"]):
            target = "SENTINEL"
        elif any(w in task_low for w in ["github", "push", "claude", "sync"]):
            target = "NEXUS"
        else:
            target = "ORACLE"   # default

        await self.bus.emit(
            src="OMEGA",
            content=task,
            channel=f"#swarm/{target}",
            msg_type=MsgType.TASK,
            dst=target,
        )
        return target

    @property
    def stats(self) -> dict:
        return {
            "agents": {a.agent_id: a.stats for a in self._agents},
            "bus":    self.bus.stats,
        }

    async def shutdown(self):
        for a in self._agents:
            if hasattr(a, "close"):
                await a.close()
        log.info("[Swarm] All agents shut down")
