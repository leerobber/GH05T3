"""Minimal but real GhostScript interpreter.
Grammar (subset per spec):

    agent IDENT { BODY }
    BODY ::= STMT*
    STMT ::= "think:" STRING
           | "emit" IDENT "->" IDENT
           | "on" IDENT "->" CALL
           | IDENT "(" (STRING | IDENT) ")"
    CALL ::= IDENT "." IDENT "(" (STRING | IDENT) ")"
           | "evolve" "(" STRING ")"

Returns a structured trace that the frontend renders as an execution log.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any


TOKEN_RE = re.compile(
    r"""
    (?P<STRING>"[^"]*") |
    (?P<ARROW>->|\u2192) |
    (?P<COLON>:) |
    (?P<LBRACE>\{) |
    (?P<RBRACE>\}) |
    (?P<LPAREN>\() |
    (?P<RPAREN>\)) |
    (?P<DOT>\.) |
    (?P<COMMA>,) |
    (?P<IDENT>[A-Za-z_][A-Za-z0-9_]*) |
    (?P<WS>\s+) |
    (?P<OTHER>.)
    """,
    re.VERBOSE,
)


@dataclass
class Token:
    kind: str
    value: str
    pos: int


def lex(src: str) -> list[Token]:
    toks = []
    for m in TOKEN_RE.finditer(src):
        kind = m.lastgroup
        if kind == "WS":
            continue
        toks.append(Token(kind, m.group(), m.start()))
    return toks


class ParseError(Exception):
    pass


@dataclass
class Node:
    kind: str
    data: dict = field(default_factory=dict)
    children: list["Node"] = field(default_factory=list)


class Parser:
    def __init__(self, toks: list[Token]):
        self.toks = toks
        self.i = 0

    def peek(self, k: int = 0) -> Token | None:
        return self.toks[self.i + k] if self.i + k < len(self.toks) else None

    def eat(self, kind: str, value: str | None = None) -> Token:
        t = self.peek()
        if not t or t.kind != kind or (value and t.value != value):
            raise ParseError(f"expected {kind}{'='+value if value else ''} got {t}")
        self.i += 1
        return t

    def parse_program(self) -> Node:
        prog = Node("program")
        while self.peek():
            t = self.peek()
            if t.kind == "IDENT" and t.value == "agent":
                prog.children.append(self.parse_agent())
            else:
                raise ParseError(f"unexpected top-level token: {t.value}")
        return prog

    def parse_agent(self) -> Node:
        self.eat("IDENT", "agent")
        name = self.eat("IDENT").value
        self.eat("LBRACE")
        node = Node("agent", {"name": name})
        while self.peek() and self.peek().kind != "RBRACE":
            node.children.append(self.parse_stmt())
        self.eat("RBRACE")
        return node

    def parse_stmt(self) -> Node:
        t = self.peek()
        if t.kind == "IDENT" and t.value == "think":
            self.eat("IDENT")
            self.eat("COLON")
            s = self.eat("STRING").value[1:-1]
            return Node("think", {"text": s})
        if t.kind == "IDENT" and t.value == "emit":
            self.eat("IDENT")
            what = self.eat("IDENT").value
            self.eat("ARROW")
            to = self.eat("IDENT").value
            return Node("emit", {"what": what, "to": to})
        if t.kind == "IDENT" and t.value == "on":
            self.eat("IDENT")
            event = self.eat("IDENT").value
            self.eat("ARROW")
            call = self.parse_call()
            return Node("on", {"event": event}, [call])
        # bare call
        return self.parse_call()

    def parse_call(self) -> Node:
        t = self.eat("IDENT")
        name = t.value
        # chained: ns.method(arg)
        if self.peek() and self.peek().kind == "DOT":
            self.eat("DOT")
            method = self.eat("IDENT").value
            self.eat("LPAREN")
            arg = self._parse_arg()
            self.eat("RPAREN")
            return Node("method_call", {"ns": name, "method": method, "arg": arg})
        # simple call: name(arg)
        self.eat("LPAREN")
        arg = self._parse_arg()
        self.eat("RPAREN")
        return Node("call", {"name": name, "arg": arg})

    def _parse_arg(self) -> Any:
        t = self.peek()
        if not t:
            return None
        if t.kind == "STRING":
            self.i += 1
            return t.value[1:-1]
        if t.kind == "IDENT":
            # support key: value style e.g. strategy: "diversity_boost"
            self.i += 1
            if self.peek() and self.peek().kind == "COLON":
                self.eat("COLON")
                v = self.peek()
                if v.kind == "STRING":
                    self.i += 1
                    return {t.value: v.value[1:-1]}
                if v.kind == "IDENT":
                    self.i += 1
                    return {t.value: v.value}
            return t.value
        return None


def parse(src: str) -> Node:
    return Parser(lex(src)).parse_program()


# Evaluator ---------------------------------------------------------------
def run(src: str) -> dict:
    """Execute a GhostScript program. Returns a trace log."""
    try:
        ast = parse(src)
    except ParseError as e:
        return {"ok": False, "error": str(e), "log": []}

    log: list[dict] = []
    archive: list[str] = []

    for agent in ast.children:
        aname = agent.data["name"]
        log.append({"step": "spawn", "agent": aname, "note": f"{aname} agent instantiated"})
        state = {"self": aname, "handlers": {}, "proposal": None}
        for stmt in agent.children:
            if stmt.kind == "think":
                log.append({"step": "think", "agent": aname, "note": stmt.data["text"]})
            elif stmt.kind == "emit":
                what = stmt.data["what"]
                to = stmt.data["to"]
                state["proposal"] = what
                log.append({"step": "emit", "agent": aname, "note": f"{what} -> {to}"})
            elif stmt.kind == "on":
                evt = stmt.data["event"]
                state["handlers"][evt] = stmt.children[0]
                log.append({"step": "bind", "agent": aname, "note": f"on {evt} bound"})
            elif stmt.kind in ("call", "method_call"):
                log.append({"step": "call", "agent": aname, "note": _fmt_call(stmt)})

        # simulate dispatcher: fire APPROVE handler if proposal present
        if "APPROVE" in state["handlers"]:
            call = state["handlers"]["APPROVE"]
            archive.append(state.get("proposal") or aname)
            log.append({"step": "dispatch", "agent": aname,
                        "note": f"APPROVE -> {_fmt_call(call)}"})
        elif "REJECT" in state["handlers"]:
            call = state["handlers"]["REJECT"]
            log.append({"step": "dispatch", "agent": aname,
                        "note": f"REJECT -> {_fmt_call(call)}"})

    return {"ok": True, "log": log, "archive": archive}


def _fmt_call(node: Node) -> str:
    if node.kind == "call":
        return f"{node.data['name']}({_fmt_arg(node.data['arg'])})"
    if node.kind == "method_call":
        return f"{node.data['ns']}.{node.data['method']}({_fmt_arg(node.data['arg'])})"
    return node.kind


def _fmt_arg(a: Any) -> str:
    if isinstance(a, dict):
        k, v = next(iter(a.items()))
        return f'{k}: "{v}"'
    if isinstance(a, str):
        return f'"{a}"'
    return ""


DEMO = '''agent Proposer {
    think: "optimize VRAM allocation"
    emit proposal -> Critic
    on APPROVE -> Archive.store(self)
    on REJECT -> evolve(strategy: "diversity_boost")
}'''
