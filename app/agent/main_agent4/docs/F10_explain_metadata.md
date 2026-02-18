# F10: Explain Metadata

## Overview

**Node ID**: F10
**Name**: Explain Metadata
**Type**: LLM Node (🧠)
**Purpose**: Explains mapping fields and data structure to the user

## Responsibility

1. Receive metadata_results from F05
2. Generate human-readable explanations of data fields
3. Explain data types, formats, and available values
4. Help users understand what data is available

## Input

- `metadata_results`: Field definitions from ES mappings
- `field_list`: Optional specific fields to explain

## Output

- `explanation`: Markdown formatted explanation of fields/data

## Example

```
Input:
{
    "metadata_results": {
        "shipper_name": {
            "type": "keyword",
            "description": "Name of the shipping line"
        },
        "container_number": {
            "type": "keyword",
            "description": "Unique container identifier"
        },
        "arrival_date": {
            "type": "date",
            "format": "yyyy-MM-dd",
            "description": "Date of arrival at destination"
        }
    }
}

Output:
{
    "explanation": "## Available Data Fields\n\n### Shipper Information\n- **shipper_name**: The shipping line name (e.g., MAERSK, Evergreen)\n- **shipper_code**: 3-letter carrier code\n\n### Container Details\n- **container_number**: Unique container ID (e.g., MSCU1234567)\n- **container_size**: 20ft or 40ft\n\n### Dates\n- **arrival_date**: Format: YYYY-MM-DD\n- **departure_date**: Format: YYYY-MM-DD\n- **eta_date**: Estimated arrival"
}
```

## Use Cases

- User asks "what fields do you have?"
- User asks "what does field X mean?"
- F02 detects user wants to understand available data
- Debugging: "why can't I find field X?"

## Trigger Patterns

- "What data do you have?"
- "Explain the fields"
- "What does arrival_date mean?"
- "Show me available filters"

## Data Flow

```
F05: Lookup Metadata
    ↓
F02: Deterministic Planner
    ↓
F10: Explain Metadata
    ↓
{ explanation }
    ↓
F13: Join Reduce
```

## State Changes

- None - stateless worker

## Error Handling

- No metadata: Return "No field information available"
- LLM failure: Return `status: "failed"`

## Design Notes

- Educational - helps users write better queries
- Can be triggered proactively or on request
- Output is deliverable (goes to final response)

## Registry Entry

```python
{
    "name": "explain_metadata",
    "description": "Explains mapping fields and data structure to the user",
    "preconditions": ["has metadata_results to explain"],
    "outputs": ["explanation"],
    "goal_type": "deliverable"
}
```

## Integration Points

- **Input**: From F02 (fan-out), requires F05 metadata_results
- **Output**: To F13 (Join Reduce) → F14 (Synthesizer)
