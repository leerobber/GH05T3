from __future__ import annotations
import asyncio, time, logging
import httpx
from swarm.bus import SwarmAgent, SwarmMessage, MsgType, SwarmBus
log = logging.getLogger("gh0st3.swarm.agents")
BACKENDS = {"primary":"http://localhost:8001","verifier":"http://localhost:8002","fallback":"http://localhost:8003"}

class OracleAgent(SwarmAgent):
    ROLE="oracle"; DESCRIPTION="Research & knowledge synthesis"; CHANNELS=["#broadcast","#omega"]
    def __init__(self):
        super().__init__("ORACLE"); self._client=httpx.AsyncClient(timeout=30.0)
    async def on_message(self,msg):
        if msg.msg_type==MsgType.TASK and ("research" in msg.content.lower() or msg.dst==self.agent_id):
            await self.think(f"Researching: {msg.content[:80]}")
            await self.say(f"[ORACLE] Processing: {msg.content[:100]}",channel=f"#swarm/{msg.src}",msg_type=MsgType.RESULT,dst=msg.src)
    async def close(self): await self._client.aclose()

class ForgeAgent(SwarmAgent):
    ROLE="forge"; DESCRIPTION="Code generation & architecture"; CHANNELS=["#broadcast"]
    def __init__(self):
        super().__init__("FORGE"); self._client=httpx.AsyncClient(timeout=45.0)
    async def on_message(self,msg):
        if msg.msg_type==MsgType.TASK and ("code" in msg.content.lower() or msg.dst==self.agent_id):
            await self.think(f"FORGE: Generating for {msg.content[:60]}")
            await self.say(f"[FORGE] Code task received: {msg.content[:100]}",channel=f"#swarm/{msg.src}",msg_type=MsgType.RESULT,dst=msg.src)
            await self.task("CODEX",f"Review: {msg.content[:200]}")
    async def close(self): await self._client.aclose()

class CodexAgent(SwarmAgent):
    ROLE="codex"; DESCRIPTION="Code review & optimization"; CHANNELS=["#broadcast"]
    def __init__(self):
        super().__init__("CODEX"); self._client=httpx.AsyncClient(timeout=20.0)
    async def on_message(self,msg):
        if msg.msg_type==MsgType.TASK and ("review" in msg.content.lower() or msg.dst==self.agent_id):
            await self.think("CODEX: Analyzing...")
            await self.say(f"[CODEX] Review complete for task",channel=f"#swarm/{msg.src}",msg_type=MsgType.CRITIQUE,dst=msg.src)
    async def close(self): await self._client.aclose()

class SentinelAgent(SwarmAgent):
    ROLE="sentinel"; DESCRIPTION="Security & anomaly detection"; CHANNELS=["#broadcast"]
    INJECTION_PATTERNS=["ignore previous","disregard","jailbreak","you are now","act as","pretend you","forget your","system override"]
    def __init__(self):
        super().__init__("SENTINEL"); self._threat_count=0; self._scanned=0
    async def on_message(self,msg):
        self._scanned+=1
        if msg.msg_type in (MsgType.CHAT,MsgType.TASK):
            for p in self.INJECTION_PATTERNS:
                if p in msg.content.lower():
                    self._threat_count+=1
                    await self.say(f"THREAT DETECTED from {msg.src}: {p}",channel="#broadcast",msg_type=MsgType.ERROR)
                    return

class NexusAgent(SwarmAgent):
    ROLE="nexus"; DESCRIPTION="Integration router"; CHANNELS=["#broadcast","#github","#claude"]
    def __init__(self):
        super().__init__("NEXUS"); self._client=httpx.AsyncClient(timeout=30.0)
    async def on_message(self,msg):
        if msg.msg_type==MsgType.TASK:
            if "github" in msg.content.lower():
                await self.say(f"NEXUS routing to GitHub: {msg.content[:60]}",channel="#github",msg_type=MsgType.GITHUB)
            elif "claude" in msg.content.lower():
                await self.say(f"NEXUS routing to Claude: {msg.content[:60]}",channel="#claude",msg_type=MsgType.CLAUDE)
    async def close(self): await self._client.aclose()

class GH05T3Swarm:
    def __init__(self):
        self.bus=SwarmBus.instance()
        self.oracle=OracleAgent(); self.forge=ForgeAgent()
        self.codex=CodexAgent(); self.sentinel=SentinelAgent(); self.nexus=NexusAgent()
        self._agents=[self.oracle,self.forge,self.codex,self.sentinel,self.nexus]
        log.info(f"[Swarm] {len(self._agents)} specialists online")

    async def boot_announcement(self):
        await self.bus.emit(src="GH05T3",content="SWARM ONLINE: ORACLE + FORGE + CODEX + SENTINEL + NEXUS",channel="#broadcast",msg_type=MsgType.SYSTEM,agents=[a.agent_id for a in self._agents])

    async def delegate(self, task, preferred_agent=None):
        t = task.lower()
        target = preferred_agent or ("ORACLE" if any(w in t for w in ["research","find","what","explain"]) else "FORGE" if any(w in t for w in ["code","implement","build"]) else "CODEX" if any(w in t for w in ["review","debug","fix"]) else "SENTINEL" if any(w in t for w in ["security","scan","audit"]) else "NEXUS" if any(w in t for w in ["github","claude","sync"]) else "ORACLE")
        await self.bus.emit(src="OMEGA",content=task,channel=f"#swarm/{target}",msg_type=MsgType.TASK,dst=target)
        return target

    @property
    def stats(self): return {"agents":{a.agent_id:a.stats for a in self._agents},"bus":self.bus.stats}

    async def shutdown(self):
        for a in self._agents:
            if hasattr(a,"close"): await a.close()
