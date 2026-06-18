"""Curated systems · code · data intelligence anchors — beyond forge seeds."""
from __future__ import annotations

from oss.forge.corpus import _shard
from oss.forge.omni_lex import shard_to_chatml as _chatml
from oss.forge.schemas import ForgeDomain

# Re-use shard helper from corpus pattern
def _s(domain, user, assistant, sid, genome="gh05t3", weight: int = 5):
    sh = _shard(domain, user, assistant, sid, genome, elite=True)
    return (_chatml(sh), weight)


def intelligence_anchors() -> list[tuple[str, int]]:
    """High-signal ChatML examples weighted for systems/code/data reasoning."""
    return [
        _s(
            ForgeDomain.SYSTEMS_ENGINEERING,
            "Design a fault-tolerant event bus for 9 agents with backpressure.",
            (
                "**System model:** producers (agents), bounded queues, consumer groups, dead-letter topic.\n\n"
                "1. *Backpressure:* per-agent credit tokens — publish blocked when queue > 80%.\n"
                "2. *Idempotency:* message_id + dedupe window prevents double-processing.\n"
                "3. *Failure domains:* broker partition per criticality tier.\n"
                "4. *Observability:* lag, retry count, DLQ rate as SLO burn alerts.\n\n"
                "**Data contract:** schema registry with compatibility checks before deploy."
            ),
            "intel-event-bus",
            "nexus",
            6,
        ),
        _s(
            ForgeDomain.COMPUTATIONAL_SCIENCE,
            "Refactor a 2k-line monolith into modules without breaking production.",
            (
                "**Strategy:** strangler fig — never big-bang.\n\n"
                "1. Map bounded contexts from call-graph + data ownership.\n"
                "2. Extract highest-churn module first behind stable interface.\n"
                "3. Characterization tests lock behavior before moves.\n"
                "4. Feature flags route traffic incrementally.\n\n"
                "```python\n# seam: inject repository, not global state\nclass OrderService:\n    def __init__(self, repo: OrderRepo): ...\n```"
            ),
            "intel-refactor",
            "forge",
            6,
        ),
        _s(
            ForgeDomain.STATISTICAL_INFERENCE_SCIENCE,
            "Pipeline shows 99% accuracy but production fails — diagnose data leakage.",
            (
                "**Hypothesis:** train/serve skew or temporal leakage.\n\n"
                "1. Audit feature timestamps vs label cutoff.\n"
                "2. Check duplicate entities across train/test splits.\n"
                "3. Compare offline metric vs live calibration curve.\n"
                "4. Shadow deploy with null model baseline.\n\n"
                "**Data rule:** split by entity_id + time, never random row shuffle for user data."
            ),
            "intel-leakage",
            "oracle",
            5,
        ),
        _s(
            ForgeDomain.AGENTIC_SYSTEMS_SCIENCE,
            "How should GH05T3 agents share memory without cross-contaminating domains?",
            (
                "**Architecture:** federated memory cortex with genome-scoped namespaces.\n\n"
                "1. ORACLE owns retrieval index; writes require genome_id tag.\n"
                "2. Cross-agent reads go through trait gate — FORGE cannot pull raw SENTINEL exploit PoCs.\n"
                "3. Episodic summaries promoted to shared tier only after verifier pass.\n"
                "4. TTL + methylation decay on stale shards.\n\n"
                "**Anti-pattern:** one global embedding soup — destroys specialization."
            ),
            "intel-agent-memory",
            "gh05t3",
            6,
        ),
        _s(
            ForgeDomain.DEEP_LEARNING_ARCHITECTURES,
            "When should we train adapters vs full fine-tune for agent specialization?",
            (
                "**Decision matrix:**\n"
                "| Signal | LoRA adapter | Full SFT |\n"
                "| Domain shift small | ✓ | |\n"
                "| New tool schema | ✓ | |\n"
                "| Reasoning style overhaul | | ✓ |\n\n"
                "**GH05T3 default:** OmniStrand LoRA per domain + shared 3B trunk — "
                "genetic curation raises effective capability without 100B params."
            ),
            "intel-adapter-vs-sft",
            "oracle",
            5,
        ),
        _s(
            ForgeDomain.THEORETICAL_COMPUTER_SCIENCE,
            "Prove why naive async fan-out can increase p99 latency under load.",
            (
                "**Model:** N concurrent tasks, shared thread pool size T, each task duration D.\n\n"
                "1. When N >> T, queue wait grows Ω((N-T)·D/T) — fan-out amplifies tail.\n"
                "2. Retry storms multiply effective N.\n"
                "3. Fix: bulkhead pools, adaptive concurrency limits, circuit breakers.\n\n"
                "**Code invariant:** measure queue depth, not just handler CPU."
            ),
            "intel-async-p99",
            "forge",
            5,
        ),
        _s(
            ForgeDomain.EPISTEMOLOGY_AND_DISCOVERY,
            "You have conflicting metrics from three data sources. Resolution protocol?",
            (
                "**Epistemic stance:** treat conflict as signal, not noise to average away.\n\n"
                "1. Document provenance + collection methodology per source.\n"
                "2. Identify overlapping vs orthogonal measurements.\n"
                "3. Run sensitivity analysis — which decisions flip under each source?\n"
                "4. Prefer actionable conservative bound until reconciled.\n\n"
                "**Never:** pick the number that confirms the desired narrative."
            ),
            "intel-conflict-data",
            "oracle",
            5,
        ),
        _s(
            ForgeDomain.NEURAL_SYMBOLIC_INTEGRATION,
            "Combine LLM codegen with symbolic verifiers for payment logic.",
            (
                "**Hybrid loop:**\n"
                "1. LLM drafts handler + invariants as comments.\n"
                "2. Symbolic checker: amount > 0, currency match, idempotency key present.\n"
                "3. Property test generates edge cases (zero, overflow, duplicate).\n"
                "4. Failed verify → structured feedback into next LLM turn.\n\n"
                "**Data:** store verifier failures as gold-negative training shards."
            ),
            "intel-neuro-symbolic",
            "forge",
            5,
        ),
        _s(
            ForgeDomain.GENERAL_COGNITION,
            "Teach step-by-step systems thinking for any new GH05T3 feature.",
            (
                "**FRAMEWORK (always apply):**\n"
                "F — *Forces:* users, agents, data flows, failure modes\n"
                "R — *Resources:* compute, money, attention, latency budget\n"
                "A — *Architecture:* components, contracts, trust boundaries\n"
                "M — *Metrics:* leading + lagging, falsifiable success criteria\n"
                "E — *Evolution:* how it learns, degrades, and gets better\n\n"
                "**Output rule:** lead with diagram or table, then implementation."
            ),
            "intel-frame-systems",
            "gh05t3",
            7,
        ),
        _s(
            ForgeDomain.MULTIMODAL_REPRESENTATION_LEARNING,
            "How do embeddings + structured metadata interact in a memory cortex?",
            (
                "**Dual index:**\n"
                "1. Vector similarity for fuzzy recall (semantic neighborhood).\n"
                "2. Structured filters: genome_id, domain, quality_tier, timestamp.\n"
                "3. Fusion score = α·cosine + β·tier_weight + γ·recency.\n"
                "4. Re-rank top-k with cross-encoder verifier.\n\n"
                "**Data hygiene:** trash-tier vectors never enter hot index."
            ),
            "intel-embed-meta",
            "oracle",
            4,
        ),
    ]