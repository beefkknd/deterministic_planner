# F13: Join Reduce

## Overview

**Node ID**: F13
**Name**: Join Reduce
**Type**: Non-LLM Node (—)
**Purpose**: Collects all worker results, routes back to planner or synthesizer

## Responsibility

1. Collect all WorkerResult outputs from parallel workers
2. Update sub-goal statuses (success/failed)
3. Store completed outputs for future reference
4. Determine if all work is complete
5. Route to next step (F02 or F14)

## Input

- `worker_results`: List of WorkerResult from all executed workers

## WorkerResult Structure

```python
class WorkerResult(TypedDict):
    sub_goal_id: int
    status: Literal["success", "failed"]
    outputs: dict[str, Any]  # slot_name -> value
    error: Optional[str]
    message: Optional[str]
```

## Processing Steps

### 1. Update Sub-Goal Statuses
```python
for result in worker_results:
    sg = find_sub_goal(state, result["sub_goal_id"])
    sg["status"] = result["status"]
    sg["result"] = result["outputs"]
    sg["error"] = result.get("error")
```

### 2. Store Completed Outputs
```python
# For dependency resolution in future rounds
state["completed_outputs"][result["sub_goal_id"]] = result["outputs"]
```

### 3. Increment Round
```python
state["round"] += 1
```

### 4. Route Decision
```python
deliverables = [sg for sg in sub_goals if sg.goal_type == "deliverable"]
completed = [sg for sg in deliverables if sg.status == "success"]

if len(completed) == len(deliverables):
    return "synthesizer"  # F14
else:
    return "planner"  # F02 - continue
```

## Decision Logic

```
All deliverables complete?
    │
    ├─ Yes → F14: Synthesizer
    │
    └─ No → F02: Deterministic Planner (next round)
              │
              ├─ Max rounds reached? → Failed
              └─ Continue planning
```

## Data Flow

```
Workers (F04-F12)
    │
    ├─ F04 → WorkerResult
    ├─ F05 → WorkerResult
    ├─ F06 → WorkerResult
    ├─ ...
    └─ F12 → WorkerResult
          │
          ↓
    F13: Join Reduce
          │
          ├─ incomplete → F02 (loop back)
          │
          └─ complete → F14: Synthesizer
```

## State Changes

- Updates each sub_goal's `status`
- Stores `result` in sub_goal
- Stores outputs in `completed_outputs`
- Increments `round`
- Sets `status` to "planning" for next round

## Error Handling

- Worker exception: Already wrapped by try/catch decorator
- Missing results: Log warning, continue with available data

## Design Notes

- This is the reduce phase of the Map/Reduce pattern
- Always executes after workers complete
- Handles both success and failure uniformly

## Integration Points

- **Input**: From all workers (F04-F12)
- **Output**: To F02 (continue) or F14 (synthesize)
