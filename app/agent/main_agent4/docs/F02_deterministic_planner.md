# F02: Deterministic Planner

## Overview

**Node ID**: F02
**Name**: Deterministic Planner
**Type**: LLM Node (🧠)
**Purpose**: Central orchestrator that plans sub-goals, checks worker preconditions, and decides continue/done/failed

## Responsibility

1. Analyze the main goal from F01
2. Check worker preconditions against available data
3. Emit a batch of sub-goals for the current round
4. Decide whether to continue, done, or failed
5. Handle dependencies between sub-goals
6. React to success/failure of previous rounds

## Input

- `main_goal`: From F01 output
- `worker_registry`: List of all available workers with preconditions
- `completed_outputs`: Data from successfully completed sub-goals
- `failed_sub_goals`: List of failed sub-goals with errors
- `round`: Current round number

## Output

- `action`: "continue" | "done" | "failed"
- `sub_goals`: List of SubGoal objects to execute
- `reasoning`: Human-readable explanation for the decision
- `synthesis_inputs`: References for F14 when action=done

## Decision Logic

### Continue
When there are pending sub-goals that can be executed with available data:
```python
{
    "action": "continue",
    "reasoning": "Metadata resolved, now generating ES query",
    "sub_goals": [
        {
            "id": "sb2",
            "worker": "es_query_gen",
            "inputs": {"metadata": {"from_sub_goal": "sb1", "slot": "metadata_results"}},
            ...
        }
    ]
}
```

### Done
When all deliverable sub-goals are complete:
```python
{
    "action": "done",
    "reasoning": "All data retrieved and question satisfied",
    "synthesis_inputs": {"results": {"from_sub_goal": "sb3", "slot": "formatted_results"}}
}
```

### Failed
When max rounds exceeded or unrecoverable error:
```python
{
    "action": "failed",
    "reasoning": "Entity 'XYZ Corp' could not be resolved after 2 retries"
}
```

## Precondition Checking

F02 evaluates each worker's preconditions against available data:

| Worker | Preconditions |
|--------|---------------|
| common_helpdesk | user query is a common/general question |
| metadata_lookup | has entity or reference to look up |
| es_query_gen | has metadata_results + analysis_result |
| es_query_exec | has ES query |
| page_query | has es_query with pagination params |
| clarify_question | planner identified ambiguity |
| explain_metadata | has metadata_results |
| show_results | has es_results |
| analyze_results | has es_results + user wants analysis |

## Data Flow

```
F01 Output → F02: Deterministic Planner
                    ↓
           { action, sub_goals }
                    ↓
        ┌───────────┴───────────┐
        ↓                       ↓
   Continue:              Done/Failed:
   Fan-out to            → F14: Synthesizer
   workers (F04-F12)     → END
        ↓
   All workers → F13: Join Reduce
        ↓
   Back to F02 (next round)
```

## State Changes

- Updates `sub_goals` list with new sub-goals
- Sets `status` to "executing", "done", or "failed"
- Stores `planner_reasoning` for debugging

## Error Handling

- Retry logic: If a sub-goal fails, F02 decides whether to retry or try alternative
- Partial success: F02 determines if partial results are acceptable
- Max rounds: Configurable cap (default 5-10) to prevent infinite loops

## Design Notes

- This is the brain of the system - all decisions flow through here
- Fully autonomous - no human messages between rounds
- Uses the WORKER_REGISTRY to dynamically dispatch work
- Reads "tone" from worker outputs to handle uncertainty

## Integration Points

- **Input**: From F01 (first round), from F13 (subsequent rounds)
- **Output**: To F04-F12 (workers), F14 (synthesizer), or END (failed)
