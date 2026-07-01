# MOE Routing Spec

## Purpose

The `MOERouter` (Mixture-of-Experts Router) maps an incoming SemanticWord's
`intent` field to the correct expert agent and S-ISA opcode, then dispatches
the instruction through the KernelAdapter's Runtime.

## Routing Table

| IntentType | Expert Role | S-ISA Opcode |
|---|---|---|
| PLAN | planner | PLAN |
| CRITIQUE | critic | CRITIQUE |
| REFLECT | critic | REFLECT |
| EXECUTE | builder | EMIT_RESULT |
| EMIT | builder | EMIT_RESULT |
| SUMMARIZE | biz | SUMMARIZE_MEMORY |
| QUERY | infra | RUN_WORKFLOW |
| (any other) | planner | PLAN (fallback) |

## Dispatch Flow

```
MOERouter.route(word_int)
    │
    ├─ SemanticWord.decode(word_int) → extract intent
    │
    ├─ look up (role, opcode) in _INTENT_ROUTE
    │
    ├─ KernelAdapter.send(0, expert_id, word_int)   ← load inbox
    │
    └─ KernelAdapter.dispatch(expert_id, opcode)    ← run step()
              │
              └─ returns list[int]  (emitted SemanticWords)
```

## Initialization

`load_experts()` must be called before `route()`. It:
1. Imports all five expert classes.
2. Registers them in `ExpertRegistry`.
3. Spawns one kernel agent per role via `KernelAdapter.spawn()`.
4. Replaces the default `Agent` instance with the typed subclass.

## ContentWorkflow usage

```python
router = MOERouter()
router.load_experts()

workflow = ContentWorkflow(router)
results = workflow.run(input_word_int)
# results: list of encoded SemanticWord integers ready for JSON serialization
```

## Extending routing

Add new rows to `_INTENT_ROUTE` in `backend/core/moe_router.py`:
```python
_INTENT_ROUTE: dict[int, tuple[str, Opcode]] = {
    ...
    int(IntentType.VOTE): ("critic", Opcode.VOTE),
}
```
Then register the corresponding expert (or reuse an existing one).
