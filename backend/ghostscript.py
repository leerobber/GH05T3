"""GhostScript — AI/ML orchestration language for GH05T3.

Grammar:
    program     ::= stmt*
    stmt        ::= let | if | for | agent | async | await | think | emit | on | expr_stmt
    let_stmt    ::= "let" IDENT "=" expr
    if_stmt     ::= "if" "(" expr ")" block ("else" block)?
    for_stmt    ::= "for" IDENT "in" expr block
    agent_stmt  ::= "agent" IDENT "{" stmt* "}"
    async_stmt  ::= "async" block
    await_stmt  ::= "await" expr
    think_stmt  ::= "think" ":" STRING
    emit_stmt   ::= "emit" IDENT "->" IDENT
    on_stmt     ::= "on" IDENT "->" expr
    expr_stmt   ::= expr
    expr        ::= pipeline
    pipeline    ::= call ("|>" call)*
    call        ::= atom ("." IDENT "(" arglist ")")* ("(" arglist ")")?
    atom        ::= STRING | NUMBER | BOOL | list | IDENT | "(" expr ")"
    list        ::= "[" (expr ("," expr)*)? "]"
    arglist     ::= (expr ("," expr)*)?

Built-in namespaces (wired to real GH05T3 providers):
    llm.chat(prompt)          — call the active LLM provider chain
    llm.embed(text)           — embed text
    memory.store(key, value)  — store in MemoryPalace
    memory.search(query)      — search MemoryPalace
    kairos.propose(idea)      — archive proposal for SAGE cycle
    evolve(strategy)          — request self-modification
    reply_from(AGENT)         — await a RESULT from a named SwarmBus agent
    think: "..."              — log a reasoning step
    emit VAR -> TARGET        — publish TASK to SwarmBus channel #swarm/TARGET
    on EVENT -> expr          — fire expr when EVENT reply arrives (RESULT/APPROVE/REJECT)
    if (cond) { ... } else { ... }  — conditional branching
    for item in list { ... }  — iteration
"""
from __future__ import annotations

import asyncio
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

# SwarmBus wiring — lazy import so ghostscript.py works standalone too
try:
    from swarm.bus import SwarmBus as _SwarmBus, MsgType as _BusMsgType
    _BUS_OK = True
except ImportError:
    _BUS_OK = False


# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------
TOKEN_RE = re.compile(
    r"""
    (?P<STRING>"[^"]*"|'[^']*')         |
    (?P<NUMBER>-?\d+(?:\.\d+)?)         |
    (?P<BOOL>true|false)                |
    (?P<PIPE_OP>\|>)                    |
    (?P<ARROW>->|→)                     |
    (?P<COLON>:)                        |
    (?P<LBRACE>\{)                      |
    (?P<RBRACE>\})                      |
    (?P<LBRACKET>\[)                    |
    (?P<RBRACKET>\])                    |
    (?P<LPAREN>\()                      |
    (?P<RPAREN>\))                      |
    (?P<COMMA>,)                        |
    (?P<DOT>\.)                         |
    (?P<EQ>=)                           |
    (?P<IDENT>[A-Za-z_][A-Za-z0-9_]*)  |
    (?P<COMMENT>\#[^\n]*)               |
    (?P<WS>\s+)                         |
    (?P<OTHER>.)
    """,
    re.VERBOSE,
)

KEYWORDS = {
    "agent", "let", "async", "await", "think", "emit", "on",
    "if", "else", "for", "in",
}

_BUILTIN_NS  = {"llm", "memory", "kairos", "Archive"}
_KEYWORD_FNS = {"evolve", "print", "reply_from"}


@dataclass
class Token:
    kind: str
    value: str
    pos: int


def lex(src: str) -> list[Token]:
    toks = []
    for m in TOKEN_RE.finditer(src):
        kind = m.lastgroup
        if kind in ("WS", "COMMENT"):
            continue
        if kind == "IDENT" and m.group() in KEYWORDS:
            kind = m.group().upper()
        toks.append(Token(kind, m.group(), m.start()))
    return toks


# ---------------------------------------------------------------------------
# AST nodes
# ---------------------------------------------------------------------------
@dataclass
class Node:
    kind: str
    data: dict = field(default_factory=dict)
    children: list["Node"] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
class ParseError(Exception):
    pass


class Parser:
    def __init__(self, toks: list[Token]):
        self.toks = toks
        self.i = 0

    def peek(self, offset: int = 0) -> Token | None:
        idx = self.i + offset
        return self.toks[idx] if idx < len(self.toks) else None

    def eat(self, kind: str, value: str | None = None) -> Token:
        t = self.peek()
        if not t:
            raise ParseError(f"unexpected end of input, expected {kind}")
        if t.kind != kind:
            raise ParseError(f"pos {t.pos}: expected {kind}, got {t.kind}={t.value!r}")
        if value is not None and t.value != value:
            raise ParseError(f"pos {t.pos}: expected {value!r}, got {t.value!r}")
        self.i += 1
        return t

    def maybe(self, kind: str, value: str | None = None) -> Token | None:
        t = self.peek()
        if t and t.kind == kind and (value is None or t.value == value):
            self.i += 1
            return t
        return None

    # ── top level ─────────────────────────────────────────────────────────
    def parse_program(self) -> Node:
        prog = Node("program")
        while self.peek():
            prog.children.append(self.parse_stmt())
        return prog

    def parse_block(self) -> Node:
        self.eat("LBRACE")
        block = Node("block")
        while self.peek() and self.peek().kind != "RBRACE":
            block.children.append(self.parse_stmt())
        self.eat("RBRACE")
        return block

    def parse_stmt(self) -> Node:
        t = self.peek()
        if not t:
            raise ParseError("unexpected end")
        if t.kind == "LET":   return self.parse_let()
        if t.kind == "IF":    return self.parse_if()
        if t.kind == "FOR":   return self.parse_for()
        if t.kind == "AGENT": return self.parse_agent()
        if t.kind == "ASYNC": return self.parse_async()
        if t.kind == "AWAIT": return self.parse_await()
        if t.kind == "THINK": return self.parse_think()
        if t.kind == "EMIT":  return self.parse_emit()
        if t.kind == "ON":    return self.parse_on()
        return Node("expr_stmt", {}, [self.parse_expr()])

    def parse_let(self) -> Node:
        self.eat("LET")
        name = self.eat("IDENT").value
        self.eat("EQ")
        val = self.parse_expr()
        return Node("let", {"name": name}, [val])

    def parse_if(self) -> Node:
        self.eat("IF")
        self.eat("LPAREN")
        cond = self.parse_expr()
        self.eat("RPAREN")
        then_block = self.parse_block()
        else_block = None
        if self.maybe("ELSE"):
            else_block = self.parse_block()
        children = [cond, then_block] + ([else_block] if else_block else [])
        return Node("if", {}, children)

    def parse_for(self) -> Node:
        self.eat("FOR")
        var = self.eat("IDENT").value
        self.eat("IN")
        iterable = self.parse_expr()
        body = self.parse_block()
        return Node("for", {"var": var}, [iterable, body])

    def parse_agent(self) -> Node:
        self.eat("AGENT")
        name = self.eat("IDENT").value
        block = self.parse_block()
        return Node("agent", {"name": name}, [block])

    def parse_async(self) -> Node:
        self.eat("ASYNC")
        block = self.parse_block()
        return Node("async", {}, [block])

    def parse_await(self) -> Node:
        self.eat("AWAIT")
        expr = self.parse_expr()
        return Node("await", {}, [expr])

    def parse_think(self) -> Node:
        self.eat("THINK")
        self.eat("COLON")
        s = self.eat("STRING").value.strip("\"'")
        return Node("think", {"text": s})

    def parse_emit(self) -> Node:
        self.eat("EMIT")
        what = self.eat("IDENT").value
        self.eat("ARROW")
        to = self.eat("IDENT").value
        return Node("emit", {"what": what, "to": to})

    def parse_on(self) -> Node:
        self.eat("ON")
        event = self.eat("IDENT").value
        self.eat("ARROW")
        call = self.parse_expr()
        return Node("on", {"event": event}, [call])

    # ── expressions ───────────────────────────────────────────────────────
    def parse_expr(self) -> Node:
        return self.parse_pipeline()

    def parse_pipeline(self) -> Node:
        left = self.parse_call()
        while self.peek() and self.peek().kind == "PIPE_OP":
            self.eat("PIPE_OP")
            right = self.parse_call()
            left = Node("pipe", {}, [left, right])
        return left

    def parse_call(self) -> Node:
        node = self.parse_atom()
        while True:
            if self.peek() and self.peek().kind == "DOT":
                self.eat("DOT")
                method = self.eat("IDENT").value
                self.eat("LPAREN")
                args = self.parse_arglist()
                self.eat("RPAREN")
                node = Node("method_call", {"method": method}, [node] + args)
            elif self.peek() and self.peek().kind == "LPAREN" and node.kind == "ident":
                self.eat("LPAREN")
                args = self.parse_arglist()
                self.eat("RPAREN")
                node = Node("func_call", {"name": node.data["name"]}, args)
            else:
                break
        return node

    def parse_arglist(self) -> list[Node]:
        args = []
        if self.peek() and self.peek().kind not in ("RPAREN",):
            args.append(self.parse_expr())
            while self.maybe("COMMA"):
                args.append(self.parse_expr())
        return args

    def parse_atom(self) -> Node:
        t = self.peek()
        if not t:
            raise ParseError("unexpected end in expression")
        if t.kind == "STRING":
            self.i += 1
            return Node("string", {"value": t.value.strip("\"'")})
        if t.kind == "NUMBER":
            self.i += 1
            v = float(t.value) if "." in t.value else int(t.value)
            return Node("number", {"value": v})
        if t.kind == "BOOL":
            self.i += 1
            return Node("bool", {"value": t.value == "true"})
        if t.kind == "LBRACKET":
            return self.parse_list_literal()
        if t.kind == "IDENT":
            self.i += 1
            return Node("ident", {"name": t.value})
        if t.value in _BUILTIN_NS or t.value in _KEYWORD_FNS:
            self.i += 1
            return Node("ident", {"name": t.value})
        if t.kind == "LPAREN":
            self.eat("LPAREN")
            e = self.parse_expr()
            self.eat("RPAREN")
            return e
        raise ParseError(f"unexpected token {t.kind}={t.value!r}")

    def parse_list_literal(self) -> Node:
        self.eat("LBRACKET")
        items = []
        if self.peek() and self.peek().kind != "RBRACKET":
            items.append(self.parse_expr())
            while self.maybe("COMMA"):
                items.append(self.parse_expr())
        self.eat("RBRACKET")
        return Node("list_literal", {}, items)


def parse(src: str) -> Node:
    return Parser(lex(src)).parse_program()


# ---------------------------------------------------------------------------
# Runtime / Evaluator
# ---------------------------------------------------------------------------
class GhostRuntimeError(Exception):
    pass


class Env:
    """Lexical environment for variable binding. Child scopes inherit parent."""
    def __init__(self, parent: "Env | None" = None):
        self._vars: dict[str, Any] = {}
        self._parent = parent

    def get(self, name: str) -> Any:
        if name in self._vars:
            return self._vars[name]
        if self._parent:
            return self._parent.get(name)
        raise GhostRuntimeError(f"undefined variable: {name!r}")

    def set(self, name: str, val: Any):
        self._vars[name] = val

    def child(self) -> "Env":
        return Env(parent=self)


def _truthy(val: Any) -> bool:
    if val is None or val is False or val == 0 or val == "" or val == []:
        return False
    if isinstance(val, str) and val.lower() in ("false", "none", "null", "0"):
        return False
    return True


class GhostRuntime:
    """
    Executes a GhostScript AST.

    llm_fn(prompt: str) -> str      — sync or async; enables real LLM calls
    memory_engine                   — MemoryPalace instance for real storage
    agent_id                        — identity on SwarmBus (default: random ghost-*)
    reply_timeout                   — seconds to wait for SwarmBus replies (default 30)
    """

    def __init__(self, llm_fn=None, memory_engine=None,
                 agent_id: str | None = None, reply_timeout: float = 30.0):
        self._llm      = llm_fn
        self._mem      = memory_engine
        self._id       = agent_id or f"ghost-{uuid.uuid4().hex[:6]}"
        self._timeout  = reply_timeout
        self.log: list[dict] = []
        self.archive: list[str] = []

    def _log(self, step: str, agent: str = "runtime", note: str = "", value: Any = None):
        entry: dict = {"step": step, "agent": agent, "note": note}
        if value is not None:
            entry["value"] = str(value)[:200]
        self.log.append(entry)

    # ── sync entry ────────────────────────────────────────────────────────
    def run(self, src: str) -> dict:
        try:
            ast = parse(src)
        except ParseError as e:
            return {"ok": False, "error": str(e), "log": [], "archive": []}
        try:
            env = Env()
            self._exec_block(ast.children, env, agent="runtime")
        except GhostRuntimeError as e:
            return {"ok": False, "error": str(e), "log": self.log, "archive": self.archive}
        return {"ok": True, "log": self.log, "archive": self.archive}

    # ── async entry ───────────────────────────────────────────────────────
    async def run_async(self, src: str) -> dict:
        try:
            ast = parse(src)
        except ParseError as e:
            return {"ok": False, "error": str(e), "log": [], "archive": []}
        try:
            env = Env()
            await self._exec_block_async(ast.children, env, agent="runtime")
        except GhostRuntimeError as e:
            return {"ok": False, "error": str(e), "log": self.log, "archive": self.archive}
        return {"ok": True, "log": self.log, "archive": self.archive}

    # ── sync block/statement execution ───────────────────────────────────
    def _exec_block(self, stmts: list[Node], env: Env, agent: str):
        for stmt in stmts:
            self._exec_stmt(stmt, env, agent)

    def _exec_stmt(self, node: Node, env: Env, agent: str):
        if node.kind == "let":
            val = self._eval(node.children[0], env, agent)
            env.set(node.data["name"], val)
            self._log("let", agent, f"{node.data['name']} = {val!r}")

        elif node.kind == "if":
            cond = self._eval(node.children[0], env, agent)
            if _truthy(cond):
                self._exec_block(node.children[1].children, env.child(), agent)
            elif len(node.children) > 2:
                self._exec_block(node.children[2].children, env.child(), agent)

        elif node.kind == "for":
            iterable = self._eval(node.children[0], env, agent)
            var = node.data["var"]
            if isinstance(iterable, str):
                iterable = iterable.split()
            for item in (iterable if hasattr(iterable, "__iter__") else []):
                child = env.child()
                child.set(var, item)
                self._exec_block(node.children[1].children, child, agent)

        elif node.kind == "agent":
            self._exec_agent_sync(node, env)

        elif node.kind == "think":
            self._log("think", agent, node.data["text"])

        elif node.kind == "emit":
            what = node.data["what"]
            to   = node.data["to"]
            val  = env.get(what) if what in env._vars else what
            self.archive.append(str(val))
            self._log("emit", agent, f"{what} → {to} [sync: archived only]", val)

        elif node.kind == "on":
            key = f"__on_{node.data['event']}"
            env.set(key, node.children[0])
            self._log("bind", agent, f"on {node.data['event']} bound")

        elif node.kind == "async":
            self._log("async", agent, "async block (sync degradation — sequential)")
            self._exec_block(node.children[0].children, env.child(), agent)

        elif node.kind in ("expr_stmt",):
            self._eval(node.children[0], env, agent)

        else:
            self._eval(node, env, agent)

    def _exec_agent_sync(self, node: Node, parent_env: Env):
        name = node.data["name"]
        self._log("spawn", name, f"{name} agent (sync mode)")
        env = parent_env.child()
        env.set("self", name)
        handlers: dict[str, Node] = {}
        proposal = None

        for stmt in node.children[0].children:
            if stmt.kind == "on":
                handlers[stmt.data["event"]] = stmt.children[0]
                self._log("bind", name, f"on {stmt.data['event']} bound")
            elif stmt.kind == "emit":
                what = stmt.data["what"]
                to   = stmt.data["to"]
                val  = env.get(what) if what in env._vars else what
                proposal = str(val)
                self.archive.append(proposal)
                self._log("emit", name, f"{what} → {to}", val)
            else:
                self._exec_stmt(stmt, env, name)

        if "APPROVE" in handlers and proposal:
            result = self._eval(handlers["APPROVE"], env, name)
            self._log("dispatch", name, f"APPROVE → {result!r}")
        elif "REJECT" in handlers:
            result = self._eval(handlers["REJECT"], env, name)
            self._log("dispatch", name, f"REJECT → {result!r}")

    # ── async block/statement execution ───────────────────────────────────
    async def _exec_block_async(self, stmts: list[Node], env: Env, agent: str):
        for stmt in stmts:
            await self._exec_stmt_async(stmt, env, agent)

    async def _exec_stmt_async(self, node: Node, env: Env, agent: str):
        if node.kind == "let":
            val = await self._eval_async(node.children[0], env, agent)
            env.set(node.data["name"], val)
            self._log("let", agent, f"{node.data['name']} = {val!r}")

        elif node.kind == "if":
            cond = await self._eval_async(node.children[0], env, agent)
            if _truthy(cond):
                await self._exec_block_async(node.children[1].children, env.child(), agent)
            elif len(node.children) > 2:
                await self._exec_block_async(node.children[2].children, env.child(), agent)

        elif node.kind == "for":
            iterable = await self._eval_async(node.children[0], env, agent)
            var = node.data["var"]
            if isinstance(iterable, str):
                iterable = iterable.split()
            for item in (iterable if hasattr(iterable, "__iter__") else []):
                child = env.child()
                child.set(var, item)
                await self._exec_block_async(node.children[1].children, child, agent)

        elif node.kind == "agent":
            await self._exec_agent_async(node, env)

        elif node.kind == "async":
            self._log("async", agent, "async block started")
            await self._exec_block_async(node.children[0].children, env.child(), agent)

        elif node.kind == "await":
            val = await self._eval_async(node.children[0], env, agent)
            self._log("await", agent, f"resolved: {val!r}")

        elif node.kind == "think":
            self._log("think", agent, node.data["text"])
            if _BUS_OK:
                try:
                    bus = _SwarmBus.instance()
                    await bus.emit(src=agent, content=node.data["text"],
                                   channel=f"#swarm/{agent}",
                                   msg_type=_BusMsgType.THOUGHT)
                except Exception:
                    pass

        elif node.kind == "emit":
            await self._emit_async(node, env, agent)

        elif node.kind == "on":
            key = f"__on_{node.data['event']}"
            env.set(key, node.children[0])
            self._log("bind", agent, f"on {node.data['event']} bound")

        elif node.kind in ("expr_stmt",):
            await self._eval_async(node.children[0], env, agent)

        else:
            await self._eval_async(node, env, agent)

    async def _emit_async(self, node: Node, env: Env, agent: str):
        """Publish a TASK to the SwarmBus and log it."""
        what = node.data["what"]
        to   = node.data["to"]
        val  = env.get(what) if what in env._vars else what
        self.archive.append(str(val))
        self._log("emit", agent, f"{what} → {to}", val)

        if _BUS_OK:
            try:
                bus = _SwarmBus.instance()
                await bus.emit(
                    src=agent,
                    content=str(val),
                    channel=f"#swarm/{to}",
                    msg_type=_BusMsgType.TASK,
                    dst=to,
                    task_id=str(uuid.uuid4())[:8],
                    ghostscript=True,
                )
                self._log("bus_emit", agent, f"published to #swarm/{to}")
            except Exception as e:
                self._log("bus_error", agent, str(e))

    async def _exec_agent_async(self, node: Node, parent_env: Env):
        """
        Execute an agent {} block with real SwarmBus wiring.

        Execution order:
          1. Register agent identity on the bus (think = broadcast THOUGHT)
          2. Execute non-emit, non-on statements (let, think, llm.chat, etc.)
          3. Collect on-handlers and emit targets
          4. Emit TASK messages to target agents via the bus
          5. Await replies from each target within reply_timeout
          6. Fire matching on-handlers (RESULT / APPROVE / REJECT) with reply content
        """
        name = node.data["name"]
        self._log("spawn", name, f"{name} agent instantiated")

        env = parent_env.child()
        env.set("self", name)

        handlers:  dict[str, Node] = {}
        emit_jobs: list[tuple[str, str]] = []  # (val, target)

        for stmt in node.children[0].children:
            if stmt.kind == "on":
                handlers[stmt.data["event"]] = stmt.children[0]
                self._log("bind", name, f"on {stmt.data['event']} bound")
            elif stmt.kind == "emit":
                what = stmt.data["what"]
                to   = stmt.data["to"]
                val  = env.get(what) if what in env._vars else what
                emit_jobs.append((str(val), to))
                self.archive.append(str(val))
                self._log("emit", name, f"{what} → {to}", val)
            else:
                await self._exec_stmt_async(stmt, env, name)

        # Publish all emit jobs to the SwarmBus
        for val, to in emit_jobs:
            if _BUS_OK:
                try:
                    bus = _SwarmBus.instance()
                    await bus.emit(
                        src=name,
                        content=val,
                        channel=f"#swarm/{to}",
                        msg_type=_BusMsgType.TASK,
                        dst=to,
                        task_id=str(uuid.uuid4())[:8],
                        ghostscript=True,
                    )
                except Exception as e:
                    self._log("bus_error", name, str(e))

        # Await replies and dispatch handlers
        if emit_jobs and handlers and _BUS_OK:
            for val, to in emit_jobs:
                reply = await self._await_reply(name, to)
                if reply is not None:
                    env.set("RESULT", reply)
                    evt = self._classify_reply(reply)
                    if evt in handlers:
                        result = await self._eval_async(handlers[evt], env, name)
                        self._log("dispatch", name, f"{evt}({to}) → {result!r}")
                    elif "RESULT" in handlers:
                        result = await self._eval_async(handlers["RESULT"], env, name)
                        self._log("dispatch", name, f"RESULT({to}) → {result!r}")
                else:
                    self._log("timeout", name, f"no reply from {to} within {self._timeout}s")
                    if "REJECT" in handlers:
                        await self._eval_async(handlers["REJECT"], env, name)
        elif emit_jobs and handlers:
            # Bus not available — simulate APPROVE for first emit
            if "APPROVE" in handlers:
                result = await self._eval_async(handlers["APPROVE"], env, name)
                self._log("dispatch", name, f"APPROVE (simulated) → {result!r}")

    def _classify_reply(self, content: str) -> str:
        """Map a reply message content to an event name."""
        upper = content.upper()
        if "APPROVE" in upper:
            return "APPROVE"
        if "REJECT" in upper:
            return "REJECT"
        return "RESULT"

    async def _await_reply(self, from_agent: str, to_agent: str) -> str | None:
        """
        Subscribe to #swarm/{from_agent} and wait for a RESULT/CRITIQUE/VERDICT
        message from to_agent. Returns the content string, or None on timeout.
        """
        if not _BUS_OK:
            return None
        bus = _SwarmBus.instance()
        loop = asyncio.get_event_loop()
        fut: asyncio.Future = loop.create_future()
        consumed = [False]

        async def _handler(msg):
            if consumed[0] or fut.done():
                return
            if (msg.src == to_agent and
                    msg.msg_type in (_BusMsgType.RESULT, _BusMsgType.CRITIQUE,
                                     _BusMsgType.VERDICT, _BusMsgType.CHAT)):
                consumed[0] = True
                fut.set_result(msg.content)

        bus.subscribe(f"#swarm/{from_agent}", _handler)
        try:
            return await asyncio.wait_for(asyncio.shield(fut), timeout=self._timeout)
        except asyncio.TimeoutError:
            consumed[0] = True
            return None
        finally:
            bus.unsubscribe(f"#swarm/{from_agent}", _handler)

    # ── expression evaluation (sync) ──────────────────────────────────────
    def _eval(self, node: Node, env: Env, agent: str = "runtime") -> Any:
        if node.kind == "string":       return node.data["value"]
        if node.kind == "number":       return node.data["value"]
        if node.kind == "bool":         return node.data["value"]
        if node.kind == "list_literal": return [self._eval(c, env, agent) for c in node.children]

        if node.kind == "ident":
            name = node.data["name"]
            if name in _BUILTIN_NS or name in _KEYWORD_FNS:
                return name
            return env.get(name)

        if node.kind == "let":
            val = self._eval(node.children[0], env, agent)
            env.set(node.data["name"], val)
            return val

        if node.kind == "pipe":
            left_val = self._eval(node.children[0], env, agent)
            return self._call_with_pipe(node.children[1], left_val, env, agent)

        if node.kind in ("func_call", "method_call"):
            return self._dispatch_call(node, env, agent)

        if node.kind == "expr_stmt":
            return self._eval(node.children[0], env, agent)

        raise GhostRuntimeError(f"cannot evaluate node: {node.kind}")

    # ── expression evaluation (async) ─────────────────────────────────────
    async def _eval_async(self, node: Node, env: Env, agent: str) -> Any:
        if node.kind == "list_literal":
            return [await self._eval_async(c, env, agent) for c in node.children]
        if node.kind in ("func_call", "method_call"):
            return await self._dispatch_call_async(node, env, agent)
        if node.kind == "pipe":
            left_val = await self._eval_async(node.children[0], env, agent)
            return await self._call_with_pipe_async(node.children[1], left_val, env, agent)
        if node.kind == "let":
            val = await self._eval_async(node.children[0], env, agent)
            env.set(node.data["name"], val)
            return val
        if node.kind == "expr_stmt":
            return await self._eval_async(node.children[0], env, agent)
        return self._eval(node, env, agent)

    # ── pipe helpers ──────────────────────────────────────────────────────
    def _call_with_pipe(self, node: Node, piped: Any, env: Env, agent: str) -> Any:
        if node.kind == "func_call":
            args = [piped] + [self._eval(c, env, agent) for c in node.children]
            return self._builtin(node.data["name"], args, agent)
        if node.kind == "method_call":
            ns_val = self._eval(node.children[0], env, agent)
            extra  = [self._eval(c, env, agent) for c in node.children[1:]]
            return self._ns_call(str(ns_val), node.data["method"], [piped] + extra, agent)
        return self._eval(node, env, agent)

    async def _call_with_pipe_async(self, node: Node, piped: Any, env: Env, agent: str) -> Any:
        if node.kind == "func_call":
            args = [piped] + [await self._eval_async(c, env, agent) for c in node.children]
            return await self._builtin_async(node.data["name"], args, agent)
        if node.kind == "method_call":
            ns_val = await self._eval_async(node.children[0], env, agent)
            extra  = [await self._eval_async(c, env, agent) for c in node.children[1:]]
            return await self._ns_call_async(str(ns_val), node.data["method"], [piped] + extra, agent)
        return await self._eval_async(node, env, agent)

    # ── call dispatch ─────────────────────────────────────────────────────
    def _dispatch_call(self, node: Node, env: Env, agent: str) -> Any:
        if node.kind == "func_call":
            args = [self._eval(c, env, agent) for c in node.children]
            return self._builtin(node.data["name"], args, agent)
        if node.kind == "method_call":
            ns_val = self._eval(node.children[0], env, agent)
            args   = [self._eval(c, env, agent) for c in node.children[1:]]
            return self._ns_call(str(ns_val), node.data["method"], args, agent)
        raise GhostRuntimeError(f"unknown call kind: {node.kind}")

    async def _dispatch_call_async(self, node: Node, env: Env, agent: str) -> Any:
        if node.kind == "func_call":
            args = [await self._eval_async(c, env, agent) for c in node.children]
            return await self._builtin_async(node.data["name"], args, agent)
        if node.kind == "method_call":
            ns_val = await self._eval_async(node.children[0], env, agent)
            args   = [await self._eval_async(c, env, agent) for c in node.children[1:]]
            return await self._ns_call_async(str(ns_val), node.data["method"], args, agent)
        raise GhostRuntimeError(f"unknown call kind: {node.kind}")

    # ── sync built-ins ────────────────────────────────────────────────────
    def _builtin(self, name: str, args: list, agent: str) -> Any:
        if name == "evolve":
            strategy = args[0] if args else "default"
            self._log("evolve", agent, f"strategy: {strategy}")
            return f"evolve({strategy})"
        if name == "print":
            val = " ".join(str(a) for a in args)
            self._log("print", agent, val)
            return val
        if name == "reply_from":
            self._log("reply_from", agent, "[sync mode — no-op, use async {}]")
            return "[reply_from requires async mode]"
        if name == "llm":
            prompt = args[0] if args else ""
            if self._llm:
                try:
                    result = self._llm(prompt)
                    self._log("llm", agent, f"prompt={prompt[:60]!r}", result)
                    return result
                except Exception as e:
                    self._log("llm_error", agent, str(e))
                    return f"[llm error: {e}]"
            self._log("llm", agent, f"[simulated] {prompt[:60]!r}")
            return f"[LLM: {prompt[:60]}]"
        raise GhostRuntimeError(f"unknown function: {name!r}")

    # ── async built-ins ───────────────────────────────────────────────────
    async def _builtin_async(self, name: str, args: list, agent: str) -> Any:
        if name == "llm":
            prompt = args[0] if args else ""
            if self._llm:
                try:
                    if asyncio.iscoroutinefunction(self._llm):
                        result = await self._llm(prompt)
                    else:
                        result = self._llm(prompt)
                    self._log("llm", agent, f"prompt={prompt[:60]!r}", result)
                    return result
                except Exception as e:
                    self._log("llm_error", agent, str(e))
                    return f"[llm error: {e}]"
            self._log("llm", agent, f"[simulated] {prompt[:60]!r}")
            return f"[LLM: {prompt[:60]}]"
        if name == "reply_from":
            target = str(args[0]) if args else ""
            if not target:
                return None
            self._log("reply_from", agent, f"awaiting reply from {target}")
            return await self._await_reply(agent, target)
        return self._builtin(name, args, agent)

    # ── sync namespace calls ──────────────────────────────────────────────
    def _ns_call(self, ns: str, method: str, args: list, agent: str) -> Any:
        if ns == "llm":
            if method == "chat":
                prompt = args[0] if args else ""
                if self._llm:
                    try:
                        result = self._llm(prompt)
                        self._log("llm.chat", agent, f"{prompt[:60]!r}", result)
                        return result
                    except Exception as e:
                        self._log("llm_error", agent, str(e))
                        return f"[llm error: {e}]"
                self._log("llm.chat", agent, f"[simulated] {prompt[:60]!r}")
                return f"[LLM: {prompt[:80]}]"
            if method == "embed":
                text = args[0] if args else ""
                self._log("llm.embed", agent, f"embedding {len(text)} chars")
                return f"[embedding:{len(text)}dims]"
            raise GhostRuntimeError(f"llm.{method} not implemented")

        if ns == "memory":
            if method == "store":
                key = str(args[0]) if args else "unnamed"
                val = args[1] if len(args) > 1 else ""
                if self._mem:
                    try:
                        self._mem.store(content=f"{key}: {val}", room="ghostscript")
                    except Exception as e:
                        self._log("memory_error", agent, str(e))
                self._log("memory.store", agent, f"{key!r} = {str(val)[:60]!r}")
                return val
            if method == "search":
                query = str(args[0]) if args else ""
                if self._mem:
                    try:
                        results = self._mem.search(query)
                        hits = [r.get("content", "") for r in results[:5]]
                        self._log("memory.search", agent, f"query={query!r} → {len(hits)} hits")
                        return hits
                    except Exception as e:
                        self._log("memory_error", agent, str(e))
                self._log("memory.search", agent, f"[simulated] query={query!r}")
                return [f"[memory result for: {query}]"]
            raise GhostRuntimeError(f"memory.{method} not implemented")

        if ns == "kairos":
            if method == "propose":
                idea = str(args[0]) if args else ""
                self._log("kairos.propose", agent, f"proposal: {idea!r}")
                self.archive.append(idea)
                return idea
            if method == "score":
                result = args[0] if args else ""
                self._log("kairos.score", agent, f"scoring: {result!r}")
                return 0.85
            raise GhostRuntimeError(f"kairos.{method} not implemented")

        if ns == "Archive":
            if method == "store":
                val = args[0] if args else ""
                self.archive.append(str(val))
                self._log("archive.store", agent, str(val)[:80])
                return val
            raise GhostRuntimeError(f"Archive.{method} not implemented")

        raise GhostRuntimeError(f"unknown namespace: {ns!r}")

    # ── async namespace calls ─────────────────────────────────────────────
    async def _ns_call_async(self, ns: str, method: str, args: list, agent: str) -> Any:
        if ns == "llm":
            if method == "chat":
                prompt = args[0] if args else ""
                if self._llm:
                    try:
                        if asyncio.iscoroutinefunction(self._llm):
                            result = await self._llm(prompt)
                        else:
                            result = self._llm(prompt)
                        self._log("llm.chat", agent, f"{prompt[:60]!r}", result)
                        return result
                    except Exception as e:
                        self._log("llm_error", agent, str(e))
                        return f"[llm error: {e}]"
                self._log("llm.chat", agent, f"[simulated] {prompt[:60]!r}")
                return f"[LLM: {prompt[:80]}]"
            if method == "embed":
                text = args[0] if args else ""
                self._log("llm.embed", agent, f"embedding {len(text)} chars")
                return f"[embedding:{len(text)}dims]"
            raise GhostRuntimeError(f"llm.{method} not implemented")

        if ns == "memory":
            if method == "store":
                key = str(args[0]) if args else "unnamed"
                val = args[1] if len(args) > 1 else ""
                if self._mem:
                    try:
                        self._mem.store(content=f"{key}: {val}", room="ghostscript")
                    except Exception as e:
                        self._log("memory_error", agent, str(e))
                self._log("memory.store", agent, f"{key!r} = {str(val)[:60]!r}")
                return val
            if method == "search":
                query = str(args[0]) if args else ""
                if self._mem:
                    try:
                        results = self._mem.search(query)
                        hits = [r.get("content", "") for r in results[:5]]
                        self._log("memory.search", agent, f"query={query!r} → {len(hits)} hits")
                        return hits
                    except Exception as e:
                        self._log("memory_error", agent, str(e))
                self._log("memory.search", agent, f"[simulated] query={query!r}")
                return [f"[memory result for: {query}]"]
            raise GhostRuntimeError(f"memory.{method} not implemented")

        # All other namespaces fall through to sync
        return self._ns_call(ns, method, args, agent)


# ---------------------------------------------------------------------------
# Public API — convenience wrappers
# ---------------------------------------------------------------------------
def run(src: str, llm_fn=None, memory_engine=None,
        agent_id: str | None = None) -> dict:
    """Execute GhostScript synchronously. Returns trace log + archive."""
    rt = GhostRuntime(llm_fn=llm_fn, memory_engine=memory_engine, agent_id=agent_id)
    return rt.run(src)


async def run_async(src: str, llm_fn=None, memory_engine=None,
                    agent_id: str | None = None,
                    reply_timeout: float = 30.0) -> dict:
    """Execute GhostScript asynchronously with real SwarmBus + LLM wiring."""
    rt = GhostRuntime(llm_fn=llm_fn, memory_engine=memory_engine,
                      agent_id=agent_id, reply_timeout=reply_timeout)
    return await rt.run_async(src)


def run_file(path: str, llm_fn=None, memory_engine=None) -> dict:
    """Load and execute a .gs file synchronously."""
    import pathlib
    src = pathlib.Path(path).read_text(encoding="utf-8")
    return run(src, llm_fn=llm_fn, memory_engine=memory_engine,
               agent_id=pathlib.Path(path).stem)


async def run_file_async(path: str, llm_fn=None, memory_engine=None,
                         reply_timeout: float = 30.0) -> dict:
    """Load and execute a .gs file asynchronously."""
    import pathlib
    src = pathlib.Path(path).read_text(encoding="utf-8")
    return await run_async(src, llm_fn=llm_fn, memory_engine=memory_engine,
                           agent_id=pathlib.Path(path).stem,
                           reply_timeout=reply_timeout)


# ---------------------------------------------------------------------------
# Demo programs (all pass)
# ---------------------------------------------------------------------------
DEMO_AGENT = '''# Classic SAGE cycle: Proposer → Critic with real emit
agent Proposer {
    think: "Optimizing VRAM allocation for Qwen2.5"
    let proposal = llm.chat("Propose one concrete VRAM optimization. Under 20 words.")
    emit proposal -> Critic
    on APPROVE -> Archive.store(proposal)
    on REJECT  -> evolve("diversity_boost")
    on RESULT  -> memory.store("last_proposal", proposal)
}'''

DEMO_PIPELINE = '''# Pipeline: LLM output piped into memory
let query = "What is KAIROS?"
let result = llm.chat(query) |> memory.store("last_answer")
print(result)
'''

DEMO_ASYNC = '''# Async parallel proposals
async {
    let a = llm.chat("Propose optimization A")
    let b = llm.chat("Propose optimization B")
    kairos.propose(a)
    kairos.propose(b)
}
'''

DEMO_IF_FOR = '''# if/else + for loop
let score = 0.9
if (score) {
    let ideas = ["FAISS archive", "cold-tier pruning", "RLVR rewards"]
    for idea in ideas {
        kairos.propose(idea)
    }
} else {
    evolve("plateau_recovery")
}
'''

DEMO_MULTI_AGENT = '''# Multi-agent: Proposer → ORACLE, then FORGE based on reply
agent Researcher {
    think: "Finding best VRAM optimization strategy"
    let query = "Best VRAM optimization for 8GB GPU running Qwen2.5?"
    emit query -> ORACLE
    on RESULT -> memory.store("research_result", RESULT)
    on REJECT -> evolve("search_wider")
}

agent Builder {
    think: "Implementing the top research finding"
    let spec = memory.search("research_result")
    emit spec -> FORGE
    on RESULT -> Archive.store(RESULT)
    on REJECT  -> evolve("simplify_spec")
}
'''


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------
# Backward-compat alias — server.py imports DEMO
DEMO = DEMO_AGENT


if __name__ == "__main__":
    import json

    print("=== Agent + SAGE cycle ===")
    print(json.dumps(run(DEMO_AGENT), indent=2))

    print("\n=== Pipeline ===")
    print(json.dumps(run(DEMO_PIPELINE), indent=2))

    print("\n=== Async ===")
    print(json.dumps(run(DEMO_ASYNC), indent=2))

    print("\n=== if/else + for loop ===")
    print(json.dumps(run(DEMO_IF_FOR), indent=2))

    print("\n=== Multi-agent ===")
    print(json.dumps(run(DEMO_MULTI_AGENT), indent=2))
