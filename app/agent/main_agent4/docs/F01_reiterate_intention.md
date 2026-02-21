# F01: Reiterate Intention

## Overview

**Node ID**: F01
**Name**: Reiterate Intention
**Type**: LLM Node (🧠)
**Purpose**: Entry point that reads chat history and restates the user's intent as an executable main goal. Writes pagination/query context into `completed_outputs[0]` for F02 to wire via InputRef.

## Responsibility

1. Receive the current user message from state (`question`)
2. Read conversation history (`TurnSummary` list from `conversation_history`)
3. Restate the user's intent as a clear, actionable `main_goal`
4. Detect if the user pasted/referenced an ES query (`user_query_text`)
5. Detect if the user is referencing prior results ("show more", "next page")
6. Write context slots to `completed_outputs[0]` for downstream InputRef wiring

## Pydantic Output Model

F01 uses structured output via `ReiterateResult`:

```python
class ReiterateResult(BaseModel):
    main_goal: str            # Clear, actionable restatement of intent
    reasoning: str            # How the intent was interpreted
    user_query_text: str | None  # Raw ES query if user pasted/referenced one
    references_prior_results: bool  # True if user wants next page / prior data
    force_execute: bool       # True if user wants to skip clarification ("just run it", "don't ask")
```

## Input

- `question`: The raw user message from state
- `conversation_history`: `List[TurnSummary]` from state (maintained by main app)

## Output (State Changes)

F01 is **not stateless** — it writes two things to state:

1. **`question`**: Replaced with the normalized `main_goal` string
2. **`completed_outputs[0]`**: Synthetic context sub-goal slot populated with:
   - `prior_es_query`: ES query dict from the most recent `es_query` key artifact in history (if `references_prior_results=True` and artifact found)
   - `prior_next_offset`: Offset for next page (from the same artifact)
   - `prior_page_size`: Page size from the same artifact
   - `user_es_query`: Raw ES query text if user pasted or referenced a query
   - `force_execute`: `True` if user explicitly requested execution without clarification (only present when `force_execute=True`)

The `completed_outputs[0]` dict is sparse — only slots that are present get written. F02 checks for presence flags (`has_prior_es_query`, `has_user_es_query`) via `_format_f01_context`.

## Data Flow

```
START (HumanMessage in state["question"])
    ↓
F01: Reiterate Intention
    ├── Normalize question → state["question"] = main_goal
    └── Write context → state["completed_outputs"][0]
    ↓
F02: Deterministic Planner
    (reads completed_outputs[0] via _format_f01_context)
```

## Behavior Examples

### Simple Query
```
User: "Show me Maersk shipments to LA"
→ main_goal: "Find all shipments from shipper 'Maersk' to destination 'Los Angeles'"
→ completed_outputs[0]: {}  (no special context)
```

### Multi-Intent Query
```
User: "what's a shipment and find me one from yesterday"
→ main_goal: "(1) Explain what a shipment is (2) Find shipments that arrived yesterday"
→ completed_outputs[0]: {}
```

### Prior Result Reference
```
User: "show me more" (after a prior turn with es_query key artifact)
→ main_goal: "Show next page of the previous search results"
→ references_prior_results: True
→ completed_outputs[0]: {
    "prior_es_query": {"query": {"term": {"shipper_name": "MAERSK"}}},
    "prior_next_offset": 20,
    "prior_page_size": 20
  }
```

### User-Pasted Query
```
User: 'run this: {"query": {"match_all": {}}}'
→ main_goal: "Execute the provided Elasticsearch query"
→ user_query_text: '{"query": {"match_all": {}}}'
→ completed_outputs[0]: {
    "user_es_query": '{"query": {"match_all": {}}}'
  }
```

### Force Execute (Skip Clarification)
```
User: "just run it, don't ask me anything"
→ main_goal: "just run it, don't ask me anything"
→ force_execute: True
→ completed_outputs[0]: {
    "force_execute": True
  }
```
F02 sees `force_execute=True` and bypasses clarification routing — dispatches F07 directly if an ES query already exists, or F06 with `params["force_execute"]=True` if not.

## Helper Functions

### `_convert_history_to_messages(history)`
Converts `List[TurnSummary]` into a chat transcript string (last 5 turns max).
Each turn becomes:
```
Human: <question>
AI: <response>
[Prior queries: <artifact_intent>]  ← appended if key_artifacts exist
```

### `_find_prior_agent_query(history)`
Scans history most-recent-first, returns the first `type=="es_query"` artifact's `slots` dict. Used to populate `prior_es_query`, `prior_next_offset`, `prior_page_size`.

## Error Handling

- If `question` is empty: Returns state unchanged with a warning log
- If `main_goal` is empty after LLM: Falls back to original `question`
- LLM failure: Returns state unchanged (original question preserved), logs error

## Design Notes

- F01 runs **once per turn** at entry
- All subsequent F02 rounds skip F01 (direct F13 → F02 loop)
- `completed_outputs[0]` uses sub-goal id=0 as the synthetic "F01 context" slot
- `_format_f01_context` in F02 only injects flags in round 1 (not later rounds)

## Integration Points

- **Input**: Reads from `state["question"]` and `state["conversation_history"]`
- **Output**: Updates `state["question"]` and `state["completed_outputs"][0]`
- **Downstream**: F02 reads `completed_outputs[0]` presence flags; workers wire InputRefs against it via `from_sub_goal: 0`
