# F09: Clarify Question

## Overview

**Node ID**: F09
**Name**: Clarify Question
**Type**: LLM Node (🧠)
**Purpose**: Generates a markdown clarification message when planner detects ambiguity

## Responsibility

1. Receive ambiguity details from workers (F05, F06)
2. Generate a clear, user-friendly clarification question
3. Format as markdown for display
4. Enable the system to proceed without human interruption

## Input

- `ambiguity`: Details about what's ambiguous
  - `field`: Which field is ambiguous
  - `options`: Possible values/interpretations
  - `confidence`: System confidence level
- `context`: Additional context for generating question

## Output

- `clarification_message`: Markdown formatted question for user

## Trigger Conditions

F02 sends to F09 when:
1. F05 returns multiple entity matches
2. F06 returns field ambiguity
3. F07 finds conflicting data interpretations
4. System confidence < threshold

## Example - Entity Ambiguity

```
Input:
{
    "ambiguity": {
        "type": "entity",
        "field": "shipper",
        "options": ["ACME Corp LLC", "ACME Corporation", "ACME Co"],
        "original": "Acme Corp"
    }
}

Output:
{
    "clarification_message": "## Clarification Needed\n\nI found multiple matches for 'Acme Corp':\n\n1. **ACME Corp LLC**\n2. **ACME Corporation**\n3. **ACME Co**\n\nWhich one did you mean?"
}
```

## Example - Field Ambiguity

```
Input:
{
    "ambiguity": {
        "type": "field",
        "field": "date",
        "options": ["arrival_date", "eta_date", "departure_date"],
        "confidence": 0.6,
        "context": "user asked about 'arrived yesterday'"
    }
}

Output:
{
    "clarification_message": "## Clarification Needed\n\nI'm not certain which date you mean:\n\n- **Arrival Date**: When the container arrived at port\n- **ETA (Estimated Arrival)**: Expected arrival date\n- **Departure Date**: When the container left the origin port\n\nWhich date type is relevant to your query?"
}
```

## Data Flow

```
F05/F06: Returns ambiguity
    ↓
F02: Deterministic Planner (detects ambiguity)
    ↓
F09: Clarify Question
    ↓
{ clarification_message }
    ↓
F13: Join Reduce
    ↓
F02: action=done → F14: Synthesizer
```

## Key Behavior

- **No human pause** - F09 generates clarification as part of response
- **Next turn** - User answers clarification in their next message
- **Preserves context** - F01 reads history to understand user answered clarification

## State Changes

- None - stateless worker

## Error Handling

- No ambiguity details: Return generic question
- LLM failure: Return `status: "failed"`

## Design Notes

- Critical for uncertainty handling - allows graceful recovery
- Generated message is conversational, not technical
- F02 decides conservative (F09) vs eager (F11) path

## Registry Entry

```python
{
    "name": "clarify_question",
    "description": "Generates a markdown clarification message when planner detects ambiguity",
    "preconditions": ["planner identified ambiguity requiring clarification"],
    "outputs": ["clarification_message"],
    "goal_type": "deliverable"
}
```

## Integration Points

- **Input**: From F02 (fan-out), triggered by ambiguity from F05/F06
- **Output**: To F13 (Join Reduce) → F14 (Synthesizer)
