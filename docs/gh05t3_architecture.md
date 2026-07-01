# GH05T3 Architecture

## Overview

GH05T3 is built on the **sovereign-core** kernel. All agent communication uses
the 64-bit **SemanticWord** encoding and the **S-ISA** instruction set. The
kernel Runtime handles agent lifecycle, message routing, and event hooks.

```
┌────────────────────────────────────────────────────────────────┐
│                        gateway_v3.py (port 8002)               │
│   HTTP / WebSocket API surface — JSON ↔ SemanticWord bridge    │
└───────────────────────────┬────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────┐
│                     ContentWorkflow                            │
│   plan → critique → emit pipeline                              │
└───────────────────────────┬────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────┐
│                       MOERouter                                │
│   intent → expert agent dispatch                               │
└──────┬──────┬──────┬──────┬──────┬─────────────────────────────┘
       │      │      │      │      │
   Planner Critic Builder  Biz   Infra
       │      │      │      │      │
       └──────┴──────┴──────┴──────┘
                      │
                      ▼
┌────────────────────────────────────────────────────────────────┐
│                    KernelAdapter                               │
│   wraps sovereign-core Runtime                                 │
└────────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────────────────┐
│              sovereign-core Runtime                            │
│   agents · payload table · hooks · S-ISA dispatch             │
└────────────────────────────────────────────────────────────────┘
```

## Layers

| Layer | Module | Purpose |
|---|---|---|
| Gateway | `backend/gateway_v3.py` | REST/WS surface, JSON ↔ SemanticWord |
| Workflow | `backend/workflows/content_workflow.py` | Orchestrates plan→critique→emit |
| Router | `backend/core/moe_router.py` | Maps intent to expert |
| Experts | `backend/experts/` | Typed Agent subclasses per role |
| Registry | `backend/core/expert_registry.py` | Role → class lookup |
| Adapter | `backend/integration/kernel_adapter.py` | Runtime wrapper with role tracking |
| Kernel | `sovereign-core/src/kernel/runtime.py` | Core Runtime (external repo) |

## Message Flow

```
User request (JSON)
    │
    ▼  gateway_v3 converts to SemanticWord
    ▼
ContentWorkflow.run(input_word_int)
    │
    ├─ MOERouter.route(PLAN word) → PlannerAgent.step(PLAN)
    │         → emits RESULT/PLAN word
    │
    ├─ MOERouter.route(CRITIQUE word) → CriticAgent.step(CRITIQUE)
    │         → emits RESULT/CRITIQUE word with adjusted confidence
    │
    └─ MOERouter.route(EMIT word) → BuilderAgent.step(EMIT_RESULT)
              → emits final RESULT words
    │
    ▼  gateway_v3 converts back to JSON
User response
```

## Downstream Integration Points

| Repo | Integration |
|---|---|
| sovereign-core | Runtime, SemanticWord, S-ISA — imported via `SOVEREIGN_CORE_PATH` |
| HyperAgents | Imports KernelAdapter, builds task graphs, schedules instructions |
| Termux-TIA | HTTP client → gateway_v3 :8002 via `GH05T3_GATEWAY_URL` |
| Honcho | WebSocket client → `/ws/events` on gateway_v3 |
