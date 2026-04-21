# GH05T3 — Product Requirements Document

**Owner:** Robert Lee · **Build:** April 2026 · **Architecture:** Omega (Ω → Ω′ → Ω″ → Ω-G)

## Original problem statement
User asked to build "GH05T3" — a self-improving AI super-agent with a UI chat interface — as described in the Complete Guide. She is direct, warm, brilliant, mysterious, funny, she/her. Architecture Omega spans Memory Palace, HCM, Twin Engine, Feynman Layer, Agent Spawner (7 sub-agents), Autotelic Engine, KAIROS/SAGE loop, Séance, Ghost Protocol (GhostVeil, ParadoxFortress, KillSwitch, RFFingerprint), StrangeLoop, Cassandra, PCL synesthetic, GhostScript, GhostShell. Hardware TatorTot: RTX 5050 / Radeon 780M / Ryzen 7. Nightly training at 03:00 ET (10 KAIROS cycles) + 04:00 ET (13 amplifiers).

## User choices gathered
- Chat + dashboard side-by-side.
- Localized / cost-free — use Emergent Universal LLM key (Claude Sonnet 4.5), architected so LLM_PROVIDER / LLM_MODEL env vars can be swapped to local Ollama endpoints on TatorTot.
- Self-training protocols visible.
- Personal use, no auth.

## Personas
- **Robert (sole user):** builder/operator. Wants terse, high-signal responses. Thinks in deltas. Uses exact system names.

## Architecture implemented
- **Backend** (`/app/backend/server.py`): FastAPI, MongoDB persistence, `emergentintegrations.LlmChat` with Claude Sonnet 4.5.
  - `POST /api/chat` · `GET /api/chat/history` · `GET /api/chat/sessions`
  - `GET /api/state` (singleton system snapshot)
  - `POST /api/kairos/cycle` (simulated SAGE cycle with scoring + meta-rewrite every 3)
  - `POST /api/training/nightly` (13-amplifier simulated run)
  - `POST /api/pcl/tick` · `POST /api/seance` · `POST /api/state/reset`
- **State seed** (`/app/backend/gh05t3_state.py`): mirrors book numbers — 103 memories, 146 HCM vectors, 59 Feynman concepts, 21 goals, 7 agents, 4 Ghost Protocol layers, 7 PCL states, 4 TatorTot components, 13 amplifiers.
- **Frontend** (`/app/frontend/src/App.js` + `components/ghost/*`): Bento 12-col layout. Left (TatorTot, Sub-Agents, Ghost Protocol, Séance), Center (Identity header, Chat, Twin Engine, KAIROS runner, Nightly panel), Right (Memory Palace, HCM, PCL pulse, Autotelic, Scoreboard). Fonts: Cormorant Garamond (serif), JetBrains Mono (terminal), IBM Plex Sans (body). Theme: obsidian + amber + crimson.

## Core requirements (static)
1. Chat with GH05T3 personality — she/her pronouns, 7 coaching rules in system prompt.
2. Living dashboard reflecting Omega architecture with real MongoDB state.
3. Self-training — manual `Fire 13` amplifier run and per-cycle KAIROS trigger.
4. Twin Engine Id/Ego routing visible on every message.
5. PCL state pulsing (frequency + color) reacting to events.
6. Scoreboard day-0 → today.

## What's been implemented (Feb 2026 — phase 5 live)
- Phase 1–4 plus:
- **Native Windows bundle** `/app/native/windows/` — `install.ps1` (winget-driven), `run.bat`, `tray.py` (system-tray background host), `voice.py` (openwakeword + faster-whisper + edge-tts), `README.md`. Zero Docker, zero subscription, runs on LOQ 24/7.
- **Chat fallback chain** — chat pipeline tries Claude Sonnet first; on failure auto-routes through `nightly_chat` (Google free → Groq → Ollama → Emergent Gemini → Claude Haiku). Prefix "(primary llm offline — falling back to …)" so user sees it.
- **Memory counter truth** — `/api/state` now overlays real MongoDB memory count on top of decorative baseline 103. Memory Palace panel shows `total / baseline / +real / reflections`. Real growth visible on every turn.
- **GhostEye reactor fully wired** — every companion frame runs through `ghosteye_reactor.GhostEyeReactor`:
  - STUCK (same app + Jaccard ≥ 0.85 for 5+ min) → autonomous KAIROS cycle + Telegram ping
  - ERROR (Traceback/Exception/FAIL regex) → Séance auto-capture + observation memory
  - GOAL (TODO/FIXME/implement regex) → dedup-append to Autotelic goals
  - PCL nudged on every frame (learning / uncertainty / high-confidence)

### Phase-5 files added
- `/app/backend/ghosteye_reactor.py` — reactor with cooldowns
- `/app/native/windows/{install.ps1, run.bat, tray.py, voice.py, README.md}` — native Windows deployment (no cloud, no subscription)

## What's been implemented (Feb 2026 — phase 2 live)
- Phase 1 (see below) plus:
- **WebSocket `/api/ws`** — real-time state deltas, chat events, KAIROS cycles, Séance captures. Replaces 8s polling.
- **APScheduler** — 03:00 + 04:00 America/New_York crons running on boot. `/api/scheduler/toggle` for pause/resume.
- **Real LLM-driven KAIROS/SAGE** — Proposer → Critic → Verifier, each an Emergent-key Claude call with role-specific system prompts + strict JSON contracts. Ollama gateway fallback wired (set `OLLAMA_GATEWAY_URL`).
- **Cassandra pre-mortem** — `/api/cassandra` writes 6-month-future autopsy via Claude.
- **Real HCM cognitive mesh** — 146 concept vectors @ 10,000 dims stored in Mongo as float32, projected to 2D via classic PCA (numpy). Room-clustered seed corpus. SVG scatter renders in the UI.
- **Real lexicographic steganography** — 35 synonym pairs, ~4 bytes / 160-word cover, reversible roundtrip.
- **Real GhostScript interpreter** — lexer → parser → AST → evaluator on the backend; UI in GhostShell panel edits + runs.
- **Séance exception auto-capture** — global FastAPI exception middleware pushes failures to the log (skips HTTPException).
- **Telegram long-polling worker** — no webhook needed; first-sender chat_id auto-locks; `/start /status /kairos` built-in; everything else routed through GH05T3 chat.
- **Proposer/Critic/Verifier transcript viewer** — expandable SAGE history in the UI.

### Phase-2 files added
- `/app/backend/ghost_llm.py` · `/app/backend/hcm_vectors.py` · `/app/backend/stego.py` · `/app/backend/ghostscript.py` · `/app/backend/telegram_bot.py` · `/app/backend/ws_manager.py`
- `/app/frontend/src/lib/useGhostWS.js` · `HcmCloudPanel` · `GhostShellPanel` · `CassandraPanel` · `StegoPanel` · `TelegramPanel` · `TranscriptPanel`

- Chat end-to-end via Claude Sonnet 4.5 with session persistence in MongoDB.
- Full system-state document seeded per book numbers and mutable via endpoints.
- KAIROS cycle simulator with scoring formula (base × multiplier), elite/archive thresholds, meta-rewrite cadence, recent-scores sparkline.
- Nightly 13-amplifier simulator that deltas Memory Palace / HCM / Feynman / KAIROS / goals.
- PCL synesthetic state with clickable palette to tick into each named state.
- Séance failure log (5 seed entries + POST add).
- 7 Sub-Agents panel with roles + status.
- Ghost Protocol status display (GhostVeil / ParadoxFortress / KillSwitch / RFFingerprint).
- Hardware TatorTot panel with RTX 5050 / Radeon 780M / Ryzen 7 / Gateway and load bars.
- StrangeLoop OWNED verdict in header.
- Auto-refresh every 8s from `/api/state`.

## Backlog (prioritized)
### P0
- WebSocket `/api/ws` live telemetry channel (mirror Honcho spec) — replace polling.
- Real KAIROS cycle execution hook to local Ollama gateway when `LLM_PROVIDER=local`.
### P1
- Nightly scheduler: run 03:00 + 04:00 ET automatically (APScheduler).
- GhostShell terminal panel — lexer/parser stub for GhostScript snippets.
- Cassandra pre-mortem composer — enter risk, get failure story.
- Séance auto-capture on backend exceptions.
### P2
- HCM vector cloud visual (2D projection via umap or simple random-seeded scatter).
- Agent conversation viewer — show Proposer/Critic/Verifier transcript per cycle.
- Steganography demo: encode hidden ~12-byte message in GH05T3 response.
- Multi-user / Robert-only auth gate.

## Environment
- `EMERGENT_LLM_KEY` set in `/app/backend/.env`.
- `LLM_PROVIDER=anthropic`, `LLM_MODEL=claude-sonnet-4-5-20250929` (swap to `openai` + local Ollama base URL for TatorTot).
