# F04: Common Helpdesk

## Overview

**Node ID**: F04
**Name**: Common Helpdesk
**Type**: LLM Node (🧠)
**Purpose**: Answers FAQ and general assistance questions

## Responsibility

1. Identify if the user's query is a common/general question
2. Provide accurate, helpful answers to FAQs
3. Handle general assistance requests (greetings, help, explanations)

## Input

- `user_query`: The original user question
- `resolved_inputs`: Empty (no dependencies - this is often a first-step worker)

## Output

- `answer`: The FAQ answer or assistance response

## Example Triggers

- "What is a shipment?"
- "How do I search for containers?"
- "What data do you have?"
- "Can you help me?"

## NOT Triggered For

- Specific data queries ("Show me Maersk shipments")
- Complex analytical questions ("Compare volumes")
- Entity-specific requests

## Data Flow

```
F02: Deterministic Planner
    ↓
F04: Common Helpdesk
    ↓
{ answer }
    ↓
F13: Join Reduce
```

## Behavior Examples

### FAQ Question
```
Input: "what's shipment"
Output: {
    "answer": "A shipment is goods being transported from an origin
               port to a destination port. It typically includes information
               about the container, shipper, consignee, and transit details."
}
```

### General Assistance
```
Input: "can you help me find data"
Output: {
    "answer": "I can help you find shipping data. You can ask me things like:
               - Show me shipments to Los Angeles
               - What are the top shippers to NYC?
               - Find containers from Maersk"
}
```

## State Changes

- None - stateless worker

## Error Handling

- If query is not an FAQ: Return message indicating this is not a help question
- LLM failure: Return `status: "failed"` with error message

## Design Notes

- Lightweight - just answers straightforward questions
- No data fetching required
- Often runs in parallel with F05 (metadata_lookup) for multi-intent queries

## Registry Entry

```python
{
    "name": "common_helpdesk",
    "description": "Answers FAQ and general assistance questions",
    "preconditions": ["user query is a common/general question"],
    "outputs": ["answer"],
    "goal_type": "deliverable"
}
```

## Integration Points

- **Input**: From F02 (fan-out)
- **Output**: To F13 (Join Reduce)
