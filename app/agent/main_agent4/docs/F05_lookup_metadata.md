# F05: Lookup Metadata

## Overview

**Node ID**: F05
**Name**: Lookup Metadata
**Type**: LLM Node (🧠)
**Purpose**: Entity name resolution via LLM, then field metadata + reference value lookup from ES mappings

## Responsibility

1. Resolve entity names to canonical values (e.g., "Maersk" → "MAERSK")
2. Identify relevant fields in the data schema
3. Look up field metadata from ES mappings
4. Find reference values for filtering
5. Generate `analysis_result` with intent_type

## Input

- `user_query`: Original user question
- `resolved_inputs`: Empty or from previous metadata lookups (for multi-entity queries)

## Output

- `metadata_results`: Field names, types, descriptions from ES mappings
- `value_results`: Reference values for the identified entities
- `analysis_result`: { intent_type: "search" | "aggregation" | "comparison" }

## Two-Stage Process

### Stage 1: Entity Resolution (LLM)
```
Input: "Maersk shipments to LA"
→ LLM identifies:
  - Entity 1: shipper = "Maersk" → canonical: "MAERSK"
  - Entity 2: destination = "LA" → canonical: "Los Angeles"
```

### Stage 2: Metadata Lookup (ES)
```
Lookup ES mappings for:
  - shipper_name field
  - destination_port field

Return field types, descriptions, and available values
```

## Analysis Result

The `analysis_result` guides downstream workers:

| Intent Type | Description | Next Worker |
|-------------|-------------|-------------|
| search | User wants to find specific records | F06: ES Query Gen |
| aggregation | User wants counts/sums/averages | F06: ES Query Gen |
| comparison | User wants to compare entities | F06: ES Query Gen → F12 |

## Example

```
Input: "Show Maersk shipments to Los Angeles"

Stage 1 - LLM:
  entity_resolution: {
    "shipper": {"original": "Maersk", "canonical": "MAERSK"},
    "destination": {"original": "LA", "canonical": "Los Angeles"}
  }

Stage 2 - ES Lookup:
  metadata_results: {
    "shipper_name": {"type": "keyword", "description": "Shipping line name"},
    "destination_port": {"type": "keyword", "description": "Port of discharge"}
  }

Output:
{
    "metadata_results": {...},
    "value_results": {"shipper_name": ["MAERSK"], "destination_port": ["Los Angeles"]},
    "analysis_result": {"intent_type": "search"}
}
```

## Data Flow

```
F02: Deterministic Planner
    ↓
F05: Lookup Metadata
    ↓
{ metadata_results, value_results, analysis_result }
    ↓
F13: Join Reduce
```

## State Changes

- None - stateless worker

## Error Handling

- Entity not found: Return "partial" status with available info
- Multiple matches: Return ambiguity in `analysis_result`
- LLM failure: Return `status: "failed"`

## Design Notes

- This is a critical support worker - most complex queries start here
- Performs RAG-style lookup from ES field mappings
- Outputs `analysis_result` to guide F02's routing decisions

## Registry Entry

```python
{
    "name": "metadata_lookup",
    "description": "Resolves entity names via LLM, then looks up field metadata and reference values from ES mappings",
    "preconditions": ["has entity or reference to look up"],
    "outputs": ["metadata_results", "value_results", "analysis_result"],
    "goal_type": "support"
}
```

## Integration Points

- **Input**: From F02 (fan-out)
- **Output**: To F06 (ES Query Gen), F10 (Explain Metadata), F13 (Join Reduce)
