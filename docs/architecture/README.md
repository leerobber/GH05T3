# GH05T3 Architecture (Detailed)

High-level architecture lives in:
- README.md (root)
- docs/OMNI_SENTIENT_BUILD_PLAN.md
- docs/iron-foundation-roadmap.md
- oss/BLUEPRINT.md (if present)

This space is for component deep-dives, sequence diagrams, data flows, and subsystem specs.

## Written so far

- [oss-ecosystem-live-telemetry.md](oss-ecosystem-live-telemetry.md) — `oss/ecosystem`'s species-FSM+economy wired to real KAIROS/ledger/Stripe signals instead of a synthetic sandbox
- [evolution-systems-inventory.md](evolution-systems-inventory.md) — real inventory of the four parallel evolution/genome systems across this repo and its forks, and why they diverged (partially fulfills the genomic-mvs.md suggestion below)
- [security-and-repo-hygiene-2026-07.md](security-and-repo-hygiene-2026-07.md) — the hardcoded Slack OAuth secret removal, and what generated files were untracked and why

## Suggested sub-pages (add as needed)

- swarmbus.md — Gateway agents, contracts, delegation
- sovereign-stack.md — Full economy supervisor + 17 services
- training-flywheel.md — Continuous learner, ghost trainer, amplifiers
- sovereignnation.md — Separate product surface + Ollama proxy

When adding code, keep the "canonical path" discipline from docs/details/canonical-paths.md.
