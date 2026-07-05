# Security fix + repo hygiene, July 2026

**Status:** Resolved (code fix); rotation of exposed credentials is an
external action, not tracked by a commit

## Hardcoded Slack OAuth secret (highest severity)

`scripts/runtime/get_slack_token.py` (and, on the `claude/fix-multi-gpu-training-2WHKH`
branch, the older root-level `get_slack_token.py`) had a real Slack app
`CLIENT_ID`/`CLIENT_SECRET` pair hardcoded in plaintext — committed and
publicly visible on GitHub, in **three** locations across two public
repos (both here and inherited via the `GH05T3-Sovereign` fork).

Fixed (commits `8fbe9b1` on `main`, `d4be9d9` on
`claude/fix-multi-gpu-training-2WHKH`): both values now come from
`SLACK_CLIENT_ID`/`SLACK_CLIENT_SECRET` env vars, with a clear error
instead of silently running with empty credentials.

**Removing it from the current file does not undo its prior exposure in
git history** — the secret is still visible in the commit history of both
public repos. The client secret itself was rotated at api.slack.com
(external action, not a commit).

## Repo hygiene: generated files that were tracked

Two separate gaps, both following the same shape — `.gitignore` had (or
gained) a rule, but specific files were already tracked from before the
rule existed, so the rule alone didn't stop them from showing up in every
`git status`:

- `backend/C:\Users\leer4\...\palace.db` — a malformed artifact of a known
  Windows-literal-path regression bug. Deleted; the real `palace.db`
  (18MB, already gitignored) was untouched.
- `evolution/kairos_log.jsonl` and `backend/evolution/kairos_log.jsonl` —
  real KAIROS cycle logs. The `backend/` copy's 3 entries were checked
  before untracking: two are the same auto-logged "all inference backends
  offline" health warning (not a real improvement proposal), one is an
  `agent_id: "TEST"` fixture — not real evolution history worth
  preserving in git. Files stayed on disk, just untracked.
- `data_disabled/` had 9 tracked files that were dev/test-run noise, not
  curated data — confirmed before untracking, not assumed: `genomic_fitness.jsonl`
  spans 44 distinct batches over 8 days with `context` values only ever
  `unit_test`/`synthetic_trading`/`saas_product_design`/`living_loop`, and
  `theory_lab_meta.jsonl`/`oss_meta_evolution.jsonl` were byte-identical
  (same MD5), 26.5MB duplicated under two names. Left tracked,
  deliberately: `breakthroughs.jsonl`/`.db` (4 real KAIROS proposals that
  scored above the 0.90 elite threshold — actual curated output, not
  logs), `aethyro_swarm.bin`/`genome_plane.bin` (real ledger/genome-plane
  state), and the real curated training-data files that happen to live in
  the same directory.
- New `.gitignore` entries: `models/`, `backend/training/checkpoints/`,
  `backend/evolution/map_elites_archive.pkl`, `llama-cpp/` and
  `sovereign-releases/` (both nested repos with their own `.git` — not
  this repo's source), `frontend/build/`, `terminals/`, `tunnel_url.txt`.

## Still open, not part of this cleanup

Several plaintext credential files were found in local, non-git-tracked
folders outside this repo entirely (a duplicate `OneDrive`-synced copy of
this project, a duplicate Jarvis copy) — moved out of cloud sync, pending
rotation and deletion. Not repo hygiene since they were never tracked
here; noted for completeness since they were found during the same
security pass.
