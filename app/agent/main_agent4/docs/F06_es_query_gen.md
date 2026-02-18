# F06: ES Query Gen

## Overview

**Node ID**: F06
**Name**: ES Query Gen
**Type**: LLM Node (🧠)
**Purpose**: Generates Elasticsearch search or aggregation queries based on analysis_result

## Responsibility

1. Receive metadata and intent_type from F05
2. Generate a valid ES query (search or aggregation)
3. Detect and report field ambiguity
4. Handle uncertainty by returning confidence levels

## Input

- `metadata_results`: Field metadata from F05
- `analysis_result`: { intent_type, entity_mappings }
- `resolved_inputs`: Hydrated from F05 outputs

## Output

- `es_query`: The generated Elasticsearch query (dict)
- `ambiguity`: Optional warning about field ambiguity

## Query Types

### Search Query
```python
{
    "query": {
        "bool": {
            "must": [
                {"term": {"shipper_name": "MAERSK"}},
                {"term": {"destination_port": "Los Angeles"}}
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
            "terms": {"field": "shipper_name", "size": 10}
        }
    }
}
```

## Ambiguity Handling

When F06 is uncertain about which field to use:

```
Input: "shipments arrived yesterday"

Analysis:
  - Possible fields: arrival_date, eta_date, departure_date
  - LLM 60% confident on arrival_date

Output:
{
    "es_query": {"query": {"term": {"arrival_date": "2024-01-15"}}},
    "ambiguity": {
        "message": "Using arrival_date with 60% confidence",
        "alternatives": ["eta_date", "departure_date"]
    }
}
```

This ambiguity is read by F02 to decide:
- **Conservative**: Send to F09 (clarify_question)
- **Eager**: Proceed to F11 (show_results)

## Data Flow

```
F05: Lookup Metadata
    ↓
F02: Deterministic Planner (checks preconditions)
    ↓
F06: ES Query Gen
    ↓
{ es_query, ambiguity }
    ↓
F13: Join Reduce
```

## State Changes

- None - stateless worker

## Error Handling

- Invalid query generated: Return `status: "failed"` with details
- No matching fields: Return `status: "failed"` with explanation
- LLM failure: Return `status: "failed"`

## Design Notes

- This is the core query generation engine
- Must output valid ES DSL (Domain Specific Language)
- Ambiguity reporting is critical for uncertainty handling
- Works closely with F05 (metadata_lookup) input

## Registry Entry

```python
{
    "name": "es_query_gen",
    "description": "Generates search or aggregation ES query based on analysis_result.intent_type; reports field ambiguity if uncertain",
    "preconditions": ["has metadata_results from metadata_lookup", "has analysis_result with intent_type"],
    "outputs": ["es_query", "ambiguity"],
    "goal_type": "support"
}
```

## Integration Points

- **Input**: From F02 (fan-out), requires F05 metadata_results
- **Output**: To F07 (SQL Exec), F08 (Paginate Query), F13 (Join Reduce)
