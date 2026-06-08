"""
GhostRecall — 7-Layer Neuroscience-Backed Memory Architecture
=============================================================
Layers (bottom → top):
  1. Sensory Buffer       — raw prompt tokens, 8s TTL, in-process deque
  2. Short-Term Cache     — live KV cache routing, 5-min TTL, in-process dict
  3. Working Memory       — active task context, session-scoped, SQLite
  4. Explicit Long-Term   — spatially optimised SQLite + ChromaDB semantic index
                            with valid_at / invalid_at temporal graph edges
  5. Implicit / Skill     — procedural skills stored as soft-prompt injections (JSON)
  6. Engram Vault         — "forgotten" neural traces preserved for semantic
                            reactivation (ChromaDB, low-priority namespace)
  7. Belief Hierarchy     — identity + world-model reconsolidation (SQLite)

Iron Dome integration:
  Every Explicit Long-Term write is logged to the IronDome hash chain.

Usage:
    from memory.ghostrecall import GhostRecall
    mem = GhostRecall()

    # Store
    mem_id = await mem.store("FORGE", "Python async best practices", tags=["python","async"])

    # Recall
    hits  = await mem.recall("async patterns", top_k=5)

    # Inject into prompt
    context = await mem.build_context("forge-session-001", query="write async code")
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import sqlite3
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

LOG = logging.getLogger("aethyro.ghostrecall")

_DATA_DIR    = Path(__file__).parent / "data"
_DB_PATH     = _DATA_DIR / "ghostrecall.db"
_CHROMA_PATH = _DATA_DIR / "ghostrecall_chroma"

# Ollama embed endpoint (NPU service first, fallback to Ollama)
_NPU_EMBED_URL    = "http://localhost:8111/embed_query"
_OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
_EMBED_MODEL      = "nomic-embed-text"

# Context budget (tokens ~ chars/4)
CONTEXT_BUDGET_CHARS = 6000

# TTLs
SENSORY_TTL_S    = 8.0
SHORT_TERM_TTL_S = 300.0


# ─────────────────────────────────────────────────────────────────────────────
# DB bootstrap
# ─────────────────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def _init_db() -> None:
    with _conn() as c:
        # Layer 3: Working memory (session-scoped)
        c.execute("""
            CREATE TABLE IF NOT EXISTS working_memory (
                id         TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                agent_id   TEXT NOT NULL DEFAULT '',
                content    TEXT NOT NULL,
                role       TEXT NOT NULL DEFAULT 'system',
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS wm_session ON working_memory(session_id)")

        # Layer 4: Explicit Long-Term memory with temporal graph edges
        c.execute("""
            CREATE TABLE IF NOT EXISTS explicit_memory (
                id           TEXT PRIMARY KEY,
                agent_id     TEXT NOT NULL DEFAULT '',
                user_id      TEXT NOT NULL DEFAULT 'system',
                content      TEXT NOT NULL,
                summary      TEXT NOT NULL DEFAULT '',
                tags         TEXT NOT NULL DEFAULT '[]',
                importance   REAL NOT NULL DEFAULT 0.5,
                confidence   REAL NOT NULL DEFAULT 1.0,
                utility      REAL NOT NULL DEFAULT 0.5,
                access_count INTEGER NOT NULL DEFAULT 0,
                valid_at     REAL NOT NULL,
                invalid_at   REAL,
                created_at   REAL NOT NULL,
                last_accessed REAL NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS em_agent ON explicit_memory(agent_id)")
        c.execute("CREATE INDEX IF NOT EXISTS em_user ON explicit_memory(user_id)")
        c.execute("CREATE INDEX IF NOT EXISTS em_valid ON explicit_memory(valid_at, invalid_at)")

        # Layer 5: Implicit skills (soft-prompt injections)
        c.execute("""
            CREATE TABLE IF NOT EXISTS skill_memory (
                id          TEXT PRIMARY KEY,
                agent_id    TEXT NOT NULL,
                skill_name  TEXT NOT NULL,
                description TEXT NOT NULL,
                soft_prompt TEXT NOT NULL,
                trigger_keywords TEXT NOT NULL DEFAULT '[]',
                use_count   INTEGER NOT NULL DEFAULT 0,
                created_at  REAL NOT NULL,
                updated_at  REAL NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS sm_agent ON skill_memory(agent_id)")

        # Layer 6: Engram Vault (neural traces of forgotten memories)
        c.execute("""
            CREATE TABLE IF NOT EXISTS engram_vault (
                id              TEXT PRIMARY KEY,
                original_mem_id TEXT NOT NULL,
                agent_id        TEXT NOT NULL DEFAULT '',
                neural_trace    TEXT NOT NULL,
                semantic_key    TEXT NOT NULL,
                activation_count INTEGER NOT NULL DEFAULT 0,
                archived_at     REAL NOT NULL,
                last_activated  REAL
            )
        """)

        # Layer 7: Belief Hierarchy (identity + world-model)
        c.execute("""
            CREATE TABLE IF NOT EXISTS belief_hierarchy (
                id          TEXT PRIMARY KEY,
                agent_id    TEXT NOT NULL,
                belief_type TEXT NOT NULL,
                statement   TEXT NOT NULL,
                confidence  REAL NOT NULL DEFAULT 0.8,
                evidence    TEXT NOT NULL DEFAULT '[]',
                created_at  REAL NOT NULL,
                updated_at  REAL NOT NULL,
                version     INTEGER NOT NULL DEFAULT 1
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS bh_agent ON belief_hierarchy(agent_id)")


_init_db()


# ─────────────────────────────────────────────────────────────────────────────
# Embedding helper (NPU first, Ollama fallback)
# ─────────────────────────────────────────────────────────────────────────────

async def _embed(text: str) -> Optional[List[float]]:
    """Embed text via NPU service (8111) or Ollama fallback."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Try NPU first
        try:
            r = await client.post(_NPU_EMBED_URL, json={"text": text})
            if r.status_code == 200:
                data = r.json()
                emb = data.get("embedding") or data.get("embeddings")
                if emb:
                    return emb if isinstance(emb[0], float) else emb[0]
        except Exception:
            pass

        # Fallback to Ollama
        try:
            r = await client.post(
                _OLLAMA_EMBED_URL,
                json={"model": _EMBED_MODEL, "prompt": text},
                timeout=15.0,
            )
            if r.status_code == 200:
                return r.json().get("embedding", [])
        except Exception as e:
            LOG.warning("[GhostRecall] embed fallback failed: %s", e)
    return None


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(x * x for x in b) ** 0.5
    return dot / (mag_a * mag_b + 1e-9)


# ─────────────────────────────────────────────────────────────────────────────
# ChromaDB integration (optional, graceful fallback to SQLite FTS)
# ─────────────────────────────────────────────────────────────────────────────

_chroma_client = None
_chroma_col    = None
_engram_col    = None

def _init_chroma() -> None:
    global _chroma_client, _chroma_col, _engram_col
    try:
        import chromadb
        _chroma_client = chromadb.PersistentClient(path=str(_CHROMA_PATH))
        _chroma_col    = _chroma_client.get_or_create_collection(
            "ghostrecall_explicit",
            metadata={"hnsw:space": "cosine"},
        )
        _engram_col = _chroma_client.get_or_create_collection(
            "ghostrecall_engrams",
            metadata={"hnsw:space": "cosine"},
        )
        LOG.info("[GhostRecall] ChromaDB initialised at %s", _CHROMA_PATH)
    except Exception as e:
        LOG.warning("[GhostRecall] ChromaDB unavailable (%s), using SQLite FTS only", e)

_init_chroma()


# ─────────────────────────────────────────────────────────────────────────────
# GhostRecall
# ─────────────────────────────────────────────────────────────────────────────

class GhostRecall:
    """7-layer neuroscience-backed memory architecture for Aethyro agents."""

    _instance: Optional["GhostRecall"] = None

    def __init__(self):
        # Layer 1: Sensory Buffer (deque, in-process)
        self._sensory: deque = deque(maxlen=200)

        # Layer 2: Short-Term Cache (dict, in-process)
        self._short_term: Dict[str, Tuple[str, float]] = {}  # key → (content, expires_at)

        self._lock = asyncio.Lock()

    @classmethod
    def instance(cls) -> "GhostRecall":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Layer 1: Sensory ──────────────────────────────────────────────────────

    def sense(self, token: str, meta: Dict | None = None) -> None:
        """Record a raw token/event in the sensory buffer."""
        self._sensory.append({
            "token": token[:500],
            "meta": meta or {},
            "ts": time.time(),
        })

    def sensory_flush(self) -> List[Dict]:
        """Return and clear all non-expired sensory tokens."""
        now = time.time()
        alive = [s for s in self._sensory if now - s["ts"] < SENSORY_TTL_S]
        self._sensory.clear()
        self._sensory.extend(alive)
        return list(alive)

    # ── Layer 2: Short-Term ───────────────────────────────────────────────────

    def short_term_put(self, key: str, content: str, ttl: float = SHORT_TERM_TTL_S) -> None:
        """Store a key-value pair in short-term cache."""
        self._short_term[key] = (content, time.time() + ttl)

    def short_term_get(self, key: str) -> Optional[str]:
        """Retrieve from short-term cache; returns None if expired/missing."""
        if key not in self._short_term:
            return None
        content, expires_at = self._short_term[key]
        if time.time() > expires_at:
            del self._short_term[key]
            return None
        return content

    # ── Layer 3: Working Memory ───────────────────────────────────────────────

    def working_put(self, session_id: str, content: str,
                    agent_id: str = "", role: str = "system",
                    ttl: float = 3600.0) -> str:
        """Store a session-scoped working memory entry."""
        now = time.time()
        rec_id = str(uuid.uuid4())
        with _conn() as c:
            c.execute(
                """
                INSERT INTO working_memory
                    (id, session_id, agent_id, content, role, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (rec_id, session_id, agent_id, content, role, now, now + ttl),
            )
        return rec_id

    def working_get(self, session_id: str, limit: int = 20) -> List[Dict]:
        """Return active (non-expired) working memory for a session."""
        now = time.time()
        with _conn() as c:
            rows = c.execute(
                "SELECT * FROM working_memory WHERE session_id=? AND expires_at>? "
                "ORDER BY created_at ASC LIMIT ?",
                (session_id, now, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Layer 4: Explicit Long-Term ───────────────────────────────────────────

    async def store(
        self,
        agent_id: str,
        content: str,
        user_id: str = "system",
        tags: List[str] | None = None,
        importance: float = 0.5,
        summary: str = "",
        valid_duration_s: float | None = None,  # None = permanent
    ) -> str:
        """
        Store a memory in Explicit Long-Term layer.
        Returns the memory ID.
        """
        from memory.iron_dome import dome_write  # avoid circular import

        now     = time.time()
        mem_id  = str(uuid.uuid4())
        tags_s  = json.dumps(tags or [])
        invalid = (now + valid_duration_s) if valid_duration_s else None

        with _conn() as c:
            c.execute(
                """
                INSERT INTO explicit_memory
                    (id, agent_id, user_id, content, summary, tags, importance,
                     confidence, utility, access_count, valid_at, invalid_at,
                     created_at, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1.0, 0.5, 0, ?, ?, ?, ?)
                """,
                (mem_id, agent_id, user_id, content, summary or content[:120],
                 tags_s, importance, now, invalid, now, now),
            )

        # Index in ChromaDB if available
        if _chroma_col is not None:
            try:
                emb = await _embed(content)
                if emb:
                    _chroma_col.add(
                        ids=[mem_id],
                        embeddings=[emb],
                        documents=[content[:1000]],
                        metadatas=[{
                            "agent_id":   agent_id,
                            "user_id":    user_id,
                            "importance": str(importance),
                            "tags":       json.dumps(tags or []),
                            "valid_at":   str(now),
                        }],
                    )
            except Exception as e:
                LOG.warning("[GhostRecall] ChromaDB index failed: %s", e)

        # Log to Iron Dome (async wrapper avoids blocking the event loop)
        from memory.iron_dome import dome_write_async
        await dome_write_async("GhostRecall", "memory_write", {
            "mem_id": mem_id, "agent_id": agent_id, "importance": importance,
        })

        LOG.debug("[GhostRecall] stored %s for %s", mem_id[:8], agent_id)
        return mem_id

    async def recall(
        self,
        query: str,
        agent_id: str | None = None,
        user_id: str | None = None,
        top_k: int = 5,
        min_importance: float = 0.0,
        include_engrams: bool = True,
    ) -> List[Dict]:
        """
        Semantic recall from Explicit Long-Term + Engram Vault.
        Falls back to SQLite LIKE search if ChromaDB/embeddings unavailable.
        """
        now = time.time()
        results: List[Dict] = []

        # ChromaDB semantic search
        if _chroma_col is not None:
            try:
                emb = await _embed(query)
                if emb:
                    # Build ChromaDB where clause (must use $and for multiple conditions)
                    where_conds = []
                    if agent_id:
                        where_conds.append({"agent_id": {"$eq": agent_id}})
                    # valid_at filter: only return non-expired memories
                    # (skip — ChromaDB metadata values are strings, complex time compare is fragile)

                    if len(where_conds) == 0:
                        chroma_where = None
                    elif len(where_conds) == 1:
                        chroma_where = where_conds[0]
                    else:
                        chroma_where = {"$and": where_conds}

                    # Guard n_results against empty collection (ChromaDB raises
                    # if n_results > number of documents in the collection).
                    col_count = _chroma_col.count()
                    if col_count == 0:
                        raise ValueError("ChromaDB collection is empty — skip to SQLite fallback")
                    chroma_results = _chroma_col.query(
                        query_embeddings=[emb],
                        n_results=min(top_k * 2, 20, col_count),
                        where=chroma_where,
                    )
                    # Safe indexing: ChromaDB can return empty lists when all
                    # results are filtered out by the where clause.
                    raw_ids   = chroma_results.get("ids")   or []
                    raw_dists = chroma_results.get("distances") or []
                    ids_list  = raw_ids[0]   if raw_ids   else []
                    dists_list = raw_dists[0] if raw_dists else []
                    for i, doc_id in enumerate(ids_list):
                        row = self._get_explicit(doc_id)
                        if row and (not row["invalid_at"] or row["invalid_at"] > now):
                            if row["importance"] >= min_importance:
                                dist  = dists_list[i] if i < len(dists_list) else 1.0
                                score = 1.0 - dist  # cosine distance → similarity
                                results.append({**row, "relevance": round(score, 4)})
            except Exception as e:
                LOG.warning("[GhostRecall] ChromaDB recall failed: %s", e)

        # SQLite fallback / supplement
        if len(results) < top_k:
            with _conn() as c:
                conds = ["(invalid_at IS NULL OR invalid_at > ?)"]
                params: List[Any] = [now]
                if agent_id:
                    conds.append("agent_id=?")
                    params.append(agent_id)
                if user_id:
                    conds.append("user_id=?")
                    params.append(user_id)
                conds.append("importance>=?")
                params.append(min_importance)
                q_lower = query.lower()
                conds.append("(LOWER(content) LIKE ? OR LOWER(tags) LIKE ?)")
                params += [f"%{q_lower}%", f"%{q_lower}%"]

                rows = c.execute(
                    f"SELECT * FROM explicit_memory WHERE {' AND '.join(conds)} "
                    f"ORDER BY importance DESC, last_accessed DESC LIMIT ?",
                    params + [top_k],
                ).fetchall()

            existing_ids = {r["id"] for r in results}
            for row in rows:
                if row["id"] not in existing_ids:
                    results.append({**dict(row), "relevance": 0.5})

        # Engram Vault — check for reactivatable neural traces
        if include_engrams and len(results) < top_k:
            engrams = await self._reactivate_engrams(query, top_k - len(results))
            results.extend(engrams)

        # Update access counts
        accessed_ids = [r["id"] for r in results if "access_count" in r]
        if accessed_ids:
            now2 = time.time()
            with _conn() as c:
                for mid in accessed_ids:
                    c.execute(
                        "UPDATE explicit_memory SET access_count=access_count+1, last_accessed=? WHERE id=?",
                        (now2, mid),
                    )

        return sorted(results, key=lambda x: x.get("relevance", 0.5), reverse=True)[:top_k]

    def _get_explicit(self, mem_id: str) -> Optional[Dict]:
        with _conn() as c:
            row = c.execute(
                "SELECT * FROM explicit_memory WHERE id=?", (mem_id,)
            ).fetchone()
        return dict(row) if row else None

    # ── Layer 5: Implicit / Skill ─────────────────────────────────────────────

    def skill_put(
        self,
        agent_id: str,
        skill_name: str,
        description: str,
        soft_prompt: str,
        trigger_keywords: List[str] | None = None,
    ) -> str:
        """Store a procedural skill as a soft-prompt injection."""
        now = time.time()
        skill_id = str(uuid.uuid4())
        with _conn() as c:
            # upsert by agent_id + skill_name
            existing = c.execute(
                "SELECT id FROM skill_memory WHERE agent_id=? AND skill_name=?",
                (agent_id, skill_name),
            ).fetchone()
            if existing:
                c.execute(
                    "UPDATE skill_memory SET description=?, soft_prompt=?, trigger_keywords=?, updated_at=? WHERE id=?",
                    (description, soft_prompt, json.dumps(trigger_keywords or []), now, existing["id"]),
                )
                return existing["id"]
            c.execute(
                """
                INSERT INTO skill_memory
                    (id, agent_id, skill_name, description, soft_prompt, trigger_keywords, use_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (skill_id, agent_id, skill_name, description, soft_prompt,
                 json.dumps(trigger_keywords or []), now, now),
            )
        return skill_id

    def skill_match(self, agent_id: str, query: str) -> List[Dict]:
        """Return skills whose trigger_keywords match the query."""
        q_lower = query.lower()
        with _conn() as c:
            rows = c.execute(
                "SELECT * FROM skill_memory WHERE agent_id=? ORDER BY use_count DESC",
                (agent_id,),
            ).fetchall()
        matched = []
        for row in rows:
            keywords = json.loads(row["trigger_keywords"] or "[]")
            if any(kw.lower() in q_lower for kw in keywords):
                matched.append(dict(row))
        return matched

    # ── Layer 6: Engram Vault ─────────────────────────────────────────────────

    async def archive_to_engram(self, mem_id: str) -> Optional[str]:
        """
        Archive an explicit memory as a neural trace in the Engram Vault.
        Marks the explicit memory as invalid. Returns engram ID.
        """
        mem = self._get_explicit(mem_id)
        if not mem:
            return None

        now = time.time()
        engram_id = str(uuid.uuid4())
        semantic_key = hashlib.sha256(mem["content"].encode()).hexdigest()[:32]

        with _conn() as c:
            c.execute(
                """
                INSERT INTO engram_vault
                    (id, original_mem_id, agent_id, neural_trace, semantic_key,
                     activation_count, archived_at, last_activated)
                VALUES (?, ?, ?, ?, ?, 0, ?, NULL)
                """,
                (engram_id, mem_id, mem["agent_id"],
                 mem["content"][:2000], semantic_key, now),
            )
            # Invalidate the explicit memory (valid_at/invalid_at temporal edge)
            c.execute(
                "UPDATE explicit_memory SET invalid_at=? WHERE id=?",
                (now, mem_id),
            )

        # Add to Engram ChromaDB collection
        if _engram_col is not None:
            try:
                emb = await _embed(mem["content"])
                if emb:
                    _engram_col.add(
                        ids=[engram_id],
                        embeddings=[emb],
                        documents=[mem["content"][:1000]],
                        metadatas=[{"agent_id": mem["agent_id"], "semantic_key": semantic_key}],
                    )
            except Exception as e:
                LOG.warning("[GhostRecall] Engram ChromaDB index failed: %s", e)

        LOG.debug("[GhostRecall] archived %s → engram %s", mem_id[:8], engram_id[:8])
        return engram_id

    async def _reactivate_engrams(self, query: str, top_k: int) -> List[Dict]:
        """Search Engram Vault and reactivate matching neural traces."""
        results = []
        if _engram_col is not None:
            try:
                emb = await _embed(query)
                if emb:
                    eng_count = _engram_col.count()
                    if eng_count == 0:
                        return results
                    res = _engram_col.query(
                        query_embeddings=[emb],
                        n_results=min(top_k, eng_count),
                    )
                    raw_ids   = res.get("ids")       or []
                    raw_dists = res.get("distances") or []
                    ids_list  = raw_ids[0]   if raw_ids   else []
                    dists_list = raw_dists[0] if raw_dists else []
                    for i, eng_id in enumerate(ids_list):
                        with _conn() as c:
                            row = c.execute(
                                "SELECT * FROM engram_vault WHERE id=?", (eng_id,)
                            ).fetchone()
                            if row:
                                c.execute(
                                    "UPDATE engram_vault SET activation_count=activation_count+1, last_activated=? WHERE id=?",
                                    (time.time(), eng_id),
                                )
                        if row:
                            dist = dists_list[i] if i < len(dists_list) else 1.0
                            results.append({
                                "id": row["id"],
                                "content": row["neural_trace"],
                                "agent_id": row["agent_id"],
                                "source": "engram_vault",
                                "relevance": round(1.0 - dist, 4),
                                "importance": 0.3,  # engrams have lower priority
                            })
            except Exception as e:
                LOG.debug("[GhostRecall] Engram reactivation: %s", e)
        return results

    # ── Layer 7: Belief Hierarchy ─────────────────────────────────────────────

    def belief_put(
        self,
        agent_id: str,
        belief_type: str,
        statement: str,
        confidence: float = 0.8,
        evidence: List[str] | None = None,
    ) -> str:
        """Store or reconsolidate a belief for an agent."""
        now = time.time()
        belief_id = str(uuid.uuid4())
        with _conn() as c:
            existing = c.execute(
                "SELECT id, version FROM belief_hierarchy WHERE agent_id=? AND belief_type=? AND statement=?",
                (agent_id, belief_type, statement),
            ).fetchone()
            if existing:
                new_version = existing["version"] + 1
                c.execute(
                    "UPDATE belief_hierarchy SET confidence=?, evidence=?, updated_at=?, version=? WHERE id=?",
                    (confidence, json.dumps(evidence or []), now, new_version, existing["id"]),
                )
                return existing["id"]
            c.execute(
                """
                INSERT INTO belief_hierarchy
                    (id, agent_id, belief_type, statement, confidence, evidence, created_at, updated_at, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (belief_id, agent_id, belief_type, statement,
                 confidence, json.dumps(evidence or []), now, now),
            )
        return belief_id

    def beliefs_get(self, agent_id: str) -> List[Dict]:
        with _conn() as c:
            rows = c.execute(
                "SELECT * FROM belief_hierarchy WHERE agent_id=? ORDER BY confidence DESC",
                (agent_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Context Builder ───────────────────────────────────────────────────────

    async def build_context(
        self,
        session_id: str,
        query: str,
        agent_id: str = "",
        user_id: str = "system",
        max_chars: int = CONTEXT_BUDGET_CHARS,
    ) -> str:
        """
        Build a context block from all memory layers for injection into prompts.
        Returns a formatted string ≤ max_chars.
        """
        parts: List[str] = []
        budget = max_chars

        # Layer 7: Beliefs
        if agent_id:
            beliefs = self.beliefs_get(agent_id)
            if beliefs:
                block = "### Core Beliefs\n" + "\n".join(
                    f"- [{b['belief_type']}] {b['statement']} (confidence={b['confidence']:.2f})"
                    for b in beliefs[:5]
                )
                parts.append(block[:400])
                budget -= len(block)

        # Layer 5: Skills
        if agent_id:
            skills = self.skill_match(agent_id, query)
            if skills:
                block = "### Relevant Skills\n" + "\n".join(
                    f"- {s['skill_name']}: {s['soft_prompt'][:200]}"
                    for s in skills[:3]
                )
                parts.append(block[:600])
                budget -= len(block)

        # Layer 3: Working memory
        working = self.working_get(session_id, limit=10)
        if working:
            block = "### Active Context\n" + "\n".join(
                f"[{w['role']}] {w['content'][:300]}" for w in working
            )
            parts.append(block[:1000])
            budget -= len(block)

        # Layer 4+6: Semantic recall
        if budget > 200:
            memories = await self.recall(query, agent_id=agent_id, user_id=user_id, top_k=5)
            if memories:
                block = "### Recalled Knowledge\n" + "\n".join(
                    f"- {m['content'][:300]} [relevance={m.get('relevance', 0):.2f}]"
                    for m in memories
                )
                parts.append(block[:min(budget, 2000)])

        return "\n\n".join(parts)

    # ── Maintenance ───────────────────────────────────────────────────────────

    async def prune_expired(self) -> int:
        """Archive expired memories to Engram Vault. Returns count archived."""
        now = time.time()
        with _conn() as c:
            expired = c.execute(
                "SELECT id FROM explicit_memory WHERE invalid_at IS NOT NULL AND invalid_at < ? LIMIT 100",
                (now,),
            ).fetchall()

        archived = 0
        for row in expired:
            await self.archive_to_engram(row["id"])
            archived += 1

        LOG.info("[GhostRecall] pruned %d expired memories → Engram Vault", archived)
        return archived

    def stats(self) -> Dict:
        with _conn() as c:
            explicit = c.execute(
                "SELECT COUNT(*) FROM explicit_memory WHERE invalid_at IS NULL"
            ).fetchone()[0]
            engrams = c.execute("SELECT COUNT(*) FROM engram_vault").fetchone()[0]
            skills  = c.execute("SELECT COUNT(*) FROM skill_memory").fetchone()[0]
            beliefs = c.execute("SELECT COUNT(*) FROM belief_hierarchy").fetchone()[0]
            working = c.execute("SELECT COUNT(*) FROM working_memory WHERE expires_at>?", (time.time(),)).fetchone()[0]
        return {
            "explicit_active": explicit,
            "engram_vault":    engrams,
            "skills":          skills,
            "beliefs":         beliefs,
            "working_active":  working,
            "sensory_buffer":  len(self._sensory),
            "short_term_keys": len(self._short_term),
        }


# ── Singleton ─────────────────────────────────────────────────────────────────
ghost = GhostRecall.instance()
