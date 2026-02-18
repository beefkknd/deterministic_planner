# F14: Synthesizer

## Overview

**Node ID**: F14
**Name**: Synthesizer
**Type**: Non-LLM Node (—)
**Purpose**: Hydrates sub-goal outputs, assembles the final response from all worker results

## Responsibility

1. Receive synthesis_inputs (references to deliverable outputs)
2. Hydrate references from completed_outputs
3. Assemble final response from all deliverables
4. Format as single AIMessage

## Input

- `synthesis_inputs`: Dict of {slot_name: InputRef} from F02
- `completed_outputs`: All sub-goal outputs from F13
- `question`: Original user question

## Synthesis Input Example

```python
# From F02's action=done:
synthesis_inputs = {
    "faq_answer": {"from_sub_goal": "sb1", "slot": "answer"},
    "search_results": {"from_sub_goal": "sb3", "slot": "formatted_results"},
    "ambiguity_note": {"from_sub_goal": "sb4", "slot": "clarification_message"}
}
```

## Hydration Process

```python
def hydrate_refs(synthesis_inputs, completed_outputs):
    hydrated = {}
    for key, ref in synthesis_inputs.items():
        sub_goal_id = ref["from_sub_goal"]
        slot = ref["slot"]
        hydrated[key] = completed_outputs[sub_goal_id].get(slot)
    return hydrated
```

## Assembly Example

```python
# Hydrated data:
{
    "faq_answer": "A shipment is goods being transported...",
    "search_results": "| Container | Shipper | ...\n| ... ",
    "ambiguity_note": "Note: I used arrival_date — did you mean eta_date?"
}

# Final response:
"""
A shipment is goods being transported from origin to destination.

## Search Results

| Container | Shipper | Destination | Arrival |
|-----------|---------|-------------|---------|
| MSCU123 | MAERSK | Los Angeles | 2024-01-15 |

Note: I used arrival_date — did you mean eta_date?
"""
```

## Data Flow

```
F13: Join Reduce (complete)
    ↓
F14: Synthesizer
    ↓
{ final_response }
    ↓
END (AIMessage)
```

## Assembly Strategies

### Concatenation (default)
- Combine all deliverables in order
- Add separators between sections

### Priority-based
- FAQ/explanation first
- Then main results
- Then notes/warnings

### Context-aware
- Reorder based on question type
- Skip redundant information

## State Changes

- Sets `final_response` in state
- Does not modify sub-goals (read-only)

## Error Handling

- Missing output: Skip that slot, log warning
- All missing: Return "Could not generate response"

## Design Notes

- **Non-LLM** - simple template assembly
- Takes all deliverable outputs and combines
- Produces ONE AIMessage that exits the agent
- No further processing after this node

## Integration Points

- **Input**: From F13 (Join Reduce) when action=done
- **Output**: END (final AIMessage to user)
