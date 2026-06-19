# Changelog

All notable changes to GH05T3 are tracked here.
Entries are produced automatically by `.github/workflows/release.yml` on every push to `main`.

## v0.3.0 — 2026-06-19

### What changed since v0.2.2

#### Features
- feat(oss): add OSS packages required for pact tests and /oss API surface (d457d29)

### Stats
- 1 commits
- 1 contributor(s)


## v0.2.2 — 2026-06-19

### What changed since v0.2.1

#### Fixes
- fix(ci): add v1_router, unblock pact jobs, skip mesh contract in backend gate (40560cc)

### Stats
- 1 commits
- 1 contributor(s)


## v0.2.1 — 2026-06-19

### What changed since v0.2.0

#### Fixes
- fix(ci): remove invalid secrets in job if conditions (d532552)

### Stats
- 1 commits
- 1 contributor(s)


## v0.2.0 — 2026-06-19

### What changed since v0.1.0

#### Features
- feat(pact): consumer/provider contract tests, CI gates, and OpenAPI exports (5b9dd7b)
- feat(train): Intelligence Training profile for systems/code/data reasoning (11de672)
- feat(train): Sovereign Train Kernel — agent-native, no TRL (e93314c)
- feat(training): forge-only fast smoke mode with Windows memory fixes (812a17d)
- feat(inference): Omni MoE routing with novel AI/ML advancements (4d4aa0f)
- feat(oss): Elite OmniStrand training with scientific domains and genetics paradigm (7234ca2)
- feat(oss): Omni Forge agency training layer with quality gate and gold export (459fbfe)
- feat(oss): Phase 1 completion — Stripe NC settlement, world scaffold, gateway health (b42275a)
- feat(oss): Phase 1 foundation layer with live gateway integration (35b9e4f)
- feat(ghost-chat): add lightweight streaming CLI agent (15131f3)
- feat(site-agents): add contractor multi-agent system (11239b9)
- feat(sage): enhanced cycle with self-refinement + continuous evolution runner (07bd0d3)
- feat(runner): auto-detect best available Ollama model for SAGE cycles (887dbab)
- feat(evolution): upgrade to 4500-cell MAP-Elites + evaluator API — matches working Windows build (a1f8a38)
- feat(sage): wire MAP-Elites ask()/tell() into run_sage_cycle() — active evolution (35bba3a)
- feat: pyribs MAP-Elites + Vickrey auction + validator + modular tools + sandbox (3cc029a)
- feat(lemonade): CPU-native STT+TTS — 780M stays on chat full-time (e235b6c)
- feat(run.bat): auto-load Lemonade 780M model on startup (5e98a55)
- feat(lemonade): AMD Radeon 780M iGPU via Lemonade — chat + STT + TTS + image gen (a4b11a8)
- feat(training): domain-specific LoRA adapter training + LLM_PROVIDER docs (7680e6e)
- feat(economy+marketplace): local ledger, LoRAFarm, agent marketplace, real-world ingestion (29d6718)
- feat(arch): elite-tier local AI upgrades — MoE routing, fp8 KV cache, BM25 memory, circuit breakers (54df68f)

#### Fixes
- fix(train): safe ChatML truncation, autocast, final loss rolling mean (4a0b4a3)
- fix: restore start_ngrok.ps1 for Windows Terminal tunnel tab (9af9636)
- Merge pull request #16 from leerobber/claude/local-ai-agents-arch-f80yf4 (8b5662b)
- fix(supervisor): bypass aethyro license gate for owner-managed services (444bb80)
- fix: ghost_trainer.py SyntaxError — hoist global decl to top of main() (c327a6f)
- fix: rotation broken by dotenv; raise proposer temperature to 0.85 (dd49c48)
- fix: proposal collapse — dedup buffer in sage_enhanced.py (e1cf4df)
- fix(ollama): keep_alive 2m + VRAM-aware model fallback — eliminates 404 cascade (732f26d)
- fix(ollama): default gateway URL to localhost:11434 — removes need for env var (ba62593)
- fix(runner): write OLLAMA_GATEWAY_URL to env so ghost_llm sees Ollama (d8a65ca)
- fix(ollama): use native /api/chat endpoint — fixes 404 on SAGE cycles (1f89556)
- fix(lemonade): correct Whisper model name + single-model load on startup (1edba54)
- fix(marketplace+cb): ledger table init + HALF_OPEN probe timeout (9fedb11)
- fix(review): address all 15 remaining coderabbitai/qodo review findings (fa05af0)
- fix(review): address qodo + coderabbitai PR review findings (9ed36ba)
- fix(review): address 6 code-review findings on economy/marketplace (a4c2c04)
- fix(review): address all Gemini Code Assist review comments (ad004b6)

#### Maintenance
- chore: add pytest test-mode conftest and slack token CLI helper (dc42cb0)
- chore(gitignore): ignore frontend/build and hermes venv (c2c0aea)
- chore(backend): add manual license-bypass launchers for backend/gateway (501174b)

#### CI
- fix(marketplace+cb): ledger table init + HALF_OPEN probe timeout (9fedb11)

#### Other
- merge origin/main: reconcile remote CI with pact contract testing jobs (bf13fbc)
- platform: smoke checks, start-missing, reliable inference startup on Windows (0bbf859)
- oss: phase 2 world wire, gateway memory/broadcast fixes, chroma embed dim (03f9f67)
- platform: run_stack orchestrator, vite env fix, deploy tests (f13234d)
- merge: resolve conflicts with main — keep SQLite fix, accept .env.example deletion (d47b792)
- Update backend/agent_marketplace.py (22b08b3)
- merge: integrate main (alignment + chaos + skill-tiers) into feature branch (72544c3)

### Stats
- 49 commits
- 3 contributor(s)


## v0.1.0 — 2026-06-15

### What changed since v0.0.0

#### Features
- feat(repo): fold standalone subsystems, code-split frontend, add release pipeline (a094fef)
- feat: local economy ledger, LoRAFarm, agent marketplace & real-world job ingestion (#14) (de1b6ed)
- feat(alignment): Sentinel gate, entropy drift, War Room chaos, T1-T4 skill tiers (2198740)
- feat(arch): elite-tier local AI — MoE routing, fp8 KV cache, BM25 memory, circuit breakers (b219dde)
- Merge pull request #10 from leerobber/claude/sovereign-mesh-podcast-ui-nkkvud (209ec8b)
- feat: vLLM/NVFP4 inference, packing training, InferenceBadge UI (ec3d5b7)
- Merge pull request #9 from leerobber/claude/sovereign-mesh-podcast-ui-nkkvud (3fe3de4)
- feat(sovereign-ui): scaffold Next.js 15 + Supabase Realtime podcast UI (98909bd)
- feat(ibac): IBAC capability MAC integration -- Step 3 complete (26a752d)
- feat: PolicyStore + file-based per-agent policy layer (b89c5f9)
- feat: IBAC parallel macro checker QuorumGate enforcement (305bae1)
- feat(sage): full SAGE/KAIROS self-improvement engine (62b4b9a)
- feat(sovereignnation): Phi-3.5-mini GPU service + full pipeline/skills integration (779059c)
- feat: SovereignNation full stack — enterprise demo, Avery training pipeline, supervisor hardening (50b5f15)
- feat: CHRONICLE agent (Mira Solis) + GH05T3 inference + Stripe integration (fe4d509)
- feat: SovereignNation Training Accelerator v5 + training datasets (7ab3863)
- feat: add GH05T3 ECC bundle (.claude, .agents, .codex config) (ef614e1)
- feat: launchers, training pipeline, desktop tools, tests (5ecc232)
- feat(frontend): ChatInterface overhaul, yarn deps update (52eb4b1)
- feat: backend expansion — new agents, ghostscript pkg, rate-limit cascade (40b8911)
- feat: holographic SwarmBus UI, ETH/MEM agent fix, system prompt simplification (97d4d25)
- feat(ghostscript): variables, async/await, pipeline operator, real LLM wiring (873b3c6)
- fix(frontend): remove blocking Emergent/PostHog scripts causing blank page (dc317a9)
- feat(tailscale): auto-detect Tailscale IP, use as primary remote URL (4964500)
- feat(tier2+3): LoRA fine-tuning, W&B, Telegram/Slack, Prometheus, Qdrant, Jira (d77d1e6)
- feat(training): wire CostTracker into pipeline status + add budget env vars to installers (2e9834c)
- feat(training): free + hybrid dataset pipeline for fine-tuning (a96d8a5)
- feat(tuning): 5-part resource tuning for single-machine operation (5274ec0)
- feat(setup): full single-machine setup with Android access (ad7fb55)
- feat(llm): replace emergentintegrations with native multi-provider router (c8b6c8b)
- feat(gpu): Claude-first routing + semaphore-guarded Ollama calls (a747a88)
- feat: full Windows v3 wiring — one-click install + auto-start (043e677)
- feat: auto-popup secrets modal on first boot (c8c7ea7)
- feat: add in-dashboard secrets entry (Anthropic key + GitHub PAT) (4ed857c)
- feat: wire gateway_v3 + SwarmBusPanel into the live app (d92f2fe)
- feat: integrate GH05T3 v3 — SwarmBus, specialists, Claude API, GitHub automation (3d00afb)

#### Fixes
- fix(test-plan): two bugs found during test plan execution (611660f)
- Merge pull request #11 from leerobber/claude/repos-workflow-task-runs-qpdd6s (8e8478f)
- fix(ci): harden gate() skip, asyncio_mode, and stale Slack branch (7a31072)
- fix: address all Gemini review comments (6 issues) (501bdc7)
- fix(sovereign-ui): address Gemini code review — hydration, stale closure, fonts (323f61b)
- fix(ci): set AETHYRO_SKIP_LICENSE=1 for backend pytest step (806f012)
- fix(aethyro_kernel): address Gemini code review findings (2c9cc0a)
- fix(sage): harden engine against 8 critical/high bugs from code review (3d9e96c)
- fix(ci): make FallbackLLMClient.set_bus sync to fix backend test failure (2c0a323)
- fix(ci+economy): replace emergentagent.com with SovereignCore; unit-only CI (ae8d0c3)
- fix: make is_gh05t3_owned_path work cross-platform (8684ef4)
- fix: run.bat launcher, LAN IP frontend build, training datasets (8350ad3)
- fix: hard-block fabricated progress reports in system prompt (152eed5)
- fix(frontend): remove blocking Emergent/PostHog scripts causing blank page (dc317a9)
- fix(llm): hot-reload keys from .env so gateway-saved keys work in server process (27b1133)
- fix(llm): proper fallback when Anthropic quota/rate-limit exceeded (b7fbbdd)
- fix(encoding): replace Unicode chars with ASCII, add UTF-8 BOM to install.ps1 (c601f3a)
- fix(collectors): NVD 90-day windows — API rejects ranges >120 days without key (1849776)
- fix: remove broken editable install from requirements.txt; add CLAUDE.md (a3a859d)
- fix: install.ps1 installs in-place, eliminates self-copy error (ff0e50d)

#### Maintenance
- chore(cleanup): reorganize root + remove dead code (4519186)
- chore(cleanup): security + portability fixes (a136433)
- chore(ci): bump GitHub actions to Node 24 majors (765530e)
- chore(training): checkpoint datasets — bug_bounty, cve_patterns, reasoning_chains (be86855)
- fix(frontend): remove blocking Emergent/PostHog scripts causing blank page (dc317a9)
- chore(training): checkpoint bug_bounty dataset (313 examples) (67177ae)
- chore(training): dataset checkpoint - cve_patterns complete, reasoning_chains 732/800, bug_bounty 246/1200 (efd940e)
- chore(training): checkpoint bug_bounty dataset (217 examples) (bb8e2e7)
- chore(training): checkpoint bug_bounty dataset (202 examples) (70f0289)
- chore: ignore GH05T3 runtime files in .gitignore (e603796)
- chore(training): checkpoint bug_bounty dataset (178 examples); add yarn.lock (c1b2fb7)
- chore(training): checkpoint datasets (cve_patterns 800 complete, bug_bounty 76) (eec2323)
- chore(training): checkpoint datasets (reasoning_chains 732, cve_patterns 143) (b3f0909)
- chore(training): checkpoint datasets (adversarial_defense 1198, reasoning_chains 57) (4aab3c3)
- chore(training): checkpoint adversarial_defense dataset (580 examples) (cf547bf)
- chore: remove backend/swarm.py (superseded by swarm_legacy.py) (6caea8d)

#### CI
- ci: set AETHYRO_SKIP_LICENSE=1 in backend test step (c5fa594)
- ci: add websockets and backend URL for backend tests (03a5b31)
- ci: include requests for backend pytest collection (875f494)
- ci: add Slack notification workflow for SovereignNation (db19e9c)

#### Docs
- docs: Add comprehensive free fallback LLM system guide (8b73798)

#### Other
- Auto-generated changes (f03db22)
- auto-commit for 42f00577-d20c-416a-857c-1d4c30d311e4 (e092f55)
- Add Aethyro AIOS System Kernel Runtime v2.0 (9a94c4d)
- [SAGE-gitops-e2e-001] E2E GitOps test: SAGE version marker (6855c9e)
- Embed Aethyro license public key in module (self-contained, no .pem dependency) (3088b95)
- Add Aethyro license gate: GH05T3 backend+gateway require active trial/subscription (d4b9aa1)
- Switch frontend to Vite: clean build, remove emergent/craco deps (467bf56)
- Add free fallback LLM routing when Anthropic API credits exhausted (a5dddf9)
- Fix CI to pass in full: live-skip conftest, pytest markers, test crash fixes (91c1851)
- Add multi-provider training pipeline — Mistral, DPO generation, 29k+ SFT pairs (899eadd)
- Fix ghost_trainer: verifier errors skip cycle instead of recording false FAILs (57c414e)
- Add multi-provider support to mentor_trainer + multiturn_gen (e80039b)
- Add Kaggle fine-tune notebook, multi-turn dataset generator, rebuild frontend (30f8515)
- Security & performance improvements: multi-agent hardening + parallel dataset generation (eaed830)
- Production hardening: CI/CD, token enforcement, Tailscale auto-detect (47cce67)
- Cleanup: .gitignore + docs + HuggingFace model cards (707d0a0)
- Rebuild frontend: PeersPanel mesh contract rewrite live (47c0d8a)
- Add training utility scripts (e098182)
- Add business + Iron Mesa training datasets and pair generators (8655581)
- Kairos dataset generator, mentor trainer, Avery flywheel (218aa3b)
- Training ops tooling: herald, cmd_listener, start_training.sh (afb30df)
- RunPod: network volume support + on-pod LoRA merge pipeline (7d6f248)
- Wire security datasets into SFT pipeline + expand training data (db03bd9)
- Mesh contract API + PeersPanel rewrite (6e57153)
- Expand Iron Mesa training to 24 pairs — full Codex added (3aea6a4)
- Add Iron Mesa doctrine training data (12 pairs) + wire into pipeline (6283f42)
- Grow web_research.jsonl to 306 pairs — full curriculum resource scrape (d0921f6)
- Add services/web_researcher.py — deep academic web scraping for training data (253f6c1)
- Grow web_research.jsonl to 220 pairs via 15-topic deep economy research (00eb25a)
- Force-reinstall transformers 4.47.1 over system transformers 5.8.1 (d83aca6)
- Pin transformers==4.47.1 + trl==0.12.2 + peft==0.14.0 to fix MoE import error (b116836)
- Bulk web_research.jsonl to 168 pairs via deep academic research mode (be4d59a)
- Expand web_research.jsonl to 110 pairs via Wikipedia link-following (257241f)
- Add 12 Wikipedia economics pairs to web_research.jsonl (68 total) (eb0d58c)
- Add web_research.jsonl to SFT pipeline (56 web-scraped pairs) (3c9ccd1)
- Replace unsloth with standard PEFT for RunPod SFT training (89291f4)
- runpod_launcher: fix UnicodeEncodeError on Windows (arrow char cp1252) (cec0ffa)
- pre_train: include real economy mentor data in SFT combined split (dd6a2e8)
- Add real economy training data (219 records from live DB tick 12557) (3470604)
- Add mentor and sovereign nation training data (8d28e78)
- Add kairos_log.jsonl runtime artifact (2114b96)
- Fix LLM fallback chain: silent quota failover + guaranteed Ollama fallback (15af2fe)
- data(training): generation checkpoint — 375 adversarial_defense examples (0e63bf9)
- data(training): partial generated datasets — generation in progress (be26fcc)
- data(training): pre-collected raw datasets — skip network collection on first run (2381c0a)
- Add single-instance + remote peers mesh (TatorTot / Laptop / Cloud) (0bf15ad)
- Harden backend against MongoDB startup race + missing .env (653802f)
- Fix 500 on /api/state + frontend suggest bug (b8b333c)
- Enhance and complete autotelic goals system — full CRUD + lifecycle (c227d51)
- Add comprehensive advanced training test suite — 124/124 passing (92c557c)
- Fix NVIDIA batch crash and locked-venv deletion (5d84503)
- Fix Permission denied on .venv\python.exe during reinstall (916cdd3)
- Strip all non-ASCII from install.ps1 and run.bat (18375fc)
- Fix mongod not found: add MongoDB bin to PATH in install.ps1 and run.bat (4526d90)
- Fix frontend crash: hardcode localhost defaults, fix GW3_URL default port (3f7590c)
- Fix Windows install: remove bad packages, add emergentintegrations shim, fix run.bat (6ced32c)
- auto-commit for 0479b076-4cad-415c-a7ff-2ef81768f258 (452523f)
- auto-commit for 05d88f19-e53c-451b-b296-9d3b3f4e012a (6e41a52)
- auto-commit for 32d76bcf-e419-4f1b-b601-4b76f59b521f (1a7e0b8)
- auto-commit for ee5638bb-b11d-4cf9-a10a-5f5d2275e8b5 (b5cb39f)
- auto-commit for e2e3fcc5-a399-476e-bba9-032539dba0e7 (adc0dda)
- auto-commit for 64d661cf-ee8f-4857-99ad-c5e82cafd14e (794adda)
- auto-commit for e971a996-e05c-4d2c-b4fc-006a283c08a2 (0738815)
- auto-commit for f3b8fe52-bd28-4787-9f4a-7c2361bc2d94 (0a30e04)
- auto-commit for 8ec9902d-375a-4d40-b54f-99a83efc5f07 (8a2f928)
- auto-commit for 036031e0-8cef-4a29-9718-220d258108f3 (76c33ab)
- auto-commit for 8b39661e-7428-41dd-bb52-3836cad5fd63 (7eb5fdf)
- auto-commit for 5cb5802b-c821-4648-a94e-0b117ad50c33 (b20f42e)
- auto-commit for 90d97bdd-0997-4211-853c-3c7af192a216 (bd13b1c)
- auto-commit for b708d995-a6c7-4eb7-9533-5a3ac36493d9 (b7e1f90)
- auto-commit for 22bf79ed-3845-4557-bcbd-024f6b9b88e6 (d7f9095)
- auto-commit for c366e235-7749-4556-88d5-acfa5f5b8c0b (d899cdc)
- auto-commit for 5ba5196d-9353-4ebc-be10-bb3c6c5546ed (e0d090f)
- auto-commit for 538e673f-6a78-4941-a1c1-c451159bb0fa (1f34dc3)
- auto-commit for 269e8513-4514-465e-b793-91a561f077da (46d8791)
- auto-commit for 36c669df-05e2-4c98-8ccb-7d6e6f90b9dd (c149c31)
- auto-commit for 05d1e6fe-e955-433f-b7d0-42296ee7f5ca (0d1374a)
- auto-commit for 4d726c8f-ba4b-47d3-865b-f0964a551aa4 (b2dc243)
- auto-commit for cb778fca-3c5f-469e-9f27-dd9449a25c79 (b211e2f)
- Initial commit (eec94db)

### Stats
- 161 commits
- 9 contributor(s)


## Unreleased

### Repo cleanup
- Scrubbed GitHub token from `.git/config` remote URL
- Untracked `frontend/build/` and `.claude/`; tightened `.gitignore` to `**/build/`
- Replaced hard-coded `C:\Users\leer4\GH05T3` in `launcher.py`, `launch_backend.py`, `launch_gateway.py` with `Path(__file__).parent`
- `launch_gateway.py` port `8003` → `8002` (matches CLAUDE.md port map)
- `kairos/kairos.py` f-string backslash fix (Python 3.11+ compatible)
- `main.py` UTF-8 BOM stripped
- Root file count: 100+ → 36
- Moved 70+ scripts to `scripts/training/`, `scripts/runtime/`, `scripts/_archive/`
- Folded `bridge/`, `companion/`, `data_gen/`, `services/web_researcher.py` into `scripts/`
- Moved Windows-only files (`.bat`, `.ps1`, `.hta`, `.html`) to `native/windows/`
- Removed: 3 Kaggle notebooks, `kernel-metadata.json`, `frontend/craco.config.js`, `frontend/plugins/`, root `integrations/` stub, duplicate `Modelfile.avery.q4km`
- Removed `cra-template` and `react-scripts` from `frontend/package.json` (project is on Vite 8)
- Frontend: code-split via manual vendor chunks — single 553 kB chunk → 7 chunks, largest 181 kB (vendor-react)
- Frontend: reorganized `components/ghost/` into `panels/`, `modals/`, `primitives/`
- Fixed `backend/gateway_v3.py` uvicorn entry: `integrations.gateway_v3:app` → `backend.gateway_v3:app`
- Updated `.github/workflows/ci.yml` for new `scripts/` paths
- New top-level `README.md` (port map, quick start, layout, CI notes) + Vite-correct `frontend/README.md`
- New `.github/workflows/release.yml` — auto-tag + GitHub Release + appended CHANGELOG on every push to main
