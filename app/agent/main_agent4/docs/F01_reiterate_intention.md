# F01: Reiterate Intention

## Overview

**Node ID**: F01
**Name**: Reiterate Intention
**Type**: LLM Node (🧠)
**Purpose**: Entry point that reads chat history and restates the user's intent as an executable main goal

## Responsibility

1. Receive the initial user query (HumanMessage)
2. Read conversation history (TurnSummary list from external memory)
3. Analyze the user's question to identify all intents
4. Restate the user's intent in a clear, executable format for the planner

## Input

- `user_message`: The raw HumanMessage from the user
- `conversation_history`: List[TurnSummary] from external memory (maintained by main app)

## Output

- `main_goal`: A clear, structured statement of what the user wants
- `intent_list`: List of detected intents (e.g., ["faq", "search", "comparison"])

## Behavior

### Single Intent
```
User: "Show me Maersk shipments to LA"
→ F01 Output: "Find all shipments from shipper 'Maersk' to destination 'Los Angeles'"
```

### Multi Intent
```
User: "what's shipment and find me a shipment arrived yesterday"
→ F01 Output: {
    "main_goal": "(1) Explain what a shipment is, (2) Find shipments that arrived yesterday",
    "intents": ["faq", "search"]
}
```

### With Context
```
User: "Show me Evergreen containers"
(History: previous question was about "Maersk")
→ F01 Output: "Find all shipments from 'Evergreen' (context: previous question was about Maersk)"
```

## Data Flow

```
START (HumanMessage)
    ↓
F01: Reiterate Intention
    ↓
{ main_goal, intent_list }
    ↓
F02: Deterministic Planner
```

## State Changes

- **No state modification** - This node is stateless
- Reads from external TurnSummary, does not modify agent state

## Error Handling

- If chat history is empty: Proceed with user message only
- If user message is empty: Return error to caller
- LLM failure: Return a generic "Could not process request" message

## Design Notes

- This is a lightweight LLM call - only restates intent, does not execute
- Used once per turn at the beginning
- All subsequent rounds skip F01 and go directly to F02
- The output feeds directly into F02 as the primary input

## Integration Points

- **Input**: Reads from external TurnSummary (maintained by main app)
- **Output**: Feeds into F02 (Deterministic Planner)
