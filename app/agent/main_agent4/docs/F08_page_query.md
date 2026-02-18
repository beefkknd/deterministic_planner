# F08: Paginate ES Query

## Overview

**Node ID**: F08
**Name**: Paginate ES Query
**Type**: Non-LLM Node (—)
**Purpose**: Handles paginated Elasticsearch queries with offset/limit

## Responsibility

1. Receive ES query with pagination parameters
2. Execute paginated query against ES
3. Return current page results
4. Indicate if more results are available
5. Calculate next offset for subsequent pages

## Input

- `es_query`: The base ES query
- `page`: Page number (1-indexed)
- `page_size`: Number of results per page

## Output

- `page_results`: Current page of results
- `has_more`: Boolean indicating more pages available
- `next_offset`: Offset for next page (null if last page)
- `total_count`: Total matching documents

## Example

```
Input:
{
    "es_query": {"query": {"match_all": {}}},
    "page": 2,
    "page_size": 20
}

Output:
{
    "page_results": [...20 records...],
    "has_more": true,
    "next_offset": 40,
    "total_count": 150
}
```

## Pagination Strategies

### Offset-based (for small datasets)
```
ES: { "from": 20, "size": 20 }
```

### Search_after (for large datasets)
```
ES: { "search_after": [last_sort_value], "size": 20 }
```

## When to Use

- User requests specific page ("show page 2")
- Large result sets that need chunking
- "Show next 20 results"
- Infinite scroll implementation

## Data Flow

```
F02: Deterministic Planner
    ↓
F08: Paginate ES Query
    ↓
{ page_results, has_more, next_offset, total_count }
    ↓
F13: Join Reduce
```

OR

```
F06: ES Query Gen
    ↓
F08: Paginate Query
    ↓
F13: Join Reduce
```

## State Changes

- None - stateless worker

## Error Handling

- Invalid page number: Return error with valid range
- Query timeout: Return partial results with warning
- Empty page: Return empty list with has_more=false

## Design Notes

- Non-LLM worker - pure query execution
- Handles both small and large dataset pagination
- Can be triggered by user request or F02 decision

## Registry Entry

```python
{
    "name": "page_query",
    "description": "Handles paginated ES queries with offset/limit",
    "preconditions": ["has es_query with pagination params"],
    "outputs": ["page_results", "has_more", "next_offset"],
    "goal_type": "support"
}
```

## Integration Points

- **Input**: From F02 (fan-out) or F06
- **Output**: To F11 (Show Results), F13 (Join Reduce)
