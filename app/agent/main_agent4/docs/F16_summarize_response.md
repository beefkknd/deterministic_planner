# F16: Summarize Response

## Overview

**Node ID**: F16
**Name**: Summarize Response
**Type**: LLM Node (🧠)
**Purpose**: Creates a concise summary of the final response for specific use cases

## Responsibility

1. Receive the full response assembled by F14
2. Generate a concise summary
3. Optionally create alternative formats (bullet points, highlights)
4. Provide different views for different contexts

## Input

- `full_response`: Complete response from F14
- `summary_type`: "brief" | "bullet" | "key_points" | "executive"
- `max_length`: Optional character limit

## Output

- `summary`: Condensed version of the response

## Summary Types

### Brief Summary
```
Full: [Long detailed response about shipping data...]
Summary: "Found 1,234 Maersk shipments to Los Angeles in Q4 2023."
```

### Bullet Points
```
Full: [Analysis comparing carriers...]
Bullets:
- Maersk: 55% market share (1,234 shipments)
- Evergreen: 30% (672 shipments)
- MSC: 15% (336 shipments)
```

### Key Points
```
Full: [Complex analysis with trends...]
Key Points:
- Maersk dominates LA route with 55% share
- Q4 showed 12% growth YoY
- Transit times improved by 2 days average
```

### Executive Summary
```
Full: [Detailed quarterly report...]
Executive: "Maersk leads with 55% share; Q4 growth strong at 12%"
```

## Use Cases

- Chat interfaces with limited space
- Notifications/alerts with summaries
- Mobile views
- Email digests
- Voice assistants

## Data Flow

```
F14: Synthesizer
    ↓
F16: Summarize Response (optional)
    ↓
{ summary }
    ↓
END (AIMessage with summary option)
```

## Optional Node

F16 is **optional** - can be triggered when:
- User explicitly asks for summary
- Response length exceeds threshold
- Channel requires brevity (SMS, push notification)
- Voice interface request

## Decision to Summarize

```
Response length > threshold?
    │
    ├─ Yes → Include summary option
    │
    └─ No → Skip F16, use full response
```

## State Changes

- None - stateless worker

## Error Handling

- LLM failure: Return full response (no summary)
- Empty response: Return empty summary

## Design Notes

- LLM-powered for intelligent summarization
- Preserves key information while reducing length
- Different summary types for different contexts
- Can provide both full + summary in response

## Integration Points

- **Input**: From F14 (Synthesizer) - optional
- **Output**: END (AIMessage to user)
