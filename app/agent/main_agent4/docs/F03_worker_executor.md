# F03: Worker Executor

## Overview

**Node ID**: F03
**Name**: Worker Executor
**Type**: Non-LLM Node (—)
**Purpose**: Dispatches to the correct worker based on sub_goal["worker"]

## Responsibility

1. Receive WorkerInput via LangGraph Send() from the routing edge
2. Look up the correct worker from WORKER_MAP by worker name
3. Invoke the worker with the WorkerInput
4. Wrap the result in {"worker_results": [result]} for the reducer

## Implementation

The routing logic (checking sub-goal readiness, hydrating inputs) lives in graph.py as `route_after_planner` - a conditional edge function. F03 is the actual node that executes workers.

```python
# In f03_worker_executor.py
WORKER_MAP = {
    "common_helpdesk": f04_common_helpdesk,
    "metadata_lookup": f05_metadata_lookup,
    "es_query_gen": f06_es_query_gen,
    "es_query_exec": f07_es_query_exec,
    "page_query": f08_page_query,
    "clarify_question": f09_clarify_question,
    "explain_metadata": f10_explain_metadata,
    "show_results": f11_show_results,
    "analyze_results": f12_analyze_results,
}

async def ainvoke(self, worker_input: WorkerInput) -> dict:
    worker = WORKER_MAP[worker_input["sub_goal"]["worker"]]
    result = await worker.ainvoke(worker_input)
    return {"worker_results": [result]}
```

## Key Point

F03 receives WorkerInput directly (not MainState) because Send() passes the payload directly to the node.
