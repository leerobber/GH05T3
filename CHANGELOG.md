# Changelog

All notable changes to GH05T3 are tracked here.
Entries are produced automatically by `.github/workflows/release.yml` on every push to `main`.

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
