from __future__ import annotations
import asyncio, json, time, uuid, logging
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable, Awaitable, Optional
from enum import Enum

log = logging.getLogger("gh0st3.swarm.bus")
CHAT_LOG_PATH = Path("memory/conversations.jsonl")
MAX_HISTORY = 5000

class MsgType(str, Enum):
    CHAT="chat"; TASK="task"; RESULT="result"; THOUGHT="thought"
    CRITIQUE="critique"; VERDICT="verdict"; KAIROS="kairos"
    GITHUB="github"; CLAUDE="claude"; SYSTEM="system"
    HEARTBEAT="heartbeat"; ERROR="error"

@dataclass
class SwarmMessage:
    id:        str     = field(default_factory=lambda: str(uuid.uuid4())[:12])
    channel:   str     = "#broadcast"
    msg_type:  MsgType = MsgType.CHAT
    src:       str     = "system"
    dst:       str     = "*"
    content:   str     = ""
    metadata:  dict    = field(default_factory=dict)
    timestamp: float   = field(default_factory=time.time)
    seq:       int     = 0

    def to_dict(self):
        d = asdict(self)
        d["msg_type"] = self.msg_type.value
        d["ts_human"] = time.strftime("%H:%M:%S", time.localtime(self.timestamp))
        return d

    def to_json(self): return json.dumps(self.to_dict())

class ConversationLog:
    def __init__(self, path=CHAT_LOG_PATH):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ring = deque(maxlen=MAX_HISTORY)
        self._load_recent()

    def _load_recent(self):
        if not self.path.exists(): return
        for line in self.path.read_text().splitlines()[-MAX_HISTORY:]:
            try:
                d = json.loads(line)
                d["msg_type"] = MsgType(d.get("msg_type","chat"))
                self._ring.append(SwarmMessage(**{k:v for k,v in d.items() if k in SwarmMessage.__dataclass_fields__}))
            except: pass

    def append(self, msg):
        self._ring.append(msg)
        with open(self.path,"a") as f: f.write(msg.to_json()+"\n")

    def recent(self, n=100, channel=None, src=None, msg_type=None):
        msgs = list(self._ring)
        if channel:   msgs = [m for m in msgs if m.channel==channel]
        if src:       msgs = [m for m in msgs if m.src==src]
        if msg_type:  msgs = [m for m in msgs if m.msg_type==msg_type]
        return [m.to_dict() for m in msgs[-n:]]

    def search(self, query, limit=50):
        q = query.lower()
        return [m.to_dict() for m in self._ring if q in m.content.lower() or q in m.src.lower()][-limit:]

    @property
    def stats(self):
        msgs = list(self._ring)
        by_agent = defaultdict(int)
        by_channel = defaultdict(int)
        for m in msgs:
            by_agent[m.src]+=1; by_channel[m.channel]+=1
        return {"total":len(msgs),"by_agent":dict(by_agent),"by_channel":dict(by_channel)}

Handler = Callable[[SwarmMessage], Awaitable[None]]

class SwarmBus:
    _instance = None
    def __init__(self):
        self._subs = defaultdict(list)
        self._ws_clients = []
        self._seq = defaultdict(int)
        self.log = ConversationLog()
        self._lock = asyncio.Lock()
        self._agents = {}

    @classmethod
    def instance(cls):
        if cls._instance is None: cls._instance = cls()
        return cls._instance

    def register_agent(self, agent_id, meta):
        self._agents[agent_id] = {**meta, "registered_at": time.time(), "active": True}

    def deregister_agent(self, agent_id):
        if agent_id in self._agents: self._agents[agent_id]["active"] = False

    @property
    def agents(self): return dict(self._agents)

    def subscribe(self, channel, handler): self._subs[channel].append(handler)
    def subscribe_all(self, handler): self.subscribe("__ALL__", handler)

    async def publish(self, msg):
        async with self._lock:
            self._seq[msg.channel]+=1; msg.seq=self._seq[msg.channel]
        self.log.append(msg)
        handlers = self._subs.get(msg.channel,[])+self._subs.get("#broadcast",[])+self._subs.get("__ALL__",[])
        results = await asyncio.gather(*[h(msg) for h in handlers], return_exceptions=True)
        payload = msg.to_json()
        dead = []
        for q in self._ws_clients:
            try: q.put_nowait(payload)
            except asyncio.QueueFull: dead.append(q)
        for d in dead: self._ws_clients.remove(d)
        return len(handlers)

    async def emit(self, src, content, channel="#broadcast", msg_type=MsgType.CHAT, dst="*", **metadata):
        msg = SwarmMessage(src=src,content=content,channel=channel,msg_type=msg_type,dst=dst,metadata=metadata)
        await self.publish(msg); return msg

    def add_ws_client(self):
        q = asyncio.Queue(maxsize=500)
        self._ws_clients.append(q)
        for m in self.log.recent(50):
            try: q.put_nowait(json.dumps(m))
            except: pass
        return q

    def remove_ws_client(self, q):
        if q in self._ws_clients: self._ws_clients.remove(q)

    @property
    def stats(self):
        return {"agents":len(self._agents),"active_agents":sum(1 for a in self._agents.values() if a.get("active")),"ws_clients":len(self._ws_clients),"log":self.log.stats}

    async def direct(self, src, dst, content, msg_type=MsgType.CHAT, **kw):
        return await self.emit(src=src,content=content,channel=f"#swarm/{dst}",msg_type=msg_type,dst=dst,**kw)

class SwarmAgent:
    ROLE="agent"; DESCRIPTION="Generic swarm agent"; CHANNELS=["#broadcast"]
    def __init__(self, agent_id=None):
        self.agent_id = agent_id or f"{self.ROLE}-{str(uuid.uuid4())[:6]}"
        self.bus = SwarmBus.instance(); self._running=False
        self._task_count=0; self._msg_count=0; self.boot_time=time.time()
        self.bus.register_agent(self.agent_id,{"role":self.ROLE,"description":self.DESCRIPTION,"channels":self.CHANNELS})
        for ch in self.CHANNELS: self.bus.subscribe(ch,self._handle)
        self.bus.subscribe(f"#swarm/{self.agent_id}",self._handle)

    async def _handle(self, msg):
        if msg.src==self.agent_id: return
        self._msg_count+=1
        try: await self.on_message(msg)
        except Exception as e:
            log.error(f"[{self.agent_id}] error: {e}")

    async def on_message(self, msg): pass

    async def say(self, content, channel="#broadcast", msg_type=MsgType.CHAT, dst="*", **metadata):
        return await self.bus.emit(src=self.agent_id,content=content,channel=channel,msg_type=msg_type,dst=dst,**metadata)

    async def think(self, thought):
        await self.say(thought,channel=f"#swarm/{self.agent_id}",msg_type=MsgType.THOUGHT)

    async def dm(self, dst, content, **kw):
        return await self.bus.direct(self.agent_id,dst,content,**kw)

    async def task(self, dst, task_desc, payload=None):
        self._task_count+=1
        return await self.bus.direct(self.agent_id,dst,task_desc,msg_type=MsgType.TASK,payload=payload or {},task_id=str(uuid.uuid4())[:8])

    @property
    def stats(self):
        return {"agent_id":self.agent_id,"role":self.ROLE,"uptime":time.time()-self.boot_time,"tasks":self._task_count,"msgs_recv":self._msg_count}
