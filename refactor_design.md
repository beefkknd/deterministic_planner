# Refactor Design: Query Management, Context Normalization, and Synthesis

## Design Goals

1. **Shield F02** from query origin complexity — F02 plans against clean normalized state only
2. **Normalize all ES query origins** through a single pipeline before planning begins
3. **Formalize key_artifacts** as a structured cross-turn memory store
4. **Clarify F07/F08 responsibility split** around pagination semantics
5. **Split F14 synthesis** into narrative (LLM) and display (verbatim) phases

---

## Domain 1: Three Origins of ES Queries

### Problem

ES queries enter the system from three different sources, each with a different lifecycle. Mixing these without a clear normalization pipeline causes F02 to reason about provenance instead of intent.

| Origin | Example Trigger | Where It Lives |
|--------|----------------|----------------|
| **Agent-generated** | "Find shipments from China" | `completed_outputs[N]["es_query"]` (current turn) |
| **User-provided** | User pastes raw JSON query | Raw text in `HumanMessage` |
| **Historical** | "Why did your last query..." / "show more" | `TurnSummary.key_artifacts` (prior turn) |

### Solution: Normalize Everything Through completed_outputs[0]

All three origins must be normalized into `completed_outputs[0]` by F01 before F02 runs. F01 owns a synthetic sub-goal (id=0) that represents "pre-loaded context for this turn." F02 wires InputRefs against `from_sub_goal: 0` exactly like any other sub-goal. F02 never knows or cares about origin.

```
completed_outputs[0] = {
    "user_es_query":    <extracted from HumanMessage if present>,
    "prior_agent_query": <retrieved from key_artifacts if referenced>,
    "next_offset":      <retrieved from key_artifacts if pagination continuation>,
    "has_more":         <from key_artifacts, used to validate pagination is possible>,
    "page_size":        <from key_artifacts or default>,
}
```

Only the slots relevant to the current turn are populated. Empty slots are not written.

---

## Domain 2: F01 as Context Normalizer — The Shield Pattern

### Principle

**F01's job: normalize context. F02's job: plan against normalized context.**

Anything that requires understanding *what the user is referring to* belongs in F01. Anything that requires *deciding what to do about it* belongs in F02.

### F01 Detection Responsibilities

F01 must detect and handle three categories of contextual references:

**Category A — User-Provided Query**
- Signals: raw JSON in the message body, code blocks containing ES query syntax
- Action: extract and write to `completed_outputs[0]["user_es_query"]`

**Category B — Reference to Prior Agent Query**
- Signals: "your query", "your last query", "why did that query", "the query you ran"
- Action: find matching entry in `key_artifacts`, write to `completed_outputs[0]["prior_agent_query"]`

**Category C — Pagination Continuation**
- Signals: "show more", "next page", "load more", "next 10", "keep going"
- Action: find matching entry in `key_artifacts`, write `{es_query, next_offset, has_more, page_size}` to `completed_outputs[0]`

### Multi-Intent Disambiguation

When multiple prior queries exist in `key_artifacts` and the user says "show more" without specifying which, F01 must resolve the ambiguity:
- If only one query has `has_more: true` → use it unambiguously
- If multiple queries have `has_more: true` → write a disambiguation signal to state; F02 dispatches F09 to ask the user which they meant
- If the referenced query has `has_more: false` → write a "no_more_results" signal; F02 can plan a clarification

### Explicit Size (Same-Turn, No F01 Intervention)

"Show me 50 shipments from China" — this is NOT a cross-turn reference. F01 does not intercept it. F02 puts `size: 50` in the F06 sub-goal's `params`. F01 only intercepts cross-turn contextual references.

### Testability Benefit

F01 is fully testable in isolation:
```
Input:  (HumanMessage, list[TurnSummary])
Output: completed_outputs[0] dict + restated intent string
```
No graph execution required. Covers all three query origin cases independently.

### Extensibility (F01_1 Pattern)

If F01 grows too large, split into a pipeline:
- `F01_a`: Intent restatement (current responsibility)
- `F01_b`: Context extraction (query origins, artifact retrieval, pagination detection)

F02 still receives the same clean normalized state. The split is internal to the pre-planning phase.

---

## Domain 3: key_artifacts — Structured Cross-Turn Memory

### Principle

Each worker node knows best what it produced that has long-term value. The worker **declares candidacy** via `memorable_slots` in its registry entry. F13 **handles storage** after each round.

### Worker Registry Extension

Add `memorable_slots: list[str]` to each worker's registry entry. Only slots listed here are written to `key_artifacts`.

| Worker | memorable_slots | Rationale |
|--------|----------------|-----------|
| F05 metadata_lookup | `["analysis_result"]` | Entity resolutions reusable next turn |
| F06 es_query_gen | `["es_query"]` | Query referenceable cross-turn |
| F07 es_query_exec | `["hit_count", "has_more"]` | Summary stats + pagination signal |
| F08 page_query | `["next_offset", "has_more", "page_size"]` | Continuation state |
| F04, F09, F10, F11, F12 | `[]` | Deliverable outputs are ephemeral |

### key_artifacts Entry Schema

Each entry written by F13:

```
{
    "type":         "es_query" | "analysis_result" | "pagination_state",
    "sub_goal_id":  int,
    "turn_id":      int,
    "intent":       str,   ← human-readable description for F01 to match against
    "slots": {
        "es_query":     {...},
        "hit_count":    142,
        "has_more":     true,
        "next_offset":  10,
        "page_size":    10,
    }
}
```

The `intent` field is critical — F01 uses it to match "show me more" against the right prior query when multiple entries exist.

### F13 Storage Logic

After each round, for each completed WorkerResult:
1. Look up the worker's `memorable_slots` in the registry
2. If non-empty, construct a `key_artifacts` entry from `WorkerResult.outputs`
3. Append to the current turn's `TurnSummary.key_artifacts` list

F13 does NOT decide what's memorable — the registry declares it. F13 is mechanical.

---

## Domain 4: Pagination — F07 vs F08 Responsibility Split

### Core Distinction

| Node | Semantics | Stateful? | from/size source |
|------|-----------|-----------|-----------------|
| F07 | First-page execution | No | Injects defaults: `from=0, size=N` at runtime |
| F08 | Continuation execution | Yes | Takes `next_offset` via InputRef |

### F06 Stays Clean

F06 generates logical queries only — no pagination params. `from` and `size` are an execution concern, not a query logic concern.

### Default from/size

Defaults live in F07's configuration (not in the query, not in F06). F07 always injects `from=0, size=<configured_default>` before executing. This makes F07 the single source of truth for first-page behavior.

### F02 Dispatch Decision

F02 chooses between F07 and F08 based purely on slot availability in state — no special pagination awareness required:
- `next_offset` NOT in `completed_outputs[0]` → dispatch F07 (first page)
- `next_offset` IS in `completed_outputs[0]` → dispatch F08 (continuation)

F02 does not understand pagination. It just sees whether a slot is available.

### Pagination Flow Across Turns

```
Turn 1: "Find shipments from China"
  F01: no pagination signal → completed_outputs[0] empty
  F06 → F07 (injects from=0, size=10) → F11
  F13: stores to key_artifacts:
       {intent: "shipments from China", es_query: {...}, hit_count: 142, has_more: true, next_offset: 10}

Turn 2: "Show me more"
  F01: detects "show more"
  F01: finds matching key_artifacts entry (has_more=true)
  F01: writes to completed_outputs[0]:
       {es_query: <prior_query>, next_offset: 10, has_more: true, page_size: 10}
  F02: sees next_offset available → dispatches F08
  F08: executes with from=10, size=10 → F11
  F13: updates key_artifacts: next_offset=20, has_more=true/false
```

### Enhancement Note: Merging F07 and F08 (Future Work)

F07 and F08 are the same operation with different `from` values. They could be merged into a single `es_query_exec` node:
- If `from` param not provided → default to 0 (current F07 behavior)
- If `from` param provided → use it (current F08 behavior)

**Benefits**: One fewer node in the graph, simpler registry, cleaner F03 dispatch.

**Risk**: Loses the explicit semantic distinction between "first page" and "continuation" — which is useful for F13's key_artifacts storage logic (F07 creates a new entry, F08 updates an existing one).

**Recommendation**: Defer until the rest of this refactor stabilizes. The F07/F08 split is low-risk and the semantic distinction is valuable for key_artifacts management.

---

## Domain 5: Synthesizer Split — Narrative vs Display

### Problem

F11 (Show Results) produces large formatted markdown tables. Including these in F14's LLM synthesis prompt wastes tokens and risks overflow. But they must appear in the final response.

### Solution: synthesis_mode Flag

Add `synthesis_mode` to SubGoal (and worker registry default):

| Mode | Meaning | F14 behavior |
|------|---------|-------------|
| `narrative` | Produces prose for LLM synthesis | Include output text in synthesis prompt |
| `display` | Produces structured data for direct display | Append verbatim AFTER synthesized prose |
| `hidden` | Support only, never in final response | Excluded from F14 entirely |

### Worker synthesis_mode Defaults

| Worker | synthesis_mode | Rationale |
|--------|---------------|-----------|
| F04 common_helpdesk | `narrative` | FAQ answer is prose |
| F09 clarify_question | `narrative` | Clarification is prose |
| F10 explain_metadata | `narrative` | Explanation is prose |
| F12 analyze_results | `narrative` | Analysis is prose |
| F11 show_results | `display` | Table/list, too large for LLM prompt |
| F05, F06, F07, F08 | `hidden` | Support nodes, not user-facing |

### F14 Two-Phase Synthesis

**Phase 1 — LLM Synthesis (narrative deliverables only):**
Collect all `narrative` sub-goal outputs. Pass them to LLM with synthesis prompt. LLM weaves into a coherent story: "A shipment is [FAQ answer]. Based on your query, [analysis]..."

**Phase 2 — Direct Append (display deliverables):**
Append all `display` sub-goal outputs verbatim after the prose. No LLM involved.

**Result:** "A shipment is goods being transported... Here are the shipments from Shanghai:\n\n| Shipper | Arrival | ... |"

---

## Node-by-Node Todo List

### F01 — Reiterate Intention

- [ ] **Detect user-provided ES query**: scan HumanMessage for raw JSON / code blocks that look like ES queries; extract into `completed_outputs[0]["user_es_query"]`
- [ ] **Detect prior-query references**: recognize phrases ("your query", "your last query", "the query you ran"); match against `key_artifacts` by type and recency; write to `completed_outputs[0]["prior_agent_query"]`
- [ ] **Detect pagination continuation**: recognize phrases ("show more", "next page", "load more", "next N", "keep going"); look up matching `key_artifacts` entry
    - If `has_more: true`: write `{es_query, next_offset, has_more, page_size}` to `completed_outputs[0]`
    - If `has_more: false`: write `{pagination_exhausted: true}` signal to state
    - If multiple `has_more: true` entries: write disambiguation signal
- [ ] **Pre-populate completed_outputs[0]** as the synthetic context sub-goal (id=0); only write slots that are actually detected/retrieved
- [ ] **Pass TurnSummary.key_artifacts** into F01's context so it can retrieve prior artifacts; define which fields of key_artifacts are summarized vs passed in full
- [ ] **Update F01 prompt** to cover all three detection categories with examples
- [ ] **Unit tests**: `(message, history) → completed_outputs[0]` for all detection cases including multi-intent disambiguation edge cases

---

### F02 — Deterministic Planner

- [ ] **No origin-aware changes** — F02 must remain shielded from query provenance
- [ ] **Declare sub-goal bundling**: when creating a F07 sub-goal, set `params["bundles_with_sub_goal"] = <F06_sub_goal_id>` so F13 knows to merge their key_artifacts entries into one
- [ ] **Use completed_outputs[0]** for InputRef wiring exactly like any other sub-goal; document that id=0 is the F01 context slot
- [ ] **Dispatch F08 vs F07**: F02's planning logic naturally chooses based on slot availability — verify this works without special-casing pagination
- [ ] **Explicit size params**: when user specifies "50 results", F02 puts `size: 50` in F06's sub-goal `params` (not a cross-turn concern, not F01's job)
- [ ] **Pagination exhausted handling**: if `completed_outputs[0]["pagination_exhausted"]` is set, F02 should dispatch F09 (clarify) explaining no more results available
- [ ] **Update F02 prompt** to document that id=0 represents pre-loaded context from F01 (not a real worker sub-goal)

---

### F05 — Lookup Metadata

- [ ] **Add to registry**: `memorable_slots: ["analysis_result"]`
- [ ] **Verify intent description**: F13 will write `intent` to key_artifacts; ensure F05's output includes a human-readable description of what was resolved (e.g., "Maersk shipper, Los Angeles port, Q4 date range")

---

### F06 — ES Query Gen

- [ ] **Remove pagination params from generated queries**: F06 must NOT include `from` or `size` in the ES query body — these are F07/F08's responsibility
- [ ] **Add to registry**: `memorable_slots: ["es_query"]`
- [ ] **Include intent description in output**: add an `intent` field to F06's output (e.g., "aggregation: shipping volumes by carrier to LA Q4") for key_artifacts storage
- [ ] **Accept explicit size via params**: if F02 passes `size` in sub-goal params (user said "50 results"), F06 can pass it through as a hint — but NOT embed it in the query body; pass it as a separate output slot `{"requested_size": 50}`

---

### F07 — ES Query Exec

- [ ] **Inject default pagination at execution time**: add `from=0, size=<configured_default>` to the query before executing; do NOT expect F06 to provide these
- [ ] **Configurable default size**: read from node config or environment variable; do not hardcode
- [ ] **Output `has_more`**: compare `hit_count` vs `size` returned; if ES total hits > `offset + size`, set `has_more: true`
- [ ] **Output `next_offset`**: always output `next_offset = 0 + size` (i.e., the offset for the next page) even if `has_more: false`
- [ ] **Add to registry**: `memorable_slots: ["hit_count", "has_more", "next_offset"]`
- [ ] **F13 key_artifacts integration**: F13 will bundle F07's memorable slots with F06's `es_query` and `intent` into a single key_artifacts entry (cross-slot bundling logic needed in F13)

---

### F08 — Paginate ES Query

- [ ] **Take `next_offset` via InputRef**: input is `{es_query: InputRef, next_offset: InputRef, page_size: InputRef}`; all three should come from `completed_outputs[0]` (written by F01 from key_artifacts)
- [ ] **Execute with provided offset**: apply `from=next_offset, size=page_size` to the query at execution time
- [ ] **Output `has_more`**: same logic as F07
- [ ] **Output `next_offset`**: `next_offset + page_size` for the next potential page
- [ ] **Add to registry**: `memorable_slots: ["next_offset", "has_more", "page_size"]`
- [ ] **F13 key_artifacts integration**: F13 should UPDATE the existing key_artifacts entry (matched by es_query hash or sub_goal lineage) rather than creating a new one

---

### F11 — Show Results

- [ ] **Add `synthesis_mode: "display"` to registry** (or sub-goal default)
- [ ] **Add `memorable_slots: []`** — display output is ephemeral
- [ ] **No other changes** — F11 itself is unchanged; the change is in how F14 treats its output

---

### F12 — Analyze Results

- [ ] **Add `synthesis_mode: "narrative"` to registry**
- [ ] **Add `memorable_slots: []`** — analysis prose is ephemeral

---

### F13 — Join Reduce

- [ ] **Read `memorable_slots` from worker registry** for each completed WorkerResult
- [ ] **Write memorable outputs to `TurnSummary.key_artifacts`**:
    - For F06 + F07 (query generation + first execution): bundle into one key_artifacts entry
    - For F08 (pagination continuation): update existing entry (match by `es_query` content hash or sub_goal lineage chain)
    - For F05: write analysis_result as its own entry type
- [ ] **Include intent description** in every key_artifacts entry; source from F06's `intent` output or F05's description
- [ ] **Include metadata**: `{sub_goal_id, turn_id, timestamp}` on every entry
- [ ] **Bundling logic**: define how F13 combines outputs from multiple sub-goals into a single key_artifacts entry (e.g., F06 es_query + F07 hit_count + F07 has_more → one "query execution" artifact)

---

### F14 — Synthesizer

- [ ] **Split synthesis into two phases**:
    - Phase 1: collect all sub-goals where `synthesis_mode == "narrative"`; pass their outputs to LLM synthesis prompt
    - Phase 2: collect all sub-goals where `synthesis_mode == "display"`; append their `formatted_results` verbatim after LLM prose
- [ ] **Do NOT include `show_results` formatted output in LLM prompt** — this is the key change; currently F14 may be passing everything to the LLM
- [ ] **Ordering**: narrative prose first, display results appended after; if multiple display results, order by sub-goal id
- [ ] **synthesis_inputs**: F02's `synthesis_inputs` dict already controls which sub-goals go to F14; add a second dict or extend InputRef with `synthesis_mode` so F14 knows how to handle each
- [ ] **Edge case**: if only `display` deliverables exist (no narrative), F14 skips LLM phase and appends directly with a minimal header

---

### State Schema Changes

- [ ] **SubGoal**: add `synthesis_mode: Literal["narrative", "display", "hidden"] = "hidden"`
- [ ] **Worker registry entry**: add `memorable_slots: list[str]` and `synthesis_mode: str`
- [ ] **TurnSummary.key_artifacts**: define as `list[KeyArtifact]` with schema above; currently may be unstructured
- [ ] **MainState**: document that `completed_outputs[0]` is reserved for F01's synthetic context sub-goal
- [ ] **WorkerCapability**: add `memorable_slots` and `synthesis_mode` fields to the dataclass

---

## Resolved Design Decisions

1. **F13 bundling** ✅ — F02 declares the linkage at planning time. When F02 creates the F07 sub-goal, it sets a `bundles_with_sub_goal: <F06_id>` param. F13 reads this and merges F07's memorable slots into F06's existing key_artifacts entry. No inference needed, fully testable.

2. **key_artifacts size limit** ✅ — Controlled by TurnSummary window size at the app level. F01 and F13 do not prune. The window caps how far back key_artifacts history goes.

3. **F01 context window** ✅ — Same as above. TurnSummary windowing is the control. F01 receives whatever key_artifacts are present in the windowed history.

4. **Disambiguation** ✅ — Latest entry in chat history has higher priority. F01 picks the most recent matching key_artifacts entry. If still ambiguous, user can elaborate in follow-up and F01 re-resolves on the next turn. No F09 dispatch needed for this case.
