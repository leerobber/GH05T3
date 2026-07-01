# Details — Internal Project Documentation

This directory holds **detailed, long-form, or audit-oriented documentation** that would clutter top-level docs or READMEs.

## Contents

- `canonical-paths.md` — Authoritative mapping of roles → files/paths/ports/launchers. Source of truth for "where does X live?"
- Future: decision records (ADRs), deep architecture notes, full audit logs, data models, etc.

## Guidelines

- Prefer short overviews in `README.md`, `RUN_ORDER.md`, or `OMNI_SENTIENT_BUILD_PLAN.md`.
- Move or link detailed analysis here.
- Keep canonical references up to date when refactoring trees (backend/oss/, scripts/, sovereignnation/, etc.).
- "One canonical path per concern" — document the decision + removal here.

See parent `docs/` for phased build plans and roadmaps.
