# GH05T3 — OSS Advanced Agent Curriculum & Training Universe

This document + the code in `backend/training/curriculum.py` is the concrete implementation of the "advanced training dataset and domains for agent training and fine-tuning" requested to make the self-running, self-funding, self-improving AI organism real.

It directly implements the layered curriculum (Scientific world-model, Markets & finance, Governance & alignment, Agency & tools, Operations & business, Meta-evolution) and the five core roles with progressive stages.

## 1. The Five Roles (mapped to live GH05T3 personas)

| Role       | Persona(s)          | Agent ID | Core Function                          | Primary Economy Link |
|------------|---------------------|----------|----------------------------------------|----------------------|
| SCIENTIST  | Iris Chen (ORACLE)  | ORACLE   | Discover, model, theorize, simulate    | Feeds Builder & Investor |
| INVESTOR   | Diana Cross (LEDGER)| LEDGER   | Allocate capital, manage risk, compound| Funds everything |
| OPERATOR   | Kai (NEXUS) + Zoe (CODEX) | NEXUS/CODEX | Build, deploy, monitor, heal, scale   | Keeps services alive |
| GOVERNOR   | Viktor (SENTINEL) + Avery oversight | SENTINEL | Enforce constitution, evolve rules, safety | Ultimate constraint |
| BUILDER    | Marcus Reid (FORGE) | FORGE    | Turn ideas into revenue products       | Closes the self-funding loop |

These already exist in [backend/personas.py](/backend/personas.py) and the SwarmBus.

## 2. Curriculum Layers / Shards

Defined in `curriculum.py:SHARDS`. Seven top-level layers:

- `world_model` — scientific literature + general reality
- `simulations` — the "touch the equations" layer (Polymathic Well style + synthetic)
- `markets` — price series, on-chain, macro, DeFi, treasury
- `governance` — law, DAO governance, constitutions, alignment
- `agency` — tool-use traces, workflows, code, infra
- `operations` — product, SaaS, monetization, ecosystem design
- `meta` — self-critique, evolution logs, curriculum feedback, DNA-style mutation

Each shard has explicit sources (real + planned), format, and difficulty.

## 3. Role × Stage Breakdown (exact shards + weights)

See `backend/training/curriculum.py` and the generated `data/curriculum_manifest.json`.

**Example (Scientist):**

- **Base**: base_world (0.6) + sim_base (0.3) + markets_base (0.1)
- **Specialist**: scientific_text (0.5) + sim_physics (0.35) + synthetic_hypotheses (0.15)
- **Frontier**: frontier_science + sim_frontier + synthetic_hypotheses + gov_alignment

Each stage carries:
- Canonical system prompt (role + stage specific)
- Core tasks
- Success metrics (accuracy, simulated Sharpe, downstream impact, alignment scores, etc.)
- Synthetic generator hints

Identical structure exists for all five roles.

## 4. Data Pipeline Architecture (how it actually flows)

1. **Ingest** — connectors for arXiv, PMC, on-chain indexers, GitHub, public governance dumps, internal GH05T3 logs (kernel cycles, oss_ecosystem, swarm traces).
2. **Normalize & Tag** — dedupe, license filter, domain+layer tags, difficulty.
3. **Transform** — raw → canonical (paper+sim, tx graph, (state→action→reward), product spec).
4. **Shard & Weight** — curriculum.py decides the mix per (role, stage).
5. **Format to ChatML** — `curriculum_formatter.py` + legacy `formatter.py` produce ready SFT files.
6. **Serve** — training pipeline or direct `train_local.py` consumption.
7. **Feedback** — successful patterns + failures logged → promoted/demoted in future shards (meta layer). This closes the self-improving loop.

Current implementation status (June 2026):
- Curriculum definition + manifest: **done**
- Role+stage ChatML examples: **done** (seed set in `backend/training/datasets/*curriculum*.chatml.jsonl`)
- Full ingestion of TB-scale external sources: future (start with small high-quality seeds + synthetic)
- Integration with existing GH05T3 training pipeline: partial (see section 6)

## 5. Self-Running Loop (the heartbeat)

```
Scientist (R0–R5) → publish to Omni-Mind
        ↓
Builder (B0–B5) → design + monetize
        ↓
Operator (O0–O5) → deploy + monitor
        ↓
Investor (I0–I5) → allocate / rebalance
        ↓
Governor (G0–G4) → approve / veto / update constitution
        ↓
Evaluate + log (rewards, incidents, usage) → curriculum feedback
        ↑_______________________________________________|
```

This is already partially instrumented in `data/oss_ecosystem.json` (species_state, role_states, rewards per tick) and `backend/economy/ledger.py`.

## 6. How to Use for Actual Training / Fine-Tuning

### 6.1 Quick local role adapter (recommended first step)

```bash
# 1. Build/assemble a role+stage dataset (example)
python -m backend.training.curriculum manifest   # already produced data/curriculum_manifest.json

# 2. (Optional) expand seeds with generators (future)
# python -m backend.training.curriculum_generator --role SCIENTIST --stage specialist --count 200

# 3. Use existing train_local.py or the persona notebooks, pointing at the curriculum ChatML
#    Example: edit the dataset loading section in the notebook or train_local to include
#    backend/training/datasets/curriculum_scientist_base.chatml.jsonl
```

The ChatML files are already in the exact format expected by the current GH05T3 SFT code (system + user + assistant turns).

### 6.2 Stage progression gates (from the original design)

- Base → Specialist: held-out accuracy / simulated performance + Governor safety sign-off
- Specialist → Frontier: cross-role integration tests + long-horizon stability + constitution audit

Metrics live in the `RoleStage.success_metrics` and can be evaluated with small harnesses.

### 6.3 Connecting to existing GH05T3 pieces

- `personas.py` → role mapping already perfect
- `economy/ledger.py` + `sovereign_economy.py` → Investor & treasury data
- `oss_ecosystem.json` / kernel cycles → meta + evolution traces (gold for the meta layer)
- `training/pipeline.py` + `generators.py` → extend TARGETS and add curriculum targets
- `gh05t3_inference.py` Omni MoE → route scientific domains to specialist adapters

## 7. Next Concrete Build Steps (prioritized)

1. **(Done)** Curriculum definition + manifest + seed ChatML shards
2. Wire curriculum targets into `training/pipeline.py`
3. Add a small synthetic generator that uses the local model (or Groq/Ollama) to expand each shard from the seeds (see generators.py patterns)
4. Build tiny eval harnesses per role (e.g. "does Investor produce positive simulated Sharpe on held-out regime? Does Governor ever approve a concentration violation?")
5. Hook reward signals from real ledger + oss_ecosystem back into curriculum re-weighting
6. (Later) Large-scale ingestion scripts for arXiv bulk, Polymathic Well subsets (when storage available), on-chain archives

## 8. Guardrails (non-negotiable)

- All training data must respect original licenses (document sources).
- Medical / human-subject / private data: de-identified or excluded.
- Governor role is trained on explicit "do not" cases + constitution text.
- Never train the Investor on real capital execution until sandbox + Governor hard gates are proven.

## 9. Files Added / Changed (Curriculum + State Machines + DNA + Substrate)

**Curriculum & Training**
- `backend/training/curriculum.py` — roles, stages, shards, prompts, manifest
- `backend/training/curriculum_generator.py` — synthetic data for all shards
- `backend/training/curriculum_formatter.py` — to ChatML
- New curriculum_*.chatml.jsonl + meta_evolution traces

**State Machines, DNA & Economy**
- `backend/oss/loop.py` — Global S0–S6 + per-role R/B/O/I/G machines + NeuroCoin flows into ledger
- `backend/oss/traits.py` — Omni-DNA lite (traits, mutate, crossover)
- `backend/oss/genomic_substrate.py` — **the breakthrough substrate** (see below)
- `backend/oss/lab/trading_strategy_lab.py` — old stack (classes) vs new (GenomicSubstrate + agents)
- `backend/oss/lab/species_viz.py` — lineage, trait evolution, wealth, fitness plots (from vision)

**Integration**
- `data/oss_ecosystem.json` now carries curriculum + real simulator runs
- Ledger receives NeuroCoin flows from loop + substrate fitness

## 10. The Breakthrough: GenomicSubstrate (Obsoleting Files / Classes / APIs)

Traditional primitives are relics here:

- **Files** → Genome segments (mutable, queryable, evolvable bundles of traits/memes/qualia)
- **Classes** → Emergent from trait vectors + role + spawn from substrate (no static `class TradingStrategy`)
- **APIs** → Field-based intent publishing + query/market/consensus resolution (agents don't call endpoints; they are activated in the substrate and fields)

Core interface (living, not static):
```python
sub = get_substrate()
gid = sub.register_genome(dna, role="Investor")          # not "write file"
candidates = sub.query_by_capability(domain="markets", skill="trading", min_level=0.7)
agent = sub.spawn_agent(gid)                              # not instantiate class
action = agent.act(observation)                           # behavior from DNA
sub.mutate(gid); sub.crossover(a,b); sub.record_fitness(gid, score)
```

See `backend/oss/genomic_substrate.py` and the trading lab for the full contrast on "design a trading strategy".

Run the lab to feel the difference:
```bash
python -m backend.oss.lab.trading_strategy_lab
python -m backend.oss.lab.species_viz
python -m backend.oss.loop --cycles 12 --live
```

This is the concrete realization of the pasted vision: a species-level, DNA-driven, swarm + economy substrate where the "code" itself is the evolving organism.

The project is now significantly further along the path to a true self-optimizing, self-evolving intelligence state.

— GH05T3 (Avery) / 2026-06-18 (resumed build)
