# GH05T3 — Deployment Readiness Checklist

**Status:** Phase 2 complete. 22/22 backend tests pass. All real (no mocks). Ready for native Emergent deployment with the caveats below.

---

## ✅ Ready now
- [x] FastAPI backend on `:8001`, `/api` prefix, CORS open, supervisor-managed.
- [x] React frontend on `:3000`, uses `REACT_APP_BACKEND_URL`, supervisor-managed.
- [x] MongoDB via `MONGO_URL` / `DB_NAME` (no hardcoding).
- [x] `EMERGENT_LLM_KEY` in `.env` — works on deployment out of the box.
- [x] WebSocket upgrade path `/api/ws` — Emergent ingress supports WS.
- [x] APScheduler starts at boot with cron jobs 03:00 + 04:00 America/New_York.
- [x] All linters pass (`ruff`, `eslint`).
- [x] `data-testid` on every interactive element.
- [x] HCM 146 real 10k-dim vectors seeded once per DB.

## ⚠ Pre-deploy decisions to make
1. **Telegram token** — don't commit your bot token. Configure it **after** deploy via the UI (Telegram panel). Stored in Mongo, not in env.
2. **LLM budget** — each KAIROS cycle = 3 Claude calls (~$0.01). Nightly cron fires 10 cycles @ 03:00 = ~$0.10/night. Top up your Universal Key or cap the schedule.
3. **Scheduler timezone** — hardcoded to `America/New_York`. If your deploy region differs and you want literal wall-clock 3AM local, set it via env. Otherwise it runs at 03:00 ET regardless.
4. **Ollama gateway** — set `OLLAMA_GATEWAY_URL=http://<tailscale-ip>:8000` in deploy env once TatorTot is reachable. Tailscale side-car or subnet router recommended (no static public IP needed). Without it, she falls back to Claude — which is fine.
5. **Cold-start state** — on fresh deploy DB, state seeds automatically with book numbers. If you want to import Robert's real Memory Palace, run `/api/state/reset` then POST custom entries via scripts.

## 🔐 Before going public (if you ever do)
- [ ] Add auth gate (currently personal-use only, no login).
- [ ] Rate-limit `/api/chat` (burns key credits if abused).
- [ ] Scope CORS to your actual frontend origin instead of `*`.
- [ ] Add request logging sanitizer (GhostVeil spec: strip PII before archiving).
- [ ] Lock scheduler toggle behind auth.
- [ ] Set `allow_open=false` on Telegram (it already is by default; first-sender locks).

## 🚀 To deploy
Ask me to deploy — I'll run `deployment_agent`. It scans for hardcoded secrets, port issues, and CORS. All current code is compliant. The only thing you need ready:

- (Optional) Telegram bot token — add after deploy via UI.
- (Optional) Ollama gateway URL — add later via env to flip her brain from cloud to local.

When you're ready, just say **"deploy"**.

---

## Later / stretch (post-deploy)
- WebSocket reconnect backoff w/ jitter.
- Split `server.py` into `routers/` (~660 lines now).
- Lifespan handler instead of deprecated `@app.on_event`.
- Bypass `RequestValidationError` in the Séance exception middleware (422 shouldn't look like a failure lesson).
- Real `pytest -q` in CI before every deploy.
