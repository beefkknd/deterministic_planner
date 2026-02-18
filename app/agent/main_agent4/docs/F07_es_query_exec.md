# F07: ES Query Exec

## Overview

**Node ID**: F07
**Name**: ES Query Exec
**Type**: Non-LLM Node (—)
**Purpose**: Executes Elasticsearch queries (no LLM, just runs the query)

## Responsibility

1. Receive a validated ES query
2. Execute against Elasticsearch
3. Return raw results
4. Report hit count and execution status

## Input

- `es_query`: The ES query dict to execute
- `params`: Optional query parameters

## Output

- `es_results`: Raw ES response (includes hits, aggregations, etc.)
- `hit_count`: Total number of hits returned

## Implementation Notes

- No LLM — pure ES query execution
- Returns raw ES response dict so downstream workers can parse it
- Uses ESShipmentService.search() for execution
