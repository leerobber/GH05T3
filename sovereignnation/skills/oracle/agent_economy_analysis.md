Interpreting SovereignNation agent economy simulation data — metrics, trends, and behavioral signals.

## When to apply
When analyzing agent economy tick data, transaction logs, generation stats, or evolution metrics.

## Key metrics and what they mean
- **awareness_score**: Agent's accumulated knowledge depth (0–1). High awareness = better task selection.
- **morale**: Drives task acceptance rate. Below 60 → agent underperforms. Above 90 → possible overcommitment.
- **tasks_completed**: Primary fitness signal. Low completion vs. high awareness = skill-task mismatch.
- **skill_mastery JSON**: Contains `_kb_boost` (knowledge feedback bonus) — a proxy for how much ChromaDB KB content has been absorbed.
- **generation**: Gen 0 = founding agents. Higher gen = survived Darwinian selection. Gen 10+ = elite lineage.

## Transaction pattern signals
- High transaction volume, low morale: agents are overloaded or price-taking at loss
- Low transaction volume, high awareness: agents are selective (hoarding) — may indicate market thinness
- Gini coefficient rising: wealth concentration forming — check if elite agents are monopolizing skill niches
- Sudden morale collapse across a generation: external shock in tick data (check tick events)

## Evolution health indicators
- Retirement rate > 15% per 100 ticks → selection pressure high (competitive economy)
- Retirement rate < 3% → selection too loose, low evolutionary pressure
- Cross-generation skill propagation: are Gen10+ agents carrying the same skills as Gen0? If yes, diversity is low.

## Causal inference approach
Do not confuse correlation with causation in economy data.
Use the ATE (Average Treatment Effect) framework:
  1. Identify the intervention (e.g., knowledge_feedback boost at tick X)
  2. Compare agent outcomes before and after with same skill pool
  3. Control for generation and base morale level
