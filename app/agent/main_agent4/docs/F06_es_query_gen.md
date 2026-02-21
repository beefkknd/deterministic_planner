# F06: ES Query Gen

## Overview

**Node ID**: F06
**Name**: ES Query Gen
**Type**: LLM Node (🧠)
**Purpose**: Generates Elasticsearch search or aggregation queries based on `analysis_result.intent_type` and entity mappings from F05. Signals `needs_clarification` when the generated query cannot reliably cover the user's intent, so F02 can route to F09 without interpreting confidence numbers.

## Responsibility

1. Receive `analysis_result` and `metadata_results` from F05 (via InputRef)
2. Determine query type: `search` or `aggregation`
3. Generate a valid ES DSL query
4. Write a `query_summary` explaining what was generated and any concerns
5. Set `needs_clarification=True` if the query cannot reliably serve the user's intent
6. Build an `intent` description for key_artifacts storage

## Input

| Input | Source | Description |
|-------|--------|-------------|
| `analysis_result` | InputRef from F05 slot `analysis_result` | Intent type and entity mappings |
| `metadata_results` | InputRef from F05 slot `metadata_results` | Field metadata from ES mappings |
| `description` | sub_goal field | Work instruction from F02 (used as `question`) |

## Output

| Slot | Type | Description |
|------|------|-------------|
| `es_query` | `dict` | Generated Elasticsearch DSL query |
| `intent` | `str` | Human-readable description of the query intent (for key_artifacts) |
| `query_summary` | `str` | LLM prose: what was generated and any metadata coverage concerns |
| `needs_clarification` | `bool` | **True** if F06 cannot reliably generate a query that matches the user's intent |
| `ambiguity` | `dict \| None` | Structured detail about the uncertainty — for F09 to use when building the clarification message |

### When `needs_clarification` is True

F06 makes this decision internally — F02 only reads the flag, never the confidence number. Examples:

| Situation | Example |
|-----------|---------|
| No field matches user's term | User said "owner", no `owner` field in metadata |
| Field uncertainty too high | `arrival_date` vs `eta_date`, cannot pick with confidence |
| Entity mapping gap | Entity was resolved by F05 but no corresponding ES field exists |

`ambiguity` is populated alongside `needs_clarification=True` to give F09 the structured detail it needs (field, alternatives, message). F02 does not read `ambiguity` — it only reads the boolean gate.

### `query_summary` — always present

F06 always fills `query_summary` in plain language, regardless of `needs_clarification`:

```
Clean:   "Generated a bool query filtering shipper_name=MAERSK and destination_port=Los Angeles."
Unclear: "Generated a term query on arrival_date as best guess. User mentioned 'owner' which
          has no direct field match — closest is consignee_name."
```

`query_summary` is context for F02's completed-output view. It is not a routing signal.

## Query Types

### Search Query
```python
{
    "query": {
        "bool": {
            "must": [
                {"term": {"shipper_name.keyword": "MAERSK"}},
                {"term": {"destination_port.keyword": "Los Angeles"}}
            ]
        }
    }
}
```

### Aggregation Query
```python
{
    "size": 0,
    "aggs": {
        "by_shipper": {
            "terms": {"field": "shipper_name.keyword", "size": 10}
        }
    }
}
```

## Examples

### Clean Query
```python
Output:
{
    "es_query": {"query": {"bool": {"must": [{"term": {"shipper_name.keyword": "MAERSK"}}]}}},
    "intent": "MAERSK",
    "query_summary": "Generated a bool query filtering on shipper_name=MAERSK.",
    "needs_clarification": False,
    "ambiguity": None,
}
# F02 sees needs_clarification=False → dispatches F07 (es_query_exec)
```

### Ambiguous Field
```python
Output:
{
    "es_query": {"query": {"term": {"arrival_date": "2024-01-15"}}},
    "intent": "arrival yesterday",
    "query_summary": "Used arrival_date as best guess. Uncertain whether user meant eta_date or departure_date.",
    "needs_clarification": True,
    "ambiguity": {
        "field": "date",
        "message": "Cannot determine which date field the user means",
        "alternatives": ["arrival_date", "eta_date", "departure_date"],
    },
}
# F02 sees needs_clarification=True → dispatches F09 (clarify_question)
# F09 receives ambiguity dict to build the clarification message
```

## Precondition Gate Effect on Downstream Workers

`needs_clarification` gates F07 and activates F09 — F02 routes by precondition matching:

| Worker | Precondition | Dispatched when |
|--------|-------------|-----------------|
| F07 (es_query_exec) | `needs_clarification=False from es_query_gen` | Clean query generated |
| F09 (clarify_question) | `needs_clarification=True from metadata_lookup or es_query_gen` | Uncertain query |

## Data Flow

F06 is always dispatched **alone** so F02 has a round boundary to read its outputs before deciding the next step.

```
Round N:
  F05: Lookup Metadata → {analysis_result, metadata_results, needs_clarification=False}
  F02: dispatches F06 alone (F05 was clean — F06 precondition met)

Round N+1:
  F06: ES Query Gen → {es_query, intent, query_summary, needs_clarification, ambiguity?}
  F02 reads needs_clarification:
    False → dispatch F07 (es_query_exec)
              params["bundles_with_sub_goal"] = F06_id
    True  → dispatch F09 (clarify_question)
              F09 receives ambiguity from F06 outputs

Round N+2 (if F07 dispatched):
  F07: ES Query Exec
  F13: builds merged key_artifact from F06+F07 via completed_outputs (cross-round bundling)
```

## State Changes

F06 is a stateless worker. F13 reads `memorable_slots=["es_query"]` from the registry to create a `KeyArtifact` of type `es_query` in `key_artifacts`. The `intent` string becomes the artifact's `intent` field.

## Error Handling

- No entity mappings and no question: Returns `status="failed"`
- LLM failure: Returns `status="failed"` with exception message
- Invalid query generated: Returns `status="failed"` (LangChain structured output validation)

## Registry Entry

```python
@worker_tool(
    preconditions=[
        "has metadata_results from metadata_lookup",
        "has analysis_result with intent_type",
        "needs_clarification=False from metadata_lookup",
    ],
    outputs=["es_query", "intent", "query_summary", "needs_clarification", "ambiguity"],
    goal_type="support",
    name="es_query_gen",
    description="Generates search or aggregation ES query based on analysis_result.intent_type; signals needs_clarification if query cannot reliably cover user intent",
    memorable_slots=["es_query"],
    synthesis_mode="hidden",
)
```

## Integration Points

- **Input**: From F02 (fan-out), requires F05 `analysis_result`, `metadata_results`, and `needs_clarification=False`
- **Output**: To F07 (`es_query` via InputRef when `needs_clarification=False`); F09 dispatched when `needs_clarification=True`; F13 builds `es_query` key artifact
