# Node Design Documents Index

This directory contains detailed design documents for each node in the Deterministic Planner architecture.

## Current Node Implementation

| ID | Node | Type | Purpose | goal_type |
|----|------|------|---------|-----------|
| F01 | Reiterate Intention | 🧠 LLM | Entry point - reads chat history, restates user intent | - |
| F02 | Deterministic Planner | 🧠 LLM | Central orchestrator - plans sub-goals, decides continue/done/failed | - |
| F03 | Worker Executor | ⚙️ Non-LLM | Dispatches to correct worker based on sub_goal["worker"] | - |
| F04 | Common Helpdesk | 🧠 LLM | Answers FAQ and general assistance questions | deliverable |
| F05 | Lookup Metadata | 🧠 LLM | Entity resolution + field metadata lookup from ES | support |
| F06 | ES Query Gen | 🧠 LLM | Generates ES search/aggregation queries | support |
| F07 | ES Query Exec | ⚙️ Non-LLM | Executes Elasticsearch queries | support |
| F08 | Page Query | ⚙️ Non-LLM | Handles paginated ES queries | support |
| F09 | Clarify Question | 🧠 LLM | Generates clarification messages for ambiguity | deliverable |
| F10 | Explain Metadata | 🧠 LLM | Explains field mappings to users | deliverable |
| F11 | Show Results | ⚙️ Non-LLM | Template-based result rendering | deliverable |
| F12 | Analyze Results | 🧠 LLM | Deep LLM analysis (comparisons, trends) | deliverable |
| F13 | Join Reduce | ⚙️ Non-LLM | Collects worker results, routes to next step | - |
| F14 | Synthesizer | ⚙️ Non-LLM | Assembles final response from deliverables | - |

**Note:** F15 and F16 were planned but not implemented.

## Flow Diagram

```mermaid
flowchart RL
    START(("START")) --> F01["F01: Reiterate Intention"]
    F01 --> F02["F02: Deterministic Planner"]

    F02 -- Send --> F04["F04: Common Helpdesk"]
    F02 -- Send --> F05["F05: Lookup Metadata"]
    F02 -- Send --> F06["F06: ES Query Gen"]
    F02 -- Send --> F07["F07: ES Query Exec"]
    F02 -- Send --> F08["F08: Page Query"]
    F02 -- Send --> F09["F09: Clarify Question"]
    F02 -- Send --> F10["F10: Explain Metadata"]
    F02 -- Send --> F11["F11: Show Results"]
    F02 -- Send --> F12["F12: Analyze Results"]

    F04 --> F13[F13: Join Reduce]
    F05 --> F13
    F06 --> F13
    F07 --> F13
    F08 --> F13
    F09 --> F13
    F10 --> F13
    F11 --> F13
    F12 --> F13

    F13 -- incomplete --> F02
    F13 -- complete --> F14[F14: Synthesizer]
    F14 --> END(("END"))
```

## Node Categories

### Entry/Exit Nodes
- **F01**: Reiterate Intention - Entry point
- **F14**: Synthesizer - Exit point (final response)

### Orchestration Nodes
- **F02**: Deterministic Planner - Central brain
- **F03**: Worker Executor - Dispatches to workers
- **F13**: Join Reduce - Collection point

### Support Workers (produce intermediate data)
- **F05**: Lookup Metadata
- **F06**: ES Query Gen
- **F07**: ES Query Exec
- **F08**: Page Query

### Deliverable Workers (produce user-facing content)
- **F04**: Common Helpdesk
- **F09**: Clarify Question
- **F10**: Explain Metadata
- **F11**: Show Results
- **F12**: Analyze Results

## LLM vs Non-LLM Distribution

| Type | Count | Nodes |
|------|-------|-------|
| 🧠 LLM | 8 | F01, F02, F04, F05, F06, F09, F10, F12 |
| ⚙️ Non-LLM | 6 | F03, F07, F08, F11, F13, F14 |

## goal_type Distribution

| Type | Meaning | Nodes |
|------|---------|-------|
| support | Intermediate data for other workers | F05, F06, F07, F08 |
| deliverable | User-facing content | F04, F09, F10, F11, F12 |

## Document Files

1. [F01_reiterate_intention.md](F01_reiterate_intention.md)
2. [F02_deterministic_planner.md](F02_deterministic_planner.md)
3. [F03_worker_executor.md](F03_worker_executor.md)
4. [F04_common_helpdesk.md](F04_common_helpdesk.md)
5. [F05_lookup_metadata.md](F05_lookup_metadata.md)
6. [F06_es_query_gen.md](F06_es_query_gen.md)
7. [F07_es_query_exec.md](F07_es_query_exec.md)
8. [F08_page_query.md](F08_page_query.md)
9. [F09_clarify_question.md](F09_clarify_question.md)
10. [F10_explain_metadata.md](F10_explain_metadata.md)
11. [F11_show_results.md](F11_show_results.md)
12. [F12_analyze_results.md](F12_analyze_results.md)
13. [F13_join_reduce.md](F13_join_reduce.md)
14. [F14_synthesizer.md](F14_synthesizer.md)
