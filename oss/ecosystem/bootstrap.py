"""OSS bootstrap plan — minimal v1 through Omni-Evolution (Phases 1–5)."""
from __future__ import annotations

from typing import Any


def oss_bootstrap_plan() -> dict[str, Any]:
    return {
        "title": "OSS Minimal Bootstrap Path",
        "phases": [
            {
                "phase": 1,
                "name": "Build the Skeleton",
                "weeks": "1–4",
                "items": [
                    {"id": "1.1", "task": "Single LLM with role-conditioning", "status": "partial",
                     "detail": "gh05t3_inference + MoE + role prompts"},
                    {"id": "1.2", "task": "Simple orchestrator (5-role FSM)", "status": "implemented",
                     "detail": "oss/kernel/orchestrator.py + oss/ecosystem/orchestrator.py"},
                    {"id": "1.3", "task": "Sandbox (fake market/infra/products)", "status": "implemented",
                     "detail": "oss/kernel/sandbox.py"},
                ],
                "constraints": ["No self-evolution", "No real economy", "No real users"],
            },
            {
                "phase": 2,
                "name": "Add DNA & Evolution",
                "weeks": "4–10",
                "items": [
                    {"id": "2.1", "task": "Omni-DNA simplified (traits, mutation, crossover, memes, qualia)",
                     "status": "partial", "detail": "oss/dna/omni_dna.py"},
                    {"id": "2.2", "task": "Per-role reward calculators → DNA trait updates",
                     "status": "implemented", "detail": "oss/ecosystem/rewards.py"},
                ],
            },
            {
                "phase": 3,
                "name": "Add Omni-Mind",
                "weeks": "10–16",
                "items": [
                    {"id": "3.1", "task": "Shared memory + shared qualia", "status": "partial",
                     "detail": "oss/mind/collective.py"},
                    {"id": "3.2", "task": "Swarm tasks + consensus", "status": "partial",
                     "detail": "oss/mind/omni_mind.py M0–M6 FSM wired"},
                ],
            },
            {
                "phase": 4,
                "name": "Add Omni-Economy",
                "weeks": "16–24",
                "items": [
                    {"id": "4.1", "task": "Neuro-Coins", "status": "implemented", "detail": "oss/economy/neuro_coin.py"},
                    {"id": "4.2", "task": "Trait Marketplace", "status": "planned"},
                    {"id": "4.3", "task": "Memory Marketplace", "status": "planned"},
                    {"id": "4.4", "task": "Desire-Driven Rewards", "status": "planned"},
                    {"id": "4.5", "task": "Soul Bonds", "status": "planned"},
                ],
            },
            {
                "phase": 5,
                "name": "Add Omni-Evolution",
                "weeks": "24+",
                "items": [
                    {"id": "5.1", "task": "Meta-learning", "status": "planned"},
                    {"id": "5.2", "task": "Self-rewriting DNA", "status": "partial", "detail": "oss/dna/omega_rewrite.py"},
                    {"id": "5.3", "task": "Omega-DNA switching", "status": "planned"},
                    {"id": "5.4", "task": "Self-directed evolution", "status": "planned"},
                ],
                "goal": "OSS becomes a true artificial species",
            },
        ],
        "current_phase": 1,
        "next_milestone": "Wire ecosystem_step into live LLM role calls",
    }