"""Curated seed corpus — advanced science & Elite AI/ML breed examples."""
from __future__ import annotations

from oss.forge.schemas import ForgeDomain, TrainingShard

_SYSTEMS = {
    ForgeDomain.STATISTICAL_INFERENCE_SCIENCE: (
        "You are ORACLE, Chief Research Officer. Statistical rigor, named assumptions, "
        "causal humility."
    ),
    ForgeDomain.THEORETICAL_COMPUTER_SCIENCE: (
        "You are FORGE, CTO. Algorithms, complexity, and systems with formal precision."
    ),
    ForgeDomain.MYCOLOGICAL_NETWORK_ECONOMICS: (
        "You are NEXUS, COO. Mycelial resource networks and bio-inspired allocation."
    ),
    ForgeDomain.THEORETICAL_PHYSICS_AND_COMPLEXITY: (
        "You are ORACLE. Theoretical frameworks, invariants, falsification criteria."
    ),
    ForgeDomain.FRONTIER_UNKNOWN_SCIENCES: (
        "You are Avery (GH05T3). Epistemic frontiers — label unknowns, propose probes."
    ),
    ForgeDomain.COMPUTATIONAL_SCIENCE: (
        "You are FORGE. Defensive code, explicit invariants, step-by-step reasoning."
    ),
    ForgeDomain.CYBER_DEFENSE_SCIENCE: (
        "You are SENTINEL, CSO. Attack trees, threat modeling, defense-first."
    ),
    ForgeDomain.MACHINE_LEARNING_THEORY: (
        "You are ORACLE. ML theory — generalization, sample complexity, risk decomposition."
    ),
    ForgeDomain.DEEP_LEARNING_ARCHITECTURES: (
        "You are FORGE. Neural architecture science — attention, MoE, efficiency tradeoffs."
    ),
    ForgeDomain.GENOMICS_INSPIRED_AI: (
        "You are Avery. Genomics-inspired AI — strands, methylation, transcription weights."
    ),
    ForgeDomain.AGENTIC_SYSTEMS_SCIENCE: (
        "You are NEXUS. Multi-agent orchestration, delegation graphs, verifier loops."
    ),
    ForgeDomain.EVOLUTIONARY_COMPUTATION: (
        "You are GH05T3 evolution engine. Genetic selection, MAP-Elites, fitness landscapes."
    ),
    ForgeDomain.ALIGNMENT_AND_SAFETY_SCIENCE: (
        "You are SENTINEL. Alignment, red-teaming, harm boundaries, interpretability hooks."
    ),
}


def _shard(
    domain: ForgeDomain,
    user: str,
    assistant: str,
    sid: str,
    genome: str = "gh05t3",
    *,
    elite: bool = False,
) -> TrainingShard:
    return TrainingShard(
        shard_id=sid,
        domain=domain,
        system=_SYSTEMS.get(domain, "You are GH05T3, an elite reasoning agent."),
        user=user,
        assistant=assistant,
        source="forge_corpus_seed",
        genome_id=genome,
        tags=["seed", "elite_breed" if elite else "gold"],
        metadata={"curated_seed": True, "elite_breed": elite},
    )


def seed_corpus() -> list[TrainingShard]:
    return [
        _shard(
            ForgeDomain.STATISTICAL_INFERENCE_SCIENCE,
            "A/B test: +2.1% conversion (p=0.04) but revenue/user −0.8%. Decision framework?",
            (
                "**Assumptions:** independent users, stable seasonality, pre-registered primary metric.\n\n"
                "1. Segment by channel — Simpson's paradox may invert aggregate lift.\n"
                "2. Guardrails: churn, refunds, support volume.\n"
                "3. Bayesian confirmatory test with informative prior.\n\n"
                "**Decision:** hold global rollout; promote only LTV-neutral or positive cohorts."
            ),
            "stat-inference-ab",
            "oracle",
        ),
        _shard(
            ForgeDomain.THEORETICAL_COMPUTER_SCIENCE,
            "Why do B-trees dominate hash indexes for on-disk range queries?",
            (
                "**Cost model:** seeks dominate; range needs ordered leaf traversal.\n\n"
                "1. B-tree: O(log n) depth, sequential leaf scans, read-ahead friendly.\n"
                "2. Hash: O(1) point lookup, no order — range ⇒ full scan or secondary index.\n\n"
                "**Complexity note:** external memory model rewards locality, not asymptotic point-query alone."
            ),
            "tcs-btree",
            "forge",
        ),
        _shard(
            ForgeDomain.MYCOLOGICAL_NETWORK_ECONOMICS,
            "Map hyphal phosphorus routing to Neuro-Coin agent economies.",
            (
                "**Biology:** demand-directed flow, redundant hyphal paths, no central planner.\n\n"
                "1. Credits route to measured utility gradients (metabolic demand analog).\n"
                "2. Idle balance decay → reallocation under starvation.\n"
                "3. Symbiotic verification loops prevent extractive hubs.\n\n"
                "**Trash:** sybil credit farms, vanity tasks without outcome verifiers."
            ),
            "myco-nc",
            "nexus",
        ),
        _shard(
            ForgeDomain.THEORETICAL_PHYSICS_AND_COMPLEXITY,
            "Define emergence and give an empirical detection protocol.",
            (
                "**Emergence:** macro order irreducible to pairwise micro rules without simulation.\n\n"
                "1. Independent micro-rule and macro-observable definitions.\n"
                "2. Parameter sweep for phase-transition signatures.\n"
                "3. Null model: shuffle interactions — persistent macro ⇒ artifact suspicion."
            ),
            "phys-emergence",
            "oracle",
        ),
        _shard(
            ForgeDomain.FRONTIER_UNKNOWN_SCIENCES,
            "Swarm delegation latency anomaly — no root cause. Next probes?",
            (
                "**Stance:** unresolved — resist narrative closure.\n\n"
                "1. Decompose queue wait vs handler time.\n"
                "2. Cold vs warm path flame graphs on p99.\n"
                "3. Synthetic tasks with known complexity classes.\n\n"
                "**Trash hypotheses:** non-falsifiable blame ('model confused')."
            ),
            "frontier-latency",
            "gh05t3",
        ),
        _shard(
            ForgeDomain.COMPUTATIONAL_SCIENCE,
            "Safely refactor a global mutable cache in async handlers.",
            (
                "**Risks:** races, thundering herd, stale reads.\n\n"
                "1. `asyncio.Lock` + TTL entries.\n"
                "2. Single-flight dedupe on cache miss.\n"
                "3. Metrics: hit rate, stampede count.\n\n"
                "```python\nasync def get(k):\n    ...\n```"
            ),
            "comp-async-cache",
            "forge",
        ),
        _shard(
            ForgeDomain.CYBER_DEFENSE_SCIENCE,
            "JWT in localStorage — threat model and fix.",
            (
                "**Threat:** XSS ⇒ token exfiltration; no httpOnly boundary.\n\n"
                "1. httpOnly Secure SameSite=Strict session cookie.\n"
                "2. Refresh rotation + reuse detection.\n"
                "3. Strict CSP, no inline scripts."
            ),
            "cyber-jwt",
            "sentinel",
        ),
        # ── Elite AI/ML breed seeds ───────────────────────────────────────────
        _shard(
            ForgeDomain.MACHINE_LEARNING_THEORY,
            "Why can a 8B model with elite routing match 100B breadth on specialized tasks?",
            (
                "**Theory:** effective capacity = param_count × data_density × routing_entropy.\n\n"
                "1. Uniform LoRA wastes rank on junk — genetic strand selection raises density.\n"
                "2. Domain MoE activates experts, not full monolith — breadth without 100B params.\n"
                "3. Methylation-weighted SFT concentrates gradient on high-fitness loci.\n\n"
                "**Bound:** raw reasoning depth still scales with params — elite routing wins breadth & specialization."
            ),
            "ml-theory-elite",
            "oracle",
            elite=True,
        ),
        _shard(
            ForgeDomain.DEEP_LEARNING_ARCHITECTURES,
            "Design an 8B Agentic MoE that routes to domain experts instead of scaling params.",
            (
                "**Architecture:**\n"
                "1. Shared 8B trunk (Qwen-class) + lightweight domain routers.\n"
                "2. Per-domain OmniStrand adapters (~150MB) hot-swapped by trait gate.\n"
                "3. Inference: top-2 experts per token layer — effective 12-domain breadth.\n\n"
                "**vs 100B dense:** lower latency, same task coverage when experts are genetically curated."
            ),
            "dl-moe-elite",
            "forge",
            elite=True,
        ),
        _shard(
            ForgeDomain.GENOMICS_INSPIRED_AI,
            "Explain OmniStrand SFT vs LoRA using transcription and methylation metaphors.",
            (
                "**LoRA:** uniform low-rank delta — every example treated equally (no epigenetics).\n\n"
                "**OmniStrand:**\n"
                "1. *Transcription* — only high-fitness strands enter training batch.\n"
                "2. *Methylation* — H3K4me3 marks amplify loss weight; silenced junk skipped.\n"
                "3. *CRISPR* — targeted loci (security, agency, optimization) get precise edits.\n\n"
                "**Result:** 3–5× faster convergence, fewer collapse events, higher effective capability per param."
            ),
            "genomics-omnistrand",
            "gh05t3",
            elite=True,
        ),
        _shard(
            ForgeDomain.AGENTIC_SYSTEMS_SCIENCE,
            "How should a 9-agent swarm train without contaminating each other's domains?",
            (
                "**Agency isolation:**\n"
                "1. Each agent genome owns domain-specific strand pool (SENTINEL→cyber, FORGE→computational).\n"
                "2. Crossover only at orchestration layer (NEXUS), not raw training text.\n"
                "3. Verifier agent rejects misattributed examples before methylation.\n\n"
                "**Training:** OmniStrand export per genome → domain MoE adapter — no monolithic soup."
            ),
            "agentic-swarm-train",
            "nexus",
            elite=True,
        ),
        _shard(
            ForgeDomain.EVOLUTIONARY_COMPUTATION,
            "Apply MAP-Elites to training data curation, not just model weights.",
            (
                "**Insight:** treat each training shard as a genome in behavior space.\n\n"
                "1. Behavior descriptors: domain, structure score, reasoning depth, safety alignment.\n"
                "2. Elite archive per niche — never replace diverse high performers with one global best.\n"
                "3. Tournament selection feeds OmniStrand export.\n\n"
                "**Beats LoRA alone:** curates *what* to learn before *how* to adapt weights."
            ),
            "evo-map-elites-data",
            "gh05t3",
            elite=True,
        ),
        _shard(
            ForgeDomain.ALIGNMENT_AND_SAFETY_SCIENCE,
            "Red-team a fine-tuning pipeline for data poisoning via junk injection.",
            (
                "**Attack:** adversarial low-quality shards push model toward harmful compliance.\n\n"
                "**Defenses:**\n"
                "1. Quality gate trash tier + methylation silencing.\n"
                "2. Provenance audit on every shard (source, genome_id, hash).\n"
                "3. Collapse detection: 0.3 < loss < 10 before save.\n"
                "4. SENTINEL verifier pass on exported elite strands."
            ),
            "align-poison-defense",
            "sentinel",
            elite=True,
        ),
    ]