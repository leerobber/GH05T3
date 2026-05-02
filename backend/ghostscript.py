"""GhostScript — AI/ML orchestration language for GH05T3.

Grammar:
    program     ::= stmt*
    stmt        ::= let_stmt | agent_stmt | async_stmt | expr_stmt
    let_stmt    ::= "let" IDENT "=" expr
    agent_stmt  ::= "agent" IDENT "{" stmt* "}"
    async_stmt  ::= "async" block | "await" expr
    expr_stmt   ::= expr
    expr        ::= pipeline
    pipeline    ::= call ("|>" call)*
    call        ::= atom ("." IDENT "(" arglist ")")* ("(" arglist ")")?
    atom        ::= STRING | NUMBER | BOOL | IDENT | "(" expr ")"
    arglist     ::= (expr ("," expr)*)?

Built-in namespaces (wired to real GH05T3 providers):
    llm.chat(prompt)          — call the active LLM provider
    llm.embed(text)           — embed text (returns dim count as str)
    memory.store(key, value)  — store in memory palace
    memory.search(query)      — search memory palace
    kairos.propose(idea)      — submit to SAGE cycle
    evolve(strategy)          — request self-modification proposal
    think: "..."              — log a reasoning step
    emit VAR -> TARGET        — route a value to another agent
    on EVENT -> call          — bind event handler
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any


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
}

# Known built-in namespaces — resolved without env lookup
_BUILTIN_NS = {"llm", "memory", "kairos", "Archive"}
# Callable keywords (not statements, just functions)
_KEYWORD_FNS = {"evolve", "print"}


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
        # Promote keywords from IDENT
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
            raise ParseError(f"line ~{t.pos}: expected {kind}, got {t.kind}={t.value!r}")
        if value is not None and t.value != value:
            raise ParseError(f"line ~{t.pos}: expected {value!r}, got {t.value!r}")
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
        if t.kind == "LET":
            return self.parse_let()
        if t.kind == "AGENT":
            return self.parse_agent()
        if t.kind == "ASYNC":
            return self.parse_async()
        if t.kind == "AWAIT":
            return self.parse_await()
        if t.kind == "THINK":
            return self.parse_think()
        if t.kind == "EMIT":
            return self.parse_emit()
        if t.kind == "ON":
            return self.parse_on()
        return Node("expr_stmt", {}, [self.parse_expr()])

    def parse_let(self) -> Node:
        self.eat("LET")
        name = self.eat("IDENT").value
        self.eat("EQ")
        val = self.parse_expr()
        return Node("let", {"name": name}, [val])

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
        if t.kind == "IDENT":
            self.i += 1
            return Node("ident", {"name": t.value})
        # Allow built-in namespaces and callable keywords as identifiers
        if t.value in _BUILTIN_NS or t.value in _KEYWORD_FNS:
            self.i += 1
            return Node("ident", {"name": t.value})
        if t.kind == "LPAREN":
            self.eat("LPAREN")
            e = self.parse_expr()
            self.eat("RPAREN")
            return e
        raise ParseError(f"unexpected token {t.kind}={t.value!r}")


def parse(src: str) -> Node:
    return Parser(lex(src)).parse_program()


# ---------------------------------------------------------------------------
# Runtime / Evaluator
# ---------------------------------------------------------------------------
class GhostRuntimeError(Exception):
    pass


class Env:
    """Lexical environment for variable binding."""
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


class GhostRuntime:
    """
    Executes a GhostScript AST.
    Pass llm_fn to enable real LLM calls:
        llm_fn(prompt: str) -> str   (sync or async)
    Pass memory_engine for real memory access.
    """
    def __init__(self, llm_fn=None, memory_engine=None):
        self._llm = llm_fn
        self._mem = memory_engine
        self.log: list[dict] = []
        self.archive: list[str] = []
        self._agents: dict[str, list[Node]] = {}

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

    # ── statement execution ───────────────────────────────────────────────
    def _exec_block(self, stmts: list[Node], env: Env, agent: str):
        for stmt in stmts:
            self._exec_stmt(stmt, env, agent)

    async def _exec_block_async(self, stmts: list[Node], env: Env, agent: str):
        for stmt in stmts:
            await self._exec_stmt_async(stmt, env, agent)

    def _exec_stmt(self, node: Node, env: Env, agent: str):
        if node.kind == "let":
            val = self._eval(node.children[0], env, agent)
            env.set(node.data["name"], val)
            self._log("let", agent, f"{node.data['name']} = {val!r}")
        elif node.kind == "agent":
            self._exec_agent(node, env)
        elif node.kind == "think":
            self._log("think", agent, node.data["text"])
        elif node.kind == "emit":
            what = node.data["what"]
            to = node.data["to"]
            val = env.get(what) if what in env._vars else what
            self.archive.append(str(val))
            self._log("emit", agent, f"{what} → {to}", val)
        elif node.kind == "on":
            # Register event handler in env
            key = f"__on_{node.data['event']}"
            env.set(key, node.children[0])
            self._log("bind", agent, f"on {node.data['event']} bound")
        elif node.kind == "async":
            self._log("async", agent, "async block (sync mode — awaiting inline)")
            self._exec_block(node.children[0].children, env.child(), agent)
        elif node.kind in ("expr_stmt",):
            self._eval(node.children[0], env, agent)
        else:
            self._eval(node, env, agent)

    async def _exec_stmt_async(self, node: Node, env: Env, agent: str):
        if node.kind == "async":
            self._log("async", agent, "async block started")
            child_env = env.child()
            await self._exec_block_async(node.children[0].children, child_env, agent)
        elif node.kind == "await":
            val = await self._eval_async(node.children[0], env, agent)
            self._log("await", agent, f"resolved: {val!r}")
        else:
            self._exec_stmt(node, env, agent)

    def _exec_agent(self, node: Node, parent_env: Env):
        name = node.data["name"]
        self._log("spawn", name, f"{name} agent instantiated")
        env = parent_env.child()
        env.set("self", name)
        block = node.children[0]

        handlers: dict[str, Node] = {}
        proposal = None

        for stmt in block.children:
            if stmt.kind == "on":
                evt = stmt.data["event"]
                handlers[evt] = stmt.children[0]
                self._log("bind", name, f"on {evt} bound")
            elif stmt.kind == "emit":
                what = stmt.data["what"]
                to = stmt.data["to"]
                val = env.get(what) if what in env._vars else what
                proposal = str(val)
                self._log("emit", name, f"{what} → {to}", val)
            else:
                self._exec_stmt(stmt, env, name)

        # Dispatch: fire APPROVE handler if proposal present
        if "APPROVE" in handlers and proposal:
            self.archive.append(proposal)
            result = self._eval(handlers["APPROVE"], env, name)
            self._log("dispatch", name, f"APPROVE → {result!r}")
        elif "REJECT" in handlers:
            result = self._eval(handlers["REJECT"], env, name)
            self._log("dispatch", name, f"REJECT → {result!r}")

    # ── expression evaluation ─────────────────────────────────────────────
    def _eval(self, node: Node, env: Env, agent: str = "runtime") -> Any:
        if node.kind == "string":
            return node.data["value"]
        if node.kind == "number":
            return node.data["value"]
        if node.kind == "bool":
            return node.data["value"]
        if node.kind == "ident":
            name = node.data["name"]
            # Built-in namespaces don't live in env — return the name as handle
            if name in _BUILTIN_NS or name in _KEYWORD_FNS:
                return name
            return env.get(name)
        if node.kind == "let":
            val = self._eval(node.children[0], env, agent)
            env.set(node.data["name"], val)
            return val
        if node.kind == "pipe":
            left_val = self._eval(node.children[0], env, agent)
            # pipe: pass left result as first arg to right call
            right = node.children[1]
            return self._call_with_pipe(right, left_val, env, agent)
        if node.kind in ("func_call", "method_call"):
            return self._dispatch_call(node, env, agent)
        if node.kind == "expr_stmt":
            return self._eval(node.children[0], env, agent)
        raise GhostRuntimeError(f"cannot evaluate node kind: {node.kind}")

    async def _eval_async(self, node: Node, env: Env, agent: str) -> Any:
        if node.kind in ("func_call", "method_call"):
            return await self._dispatch_call_async(node, env, agent)
        return self._eval(node, env, agent)

    def _call_with_pipe(self, node: Node, piped: Any, env: Env, agent: str) -> Any:
        """Inject piped value as first argument to a call node."""
        if node.kind == "func_call":
            name = node.data["name"]
            args = [piped] + [self._eval(c, env, agent) for c in node.children]
            return self._builtin(name, args, agent)
        if node.kind == "method_call":
            # ns.method(extra_args) with piped as first arg
            ns_node = node.children[0]
            ns_val = self._eval(ns_node, env, agent)
            method = node.data["method"]
            extra_args = [self._eval(c, env, agent) for c in node.children[1:]]
            return self._ns_call(str(ns_val), method, [piped] + extra_args, agent)
        return self._eval(node, env, agent)

    def _dispatch_call(self, node: Node, env: Env, agent: str) -> Any:
        if node.kind == "func_call":
            name = node.data["name"]
            args = [self._eval(c, env, agent) for c in node.children]
            return self._builtin(name, args, agent)
        if node.kind == "method_call":
            ns_node = node.children[0]
            ns_val = self._eval(ns_node, env, agent)
            method = node.data["method"]
            args = [self._eval(c, env, agent) for c in node.children[1:]]
            return self._ns_call(str(ns_val), method, args, agent)
        raise GhostRuntimeError(f"unknown call kind: {node.kind}")

    async def _dispatch_call_async(self, node: Node, env: Env, agent: str) -> Any:
        if node.kind == "func_call":
            name = node.data["name"]
            args = [self._eval(c, env, agent) for c in node.children]
            return await self._builtin_async(name, args, agent)
        return self._dispatch_call(node, env, agent)

    # ── built-ins ─────────────────────────────────────────────────────────
    def _builtin(self, name: str, args: list, agent: str) -> Any:
        if name == "evolve":
            strategy = args[0] if args else "default"
            self._log("evolve", agent, f"strategy: {strategy}")
            return f"evolve({strategy})"
        if name == "print":
            val = " ".join(str(a) for a in args)
            self._log("print", agent, val)
            return val
        if name == "llm":
            # sync LLM call
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
            return f"[LLM response to: {prompt[:60]}]"
        raise GhostRuntimeError(f"unknown function: {name!r}")

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
            return f"[LLM response to: {prompt[:60]}]"
        return self._builtin(name, args, agent)

    def _ns_call(self, ns: str, method: str, args: list, agent: str) -> Any:
        """Namespace method calls: llm.chat(), memory.store(), kairos.propose()"""

        # llm.*
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

        # memory.*
        if ns == "memory":
            if method == "store":
                key = args[0] if args else "unnamed"
                val = args[1] if len(args) > 1 else ""
                self._log("memory.store", agent, f"{key!r} = {str(val)[:60]!r}")
                return val
            if method == "search":
                query = args[0] if args else ""
                self._log("memory.search", agent, f"query={query!r}")
                return f"[memory results for: {query}]"
            raise GhostRuntimeError(f"memory.{method} not implemented")

        # kairos.*
        if ns == "kairos":
            if method == "propose":
                idea = args[0] if args else ""
                self._log("kairos.propose", agent, f"proposal: {idea!r}")
                self.archive.append(idea)
                return idea
            if method == "score":
                result = args[0] if args else ""
                self._log("kairos.score", agent, f"scoring: {result!r}")
                return 0.85
            raise GhostRuntimeError(f"kairos.{method} not implemented")

        # Archive.*
        if ns == "Archive":
            if method == "store":
                val = args[0] if args else ""
                self.archive.append(str(val))
                self._log("archive.store", agent, str(val)[:80])
                return val
            raise GhostRuntimeError(f"Archive.{method} not implemented")

        raise GhostRuntimeError(f"unknown namespace: {ns!r}")


# ---------------------------------------------------------------------------
# Convenience: sync run() for backward compatibility + server endpoint
# ---------------------------------------------------------------------------
def run(src: str, llm_fn=None, memory_engine=None) -> dict:
    """Execute GhostScript synchronously. Returns trace log."""
    rt = GhostRuntime(llm_fn=llm_fn, memory_engine=memory_engine)
    return rt.run(src)


async def run_async(src: str, llm_fn=None, memory_engine=None) -> dict:
    """Execute GhostScript with real async LLM calls."""
    rt = GhostRuntime(llm_fn=llm_fn, memory_engine=memory_engine)
    return await rt.run_async(src)


# ---------------------------------------------------------------------------
# Demo programs
# ---------------------------------------------------------------------------
DEMO = '''# Classic SAGE cycle in GhostScript
agent Proposer {
    think: "optimize VRAM allocation for Qwen2.5"
    let proposal = llm.chat("Propose one concrete VRAM optimization")
    emit proposal -> Critic
    on APPROVE -> Archive.store(proposal)
    on REJECT -> evolve("diversity_boost")
}'''

PIPELINE_DEMO = '''# Pipeline operator: output of left becomes first arg of right
let query = "What is KAIROS?"
let result = llm.chat(query) |> memory.store("last_answer")
print(result)
'''

ASYNC_DEMO = '''# Async parallel LLM calls
async {
    let a = llm.chat("Propose optimization A")
    let b = llm.chat("Propose optimization B")
    kairos.propose(a)
    kairos.propose(b)
}
'''


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json
    print("=== Classic agent ===")
    print(json.dumps(run(DEMO), indent=2))

    print("\n=== Pipeline demo ===")
    print(json.dumps(run(PIPELINE_DEMO), indent=2))

    print("\n=== Async demo ===")
    print(json.dumps(run(ASYNC_DEMO), indent=2))
