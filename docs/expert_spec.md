# Expert Agent Spec

Expert agents extend `sovereign-core`'s `Agent` base class. Each handles one
or more S-ISA opcodes and returns a list of encoded SemanticWord integers.

## Base contract

```python
class Agent:
    id: int
    state: AgentState
    inbox: list[int]
    memory_ref: int
    log: list

    def receive(self, word_int: int) -> None: ...
    def step(self, instruction: Instruction) -> list[int]: ...
```

`step()` must always:
1. Transition `self.state` during processing.
2. Return to `AgentState.IDLE` before returning.
3. Clear `self.inbox` after consuming it.
4. Append a log entry for observability.

## Registered Experts

### PlannerAgent (`experts/planner_agent.py`)
| Opcode | Behaviour |
|---|---|
| `PLAN` | Consumes inbox, emits one `RESULT/PLAN` word at confidence 0.9 |
| others | Falls back to `Agent.step()` |

### CriticAgent (`experts/critic_agent.py`)
| Opcode | Behaviour |
|---|---|
| `CRITIQUE` | Scores each inbox word (confidence − 0.05), emits one word per inbox item |
| `REFLECT` | Emits one `RESULT/REFLECT` word at confidence 0.85 |
| empty inbox + CRITIQUE | Emits one default word at confidence 0.5 |

### BuilderAgent (`experts/builder_agent.py`)
| Opcode | Behaviour |
|---|---|
| `EMIT_RESULT` | Returns current inbox as output; emits default if inbox empty |

### BizAgent (`experts/biz_agent.py`)
| Opcode | Behaviour |
|---|---|
| `SUMMARIZE_MEMORY` | Emits one `MEMORY/SUMMARIZE` word at confidence 0.88 |

### InfraAgent (`experts/infra_agent.py`)
| Opcode | Behaviour |
|---|---|
| `RUN_WORKFLOW` | Reads `args[0]` as workflow_id, emits `TOOL/EXECUTE` word with `payload_ref=workflow_id` |

## Adding a new expert

1. Create `backend/experts/my_agent.py` extending `Agent`.
2. Override `step()` for target opcodes; call `super().step()` for the rest.
3. Register in `MOERouter.load_experts()`:
   ```python
   from backend.experts.my_agent import MyAgent
   experts["my_role"] = MyAgent
   ```
4. Add intent → (role, opcode) entry to `_INTENT_ROUTE` in `moe_router.py`.
5. Add tests in `tests/test_expert_agents.py`.
