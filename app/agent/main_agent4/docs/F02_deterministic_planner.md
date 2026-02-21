# F02: Deterministic Planner

## Overview

**Node ID**: F02
**Name**: Deterministic Planner
**Type**: LLM Node (🧠)
**Purpose**: Central orchestrator that plans sub-goals with InputRef dependency wiring, decides continue/done/failed, and routes via `route_after_planner`.

## Responsibility

1. Analyze the normalized `main_goal` from F01 (or from prior rounds)
2. Read F01 context flags from `completed_outputs[0]` (round 1 only)
3. Check worker preconditions against available data
4. Emit a batch of sub-goals with InputRef wiring for the current round
5. Track pending sub-goals (awaiting dependencies) to avoid duplicates
6. Decide `continue`, `done`, or `failed`
7. When `done`: emit `synthesis_inputs` referencing deliverable outputs

## Input

- `question`: Normalized main goal (from F01)
- `worker_registry`: Formatted list of workers with preconditions/outputs
- `completed_outputs`: Data from successfully completed sub-goals (keyed by sub-goal id)
- `sub_goals`: All sub-goals including pending, success, failed
- `round`: Current round number
- `max_rounds`: Round budget (default 10)

## Pydantic Output Model

F02 uses structured output via `PlannerDecision`:

```python
class PlannerDecision(BaseModel):
    action: Literal["continue", "done", "failed"]
    reasoning: str
    sub_goals: list[PlannedSubGoal]      # Only when action=continue
    synthesis_inputs: dict[str, PlannedInputRef]  # Only when action=done

class PlannedSubGoal(BaseModel):
    worker: str
    description: str
    inputs: dict[str, PlannedInputRef]   # InputRef wiring
    params: dict[str, Any]               # Static parameters
    goal_type: Literal["support", "deliverable"]

class PlannedInputRef(BaseModel):
    from_sub_goal: int   # Source sub-goal ID
    slot: str            # Output slot name from source
```

## Decision Logic

### Continue
Dispatch new sub-goals for this round:
```python
{
    "action": "continue",
    "reasoning": "Metadata resolved, now generating ES query",
    "sub_goals": [
        {
            "worker": "es_query_gen",
            "inputs": {"analysis_result": {"from_sub_goal": 1, "slot": "analysis_result"}},
            "params": {},
            "goal_type": "support"
        }
    ]
}
```

### Done
All deliverables satisfied; emit synthesis references:
```python
{
    "action": "done",
    "reasoning": "Results retrieved and formatted",
    "synthesis_inputs": {"results": {"from_sub_goal": 3, "slot": "formatted_results"}}
}
```

### Failed
Unrecoverable error or max rounds exceeded:
```python
{
    "action": "failed",
    "reasoning": "Entity could not be resolved after 2 retries"
}
```

## F01 Context (completed_outputs[0])

F01 writes a synthetic context sub-goal at id=0 in `completed_outputs`. F02 reads this via `_format_f01_context` (round 1 only) and injects presence flags into the planner prompt:

```
Context from F01: has_prior_es_query, has_user_es_query
```

Available slots in `completed_outputs[0]`:

| Slot | Description |
|------|-------------|
| `prior_es_query` | ES query dict from prior turn's pagination artifact |
| `prior_next_offset` | Offset for next page |
| `prior_page_size` | Page size from prior pagination |
| `user_es_query` | Raw ES query text pasted by user |
| `force_execute` | `True` if user wants to bypass clarification (present only when True) |

**Round guard**: `_format_f01_context` returns `""` for rounds > 1. The F01 context is only meaningful for the initial planning decision.

## InputRef Wiring

Sub-goals can wire inputs from any completed or newly created sub-goal:

```python
# Wire from prior completed sub-goal
"inputs": {"metadata": {"from_sub_goal": 1, "slot": "analysis_result"}}

# Wire from F01 context (id=0)
"inputs": {
    "es_query": {"from_sub_goal": 0, "slot": "prior_es_query"},
    "offset": {"from_sub_goal": 0, "slot": "prior_next_offset"},
    "limit": {"from_sub_goal": 0, "slot": "prior_page_size"},
}

# Wire from a new sub-goal in the same batch (forward reference)
"inputs": {"es_query": {"from_sub_goal": 2, "slot": "es_query"}}
```

`_convert_planned_sub_goals` validates all InputRefs. Invalid references mark the sub-goal as `failed` immediately.

## Key Planner Rules (from system prompt)

| Rule | Description |
|------|-------------|
| 1. PRECONDITIONS | Never dispatch a worker whose preconditions aren't met |
| 2. DEPENDENCY WIRING | Wire outputs between sub-goals via InputRef |
| 3. F01 CONTEXT (id=0) | Use `from_sub_goal: 0` for pagination/query context from F01 |
| 4. ROUND BUDGET | Plan efficiently within `max_rounds` |
| 5. CLARIFICATION ROUTING | Dispatch F06 alone; read `needs_clarification` to route to F07 or F09; `force_execute` bypasses this |
| 6. PARTIAL SUCCESS | May declare "done" with partial results |
| 7. FIRST ROUND | FAQ → common_helpdesk; Data queries → metadata_lookup first |
| 8. WIRING BETWEEN ROUNDS | Always wire from correct sub-goal id and slot |
| 9. PAGINATION | `has_prior_es_query` → dispatch page_query; wire from `completed_outputs[0]` |
| 10. PENDING SUB-GOALS | Do NOT duplicate pending sub-goals; they dispatch when ready |
| 11. EXPLICIT SIZE | User-specified result count → `params["size"]` (not in query body) |
| 12. QUERY BUNDLING | Always set `params["bundles_with_sub_goal"]` on F07; F13 handles cross-round merging |

## Clarification Routing (Rule 5)

F05 and F06 both output `needs_clarification: bool`. F02 routes by matching worker preconditions against this flag — no threshold arithmetic, no confidence values in F02 logic.

| Signal source | `needs_clarification` | F02 routes to |
|---------------|-----------------------|---------------|
| F05 (`metadata_lookup`) | `True` | F09 (`clarify_question`); F06 precondition NOT met |
| F05 (`metadata_lookup`) | `False` | F06 (`es_query_gen`); precondition met |
| F06 (`es_query_gen`) | `True` | F09 (`clarify_question`); F07 precondition NOT met |
| F06 (`es_query_gen`) | `False` | F07 (`es_query_exec`); precondition met |

The threshold decision (what counts as "needs clarification") lives inside F05 and F06's own LLM calls — not in F02. F02 only reads the boolean.

`query_summary` (F06 output) is prose context visible in completed-output view. It is not a routing signal — F02 reads it for understanding, not for branching.

**Critical**: F06 must always be dispatched **alone** (not bundled with F07 in the same round). This gives F02 one round boundary to read `needs_clarification` before dispatching F07 or F09. F13 supports cross-round artifact merging via `completed_outputs` lookup.

### Force Execute Override

When `force_execute=True` appears in F01 context (`completed_outputs[0]`), F02 bypasses normal clarification routing:

| Condition | F02 Action |
|-----------|------------|
| `force_execute=True` AND `es_query` exists in `completed_outputs` | Dispatch F07 (`es_query_exec`) directly using the cached query; skip F06 entirely |
| `force_execute=True` AND no query yet | Dispatch F06 with `params["force_execute"]=True`; F06 will suppress `needs_clarification` internally and proceed to execute |

This allows users to say "just run it", "don't ask", or "use best guess" to bypass the clarification flow.

## Query Bundling (Rule 12)

When dispatching F07 after F06 has completed (in a later round), set `bundles_with_sub_goal` so F13 merges their key_artifacts:

```python
# Round N: F06 was dispatched alone and completed
# Round N+1: F02 sees needs_clarification=False, dispatches F07:
{
    "worker": "es_query_exec",
    "inputs": {"es_query": {"from_sub_goal": 1, "slot": "es_query"}},
    "params": {"bundles_with_sub_goal": 1},   # F06's sub-goal ID
    "goal_type": "support"
}
```

F13 handles the cross-round case: when F06 ran in a previous round, it fetches `es_query` from `completed_outputs[bundles_with]` to build the merged artifact.

## Pending Sub-Goal Tracking

F02 sees three sections in the prompt:
- **Completed sub-goals**: Their outputs (for wiring)
- **Failed sub-goals**: Their errors (for retry/fallback decisions)
- **Pending sub-goals**: Their descriptions and dependency descriptions (to avoid duplicates)

`_format_pending_context` shows pending sub-goals with their unresolved dependencies, e.g.:
```
- sub_goal 3 (show_results): Display search results
  waiting for: es_results: from sg2.es_results
```

## State Changes

- Appends new sub-goals to `state["sub_goals"]`
- Sets `state["status"]` to `"executing"`, `"done"`, or `"failed"`
- Stores `state["planner_reasoning"]` for debugging
- When `done`: Sets `state["synthesis_inputs"]` for F14

## Data Flow

```
F01 → F02 (round 1)
F13 → F02 (rounds 2+)

F02 output → route_after_planner:
    status="executing" → Send() fan-out to F03 × N
    status="done"      → f14_synthesizer
    status="failed"    → END
```

## Error Handling

- Round budget exceeded: Sets `status="failed"` before calling LLM
- No `question` in state: Sets `status="failed"`
- `continue` with empty sub-goals: Sets `status="failed"`
- Invalid synthesis_inputs (slot not found): Skipped with a warning log
- LLM exception: Sets `status="failed"` with exception message

## Integration Points

- **Input**: From F01 (first round), from F13 (subsequent rounds)
- **Output**: Via `route_after_planner` conditional edge to workers, F14, or END
