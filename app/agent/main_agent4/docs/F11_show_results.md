# F11: Show Results

## Overview

**Node ID**: F11
**Name**: Show Results
**Type**: Non-LLM Node (—)
**Purpose**: Template-based rendering of Elasticsearch query results (no LLM, saves tokens)

## Responsibility

1. Receive ES query results
2. Apply template-based formatting
3. Render results in a user-friendly format
4. Handle various result types (search, aggregation)

## Input

- `es_results`: Raw results from ES query
- `template_type`: Optional template selection
- `columns`: Optional column specifications

## Output

- `formatted_results`: Formatted output string (markdown table, list, etc.)

## Template Types

### Table Template (default for search)
```
| Container | Shipper | Destination | Arrival |
|----------|---------|-------------|---------|
| MSCU123 | MAERSK | Los Angeles | 2024-01-15 |
| TCLU456 | EVERGREEN | New York | 2024-01-16 |
```

### Aggregation Template
```
Top 5 Shippers to Los Angeles:

1. MAERSK - 1,234 shipments
2. EVERGREEN - 987 shipments
3. MSC - 654 shipments
```

### Summary Template
```
Found 2,456 shipments matching your criteria.

Showing first 20 results:
[table]
```

## Example

```
Input:
{
    "es_results": {
        "hits": {
            "total": {"value": 2456},
            "hits": [
                {
                    "_source": {
                        "container_number": "MSCU1234567",
                        "shipper_name": "MAERSK",
                        "destination_port": "Los Angeles",
                        "arrival_date": "2024-01-15"
                    }
                }
            ]
        }
    },
    "template_type": "table"
}

Output:
{
    "formatted_results": "## Search Results\n\nFound 2,456 shipments\n\n| Container | Shipper | Destination | Arrival Date |\n|-----------|---------|-------------|--------------|\n| MSCU1234567 | MAERSK | Los Angeles | 2024-01-15 |\n\n[Showing first 20 results]"
}
```

## When to Use

- Simple result display without analysis
- When user just wants to see data
- When confidence is high (no ambiguity)
- Template rendering sufficient for user needs

## NOT Used When

- User wants comparison/trends (use F12: Analyze Results)
- Complex narrative required
- Results need interpretation

## Data Flow

```
F06/F08: ES Query
    ↓
F11: Show Results
    ↓
{ formatted_results }
    ↓
F13: Join Reduce
```

## State Changes

- None - stateless worker

## Error Handling

- Empty results: Return "No results found" message
- Malformed results: Return error with details

## Design Notes

- **Non-LLM** - uses templates only, saves tokens
- Fast and predictable output
- F02 decides between F11 (simple) vs F12 (analysis)

## Registry Entry

```python
{
    "name": "show_results",
    "description": "Template-based rendering of ES query results (no LLM)",
    "preconditions": ["has es_results to display"],
    "outputs": ["formatted_results"],
    "goal_type": "deliverable"
}
```

## Integration Points

- **Input**: From F02 (fan-out), requires F06/F08 results
- **Output**: To F13 (Join Reduce) → F14 (Synthesizer)
