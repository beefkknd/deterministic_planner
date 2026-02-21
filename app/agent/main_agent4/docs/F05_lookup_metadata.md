# F05: Lookup Metadata

## Overview

**Node ID**: F05
**Name**: Lookup Metadata
**Type**: LLM Node (🧠)
**Purpose**: Entity name resolution via LLM, then field metadata + reference value lookup from ES mappings. Signals `needs_clarification` when entity resolution is ambiguous or incomplete, so F02 can route to F09 without interpreting resolution details.

## Responsibility

1. Resolve entity names to canonical values (e.g., "Maersk" → "MAERSK")
2. Identify relevant fields in the data schema
3. Look up field metadata from ES mappings
4. Find reference values for filtering
5. Generate `analysis_result` with intent_type
6. Set `needs_clarification=True` if resolution was ambiguous or incomplete

## Input

- `user_query`: Original user question
- `resolved_inputs`: Empty or from previous metadata lookups (for multi-entity queries)

## Output

| Slot | Type | Description |
|------|------|-------------|
| `metadata_results` | `dict` | Field names, types, descriptions from ES mappings |
| `value_results` | `dict` | Reference values for the identified entities |
| `analysis_result` | `dict` | `{ intent_type: "search" \| "aggregation" \| "comparison" }` |
| `needs_clarification` | `bool` | **True** if F05 could not cleanly resolve entities — F02 should route to F09 instead of F06 |

### When `needs_clarification` is True

F05 sets this flag when it cannot proceed confidently. Examples:

| Situation | Example |
|-----------|---------|
| Multiple entity matches | "ACME" resolves to 3 different shippers |
| No field match for user term | User says "owner" — no `owner` field exists |
| Unresolved entities | Entity extraction returned `unresolved_entities` list |
| Low-confidence canonical value | Less than 70% confidence in any single resolution |

When `needs_clarification=True`, F05 still populates the other output slots with whatever it found — the data is available for F09 to use as context when generating the clarification message.

## Two-Stage Process

### Stage 1: Entity Resolution (LLM)
```
Input: "Maersk shipments to LA"
→ LLM identifies:
  - Entity 1: shipper = "Maersk" → canonical: "MAERSK"   (confidence: 0.95)
  - Entity 2: destination = "LA" → canonical: "Los Angeles" (confidence: 0.90)
→ needs_clarification: False  (clean resolution)
```

```
Input: "ACME shipments"
→ LLM identifies:
  - Entity 1: shipper = "ACME" → 3 candidates: "ACME Corp LLC", "ACME Corporation", "ACME Co"
→ needs_clarification: True  (ambiguous match)
```

### Stage 2: Metadata Lookup (ES)
```
Lookup ES mappings for resolved fields:
  - shipper_name field
  - destination_port field

Return field types, descriptions, and available values
```

## Analysis Result

The `analysis_result` guides downstream workers when `needs_clarification=False`:

| Intent Type | Description | Next Worker |
|-------------|-------------|-------------|
| search | User wants to find specific records | F06: ES Query Gen |
| aggregation | User wants counts/sums/averages | F06: ES Query Gen |
| comparison | User wants to compare entities | F06: ES Query Gen → F12 |

## Examples

### Clean Resolution
```python
Output:
{
    "metadata_results": {"shipper_name": {...}, "destination_port": {...}},
    "value_results": {"shipper_name": ["MAERSK"], "destination_port": ["Los Angeles"]},
    "analysis_result": {"intent_type": "search", "entity_mappings": {"Maersk": "MAERSK"}},
    "needs_clarification": False,
}
```

### Ambiguous Resolution
```python
Output:
{
    "metadata_results": {"shipper_name": {...}},
    "value_results": {"shipper_name": ["ACME Corp LLC", "ACME Corporation", "ACME Co"]},
    "analysis_result": {"intent_type": "search", "entity_mappings": {}},
    "needs_clarification": True,
}
# F02 sees needs_clarification=True → dispatches F09 (clarify_question)
# F09 receives value_results to build "Did you mean: ACME Corp LLC, ACME Corporation, ACME Co?"
```

## Data Flow

```
F02: Deterministic Planner
    ↓
F05: Lookup Metadata
    ↓
{ metadata_results, value_results, analysis_result, needs_clarification }
    ↓
F13: Join Reduce → F02 (next round)

F02 next round:
    needs_clarification=False → F06 (es_query_gen) precondition met
    needs_clarification=True  → F09 (clarify_question) precondition met
                                F06 precondition NOT met (blocks query generation)
```

## Precondition Gate Effect on Downstream Workers

`needs_clarification` acts as a gate on worker preconditions — F02 routes by matching, not by interpreting the value:

| Worker | Precondition | Dispatched when |
|--------|-------------|-----------------|
| F06 (es_query_gen) | `needs_clarification=False from metadata_lookup` | Clean resolution |
| F09 (clarify_question) | `needs_clarification=True from metadata_lookup or es_query_gen` | Ambiguous resolution |

## State Changes

F05 is a stateless worker. F13 reads `memorable_slots=["analysis_result"]` from the registry to create an `analysis_result` key artifact.

## Error Handling

- Entity not found: Populate best-effort results, set `needs_clarification=True`
- Multiple matches: Populate all candidates in `value_results`, set `needs_clarification=True`
- LLM failure: Return `status="failed"`

## Registry Entry

```python
@worker_tool(
    preconditions=["has entity or reference to look up"],
    outputs=["metadata_results", "value_results", "analysis_result", "needs_clarification"],
    goal_type="support",
    name="metadata_lookup",
    description="Resolves entity names via LLM, then looks up field metadata and reference values from ES mappings",
    memorable_slots=["analysis_result"],
    synthesis_mode="hidden",
)
```

## Design Notes

### F10 (Explain Metadata) and `needs_clarification` Do Not Conflict

F10 and F09 serve distinct intent paths — they can both be dispatched in the same round without conflict.

The key: F05's LLM interprets "multiple field matches" differently depending on **intent**:

| Intent | Situation | `needs_clarification` | Why |
|--------|-----------|----------------------|-----|
| `explain` | User asks "what date fields do you have?" — finds `arrival_date`, `eta_date`, `departure_date` | `False` | Multiple results is the correct answer — nothing is ambiguous |
| `search` | User says "shipments arriving yesterday" — finds `arrival_date`, `eta_date`, `departure_date` | `True` | F05 cannot confidently pick a single field — user clarification needed |

**Hybrid queries** ("what date fields are there, and show me yesterday's arrivals") are handled naturally:

- F05 sets `needs_clarification=True` (the search portion is ambiguous)
- F02 can dispatch **F10 and F09 in parallel** — F10 explains the fields, F09 asks which one the user meant
- F06 is blocked (its precondition `needs_clarification=False from metadata_lookup` is not met)

This means the threshold logic stays inside F05 — F02 never needs to read intent type to decide routing. It only reads the boolean gate.

## Integration Points

- **Input**: From F02 (fan-out)
- **Output**: To F06 (when `needs_clarification=False`), F09 (when `needs_clarification=True`), F10 (Explain Metadata), F13 (Join Reduce)
