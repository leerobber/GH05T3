"""Scientific domain catalog — research titles, search tags, elite AI/ML disciplines."""
from __future__ import annotations

from dataclasses import dataclass

from oss.forge.schemas import ForgeDomain


@dataclass(frozen=True)
class DomainSpec:
    key: ForgeDomain
    title: str
    discipline: str
    search_tags: tuple[str, ...]
    keywords: tuple[str, ...]


DOMAIN_CATALOG: tuple[DomainSpec, ...] = (
    # ── Foundational sciences ─────────────────────────────────────────────
    DomainSpec(
        ForgeDomain.CYBER_DEFENSE_SCIENCE,
        "Cyber-Defense Science",
        "Information Security",
        ("cybersecurity", "threat modeling", "zero trust", "cryptography"),
        ("cve", "exploit", "mitigation", "threat", "vulnerability", "owasp", "defense"),
    ),
    DomainSpec(
        ForgeDomain.COMPUTATIONAL_SCIENCE,
        "Computational Science",
        "Software & Algorithms",
        ("software engineering", "algorithms", "systems programming"),
        ("function", "algorithm", "refactor", "debug", "api", "python", "invariant"),
    ),
    DomainSpec(
        ForgeDomain.EPISTEMOLOGY_AND_DISCOVERY,
        "Epistemology & Discovery Science",
        "Research Methodology",
        ("scientific method", "literature review", "hypothesis testing"),
        ("hypothesis", "methodology", "literature", "synthesis", "evidence", "falsify"),
    ),
    DomainSpec(
        ForgeDomain.SYSTEMS_ENGINEERING,
        "Systems Engineering",
        "Operations & Reliability",
        ("SRE", "distributed systems", "incident response"),
        ("deploy", "incident", "runbook", "sla", "capacity", "rollback", "failure mode"),
    ),
    DomainSpec(
        ForgeDomain.STATISTICAL_INFERENCE_SCIENCE,
        "Statistical Inference Science",
        "Data Science",
        ("bayesian inference", "causal inference", "experiment design"),
        ("feature", "bias", "variance", "regression", "cluster", "p-value", "cohort"),
    ),
    DomainSpec(
        ForgeDomain.THEORETICAL_COMPUTER_SCIENCE,
        "Theoretical Computer Science",
        "Computability & Complexity",
        ("complexity theory", "formal methods", "type theory"),
        ("complexity", "compiler", "distributed", "cache", "protocol", "graph", "np"),
    ),
    DomainSpec(
        ForgeDomain.MYCOLOGICAL_NETWORK_ECONOMICS,
        "Mycological Network Economics",
        "Bio-Inspired Resource Allocation",
        ("mycelium networks", "decentralized economics", "stigmergy"),
        ("mycelium", "hyphal", "symbiosis", "allocation", "network", "nutrient", "exchange"),
    ),
    DomainSpec(
        ForgeDomain.THEORETICAL_PHYSICS_AND_COMPLEXITY,
        "Theoretical Physics & Complexity Science",
        "Physics & Emergence",
        ("statistical mechanics", "complex systems", "phase transitions"),
        ("theorem", "entropy", "field", "symmetry", "quantum", "emergence", "invariant"),
    ),
    DomainSpec(
        ForgeDomain.FRONTIER_UNKNOWN_SCIENCES,
        "Frontier & Unknown Sciences",
        "Epistemic Frontiers",
        ("anomaly detection", "unknown unknowns", "exploration"),
        ("uncertainty", "frontier", "unknown", "explore", "epistemic", "anomaly", "probe"),
    ),
    DomainSpec(
        ForgeDomain.GENERAL_COGNITION,
        "General Cognition Science",
        "Cross-Domain Reasoning",
        ("reasoning", "planning", "metacognition"),
        ("reason", "analyze", "step", "conclude", "evaluate"),
    ),
    # ── Elite AI/ML research (new breed) ────────────────────────────────────
    DomainSpec(
        ForgeDomain.MACHINE_LEARNING_THEORY,
        "Machine Learning Theory",
        "AI/ML Foundations",
        ("PAC learning", "generalization bounds", "VC dimension", "sample complexity"),
        ("generalization", "overfitting", "regularization", "pac", "bias-variance", "risk"),
    ),
    DomainSpec(
        ForgeDomain.DEEP_LEARNING_ARCHITECTURES,
        "Deep Learning Architecture Science",
        "Neural Architectures",
        ("transformers", "attention", "mixture of experts", "state space models"),
        ("transformer", "attention", "moe", "layer", "activation", "residual", "embedding"),
    ),
    DomainSpec(
        ForgeDomain.NEURAL_SYMBOLIC_INTEGRATION,
        "Neural-Symbolic Integration Science",
        "Hybrid AI",
        ("neuro-symbolic", "logic tensors", "differentiable reasoning"),
        ("symbolic", "logic", "predicate", "differentiable", "reasoning", "proof"),
    ),
    DomainSpec(
        ForgeDomain.EVOLUTIONARY_COMPUTATION,
        "Evolutionary Computation Science",
        "Genetic Algorithms & MAP-Elites",
        ("genetic algorithms", "neuroevolution", "quality diversity"),
        ("mutation", "crossover", "fitness", "selection", "genome", "elite", "diversity"),
    ),
    DomainSpec(
        ForgeDomain.GENOMICS_INSPIRED_AI,
        "Genomics-Inspired AI Science",
        "Biological Training Metaphors",
        ("epigenetics", "transcription", "CRISPR editing", "strand architecture"),
        ("methylation", "transcription", "crispr", "strand", "allele", "phenotype", "genotype"),
    ),
    DomainSpec(
        ForgeDomain.COGNITIVE_NEUROSCIENCE,
        "Cognitive Neuroscience",
        "Brain-Inspired Cognition",
        ("working memory", "attention neuroscience", "predictive coding"),
        ("cortex", "memory", "attention", "prediction", "neuron", "cognitive"),
    ),
    DomainSpec(
        ForgeDomain.QUANTUM_MACHINE_LEARNING,
        "Quantum Machine Learning Science",
        "Quantum-Classical Hybrid ML",
        ("quantum circuits", "variational quantum eigensolver", "QML"),
        ("qubit", "quantum", "superposition", "entanglement", "variational", "hamiltonian"),
    ),
    DomainSpec(
        ForgeDomain.ALIGNMENT_AND_SAFETY_SCIENCE,
        "Alignment & Safety Science",
        "AI Safety",
        ("RLHF", "constitutional AI", "interpretability", "red teaming"),
        ("alignment", "safety", "jailbreak", "reward", "harm", "guardrail", "interpret"),
    ),
    DomainSpec(
        ForgeDomain.MULTIMODAL_REPRESENTATION_LEARNING,
        "Multimodal Representation Learning",
        "Vision-Language-Audio Fusion",
        ("contrastive learning", "CLIP", "cross-modal alignment"),
        ("multimodal", "vision", "audio", "embedding", "contrastive", "alignment"),
    ),
    DomainSpec(
        ForgeDomain.AGENTIC_SYSTEMS_SCIENCE,
        "Agentic Systems Science",
        "Multi-Agent Orchestration",
        ("swarm intelligence", "tool use", "planning agents", "delegation"),
        ("agent", "swarm", "delegate", "tool", "plan", "orchestrat", "multi-agent"),
    ),
)

_CATALOG_BY_KEY = {spec.key: spec for spec in DOMAIN_CATALOG}
_KEYWORDS: dict[ForgeDomain, tuple[str, ...]] = {
    spec.key: spec.keywords for spec in DOMAIN_CATALOG
}

# Legacy slug → scientific domain (backward compatible ingest)
LEGACY_ALIASES: dict[str, ForgeDomain] = {
    "security": ForgeDomain.CYBER_DEFENSE_SCIENCE,
    "code": ForgeDomain.COMPUTATIONAL_SCIENCE,
    "research": ForgeDomain.EPISTEMOLOGY_AND_DISCOVERY,
    "ops": ForgeDomain.SYSTEMS_ENGINEERING,
    "data_science": ForgeDomain.STATISTICAL_INFERENCE_SCIENCE,
    "computer_science": ForgeDomain.THEORETICAL_COMPUTER_SCIENCE,
    "fungi_economics": ForgeDomain.MYCOLOGICAL_NETWORK_ECONOMICS,
    "theoretical_science": ForgeDomain.THEORETICAL_PHYSICS_AND_COMPLEXITY,
    "unknown": ForgeDomain.FRONTIER_UNKNOWN_SCIENCES,
    "default": ForgeDomain.GENERAL_COGNITION,
    # pipeline file stems
    "adversarial_defense": ForgeDomain.CYBER_DEFENSE_SCIENCE,
    "cve_patterns": ForgeDomain.CYBER_DEFENSE_SCIENCE,
    "bug_bounty": ForgeDomain.CYBER_DEFENSE_SCIENCE,
    "reasoning_chains": ForgeDomain.EPISTEMOLOGY_AND_DISCOVERY,
    "sovereign_recall": ForgeDomain.EPISTEMOLOGY_AND_DISCOVERY,
}


def resolve_domain(value: str) -> ForgeDomain:
    """Resolve scientific or legacy slug to ForgeDomain."""
    v = (value or "").lower().strip()
    try:
        return ForgeDomain(v)
    except ValueError:
        return LEGACY_ALIASES.get(v, ForgeDomain.GENERAL_COGNITION)


def domain_keywords(domain: ForgeDomain) -> tuple[str, ...]:
    return _KEYWORDS.get(domain, ())


def list_domains() -> list[dict]:
    return [
        {
            "key": spec.key.value,
            "title": spec.title,
            "discipline": spec.discipline,
            "search_tags": list(spec.search_tags),
            "elite_tier": spec.key.value in _ELITE_DOMAINS,
        }
        for spec in DOMAIN_CATALOG
    ]


def search_domains(query: str) -> list[dict]:
    q = query.lower().strip()
    if not q:
        return list_domains()
    hits = []
    for spec in DOMAIN_CATALOG:
        blob = " ".join([spec.title, spec.discipline, *spec.search_tags, *spec.keywords]).lower()
        if q in blob or any(q in tag for tag in spec.search_tags):
            hits.append(spec)
    return [
        {"key": s.key.value, "title": s.title, "discipline": s.discipline}
        for s in hits
    ]


_ELITE_DOMAINS = {
    ForgeDomain.MACHINE_LEARNING_THEORY,
    ForgeDomain.DEEP_LEARNING_ARCHITECTURES,
    ForgeDomain.NEURAL_SYMBOLIC_INTEGRATION,
    ForgeDomain.EVOLUTIONARY_COMPUTATION,
    ForgeDomain.GENOMICS_INSPIRED_AI,
    ForgeDomain.COGNITIVE_NEUROSCIENCE,
    ForgeDomain.QUANTUM_MACHINE_LEARNING,
    ForgeDomain.ALIGNMENT_AND_SAFETY_SCIENCE,
    ForgeDomain.MULTIMODAL_REPRESENTATION_LEARNING,
    ForgeDomain.AGENTIC_SYSTEMS_SCIENCE,
}