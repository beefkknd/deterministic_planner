"""
State and Worker Classes for Deterministic Planner Agent

This module contains all state definitions, worker DTOs, and worker registry
for the 16-node LangGraph implementation.
"""

from typing import TypedDict, Optional, Literal, Any, Annotated


# =============================================================================
# Custom Reducers
# =============================================================================

def worker_results_reducer(existing: list, update: list) -> list:
    """
    Reducer for worker_results field.

    - If update is empty (F13 returning []), clear the results.
    - Otherwise, concatenate (for Send() branches).
    """
    if not update:
        return []
    return existing + update


# =============================================================================
# TypedDict Classes (for LangGraph state)
# =============================================================================

class InputRef(TypedDict):
    """
    Dependency pointer - references output from another sub-goal.

    Used to wire outputs from one worker to inputs of another.
    """
    from_sub_goal: int  # sub_goal id
    slot: str           # output slot name


class SubGoal(TypedDict):
    """
    Task unit - represents a single unit of work to be executed.

    Each sub-goal is assigned to a worker and has inputs wired from
    other sub-goals' outputs.
    """
    id: int
    worker: str                          # node/worker name (e.g., "metadata_lookup")
    description: str                     # human-readable work instruction
    inputs: dict[str, InputRef]         # named inputs wired from other sub-goals
    params: dict[str, Any]               # additional parameters for worker
    outputs: list[str]                   # declared output slot names
    goal_type: Literal["support", "deliverable"]
    status: Literal["pending", "success", "failed"]
    result: Optional[dict[str, Any]]     # actual output values after execution
    error: Optional[str]


class WorkerInput(TypedDict):
    """
    Worker Data DTO - input passed to a worker function.

    Contains the sub-goal definition and resolved input values.
    """
    sub_goal: SubGoal
    resolved_inputs: dict[str, Any]  # hydrated from InputRefs


class WorkerResult(TypedDict):
    """
    Worker Data DTO - output returned from a worker function.

    All workers return this structure regardless of success/failure.
    """
    sub_goal_id: int
    status: Literal["success", "failed"]
    outputs: dict[str, Any]       # slot_name -> value
    error: Optional[str]          # error details if failed
    message: Optional[str]         # human-readable explanation for planner


class WorkerCapability(TypedDict):
    """
    Registry Entry - declares a worker's capabilities.

    F02 uses this registry to check preconditions before dispatching.
    F13 uses memorable_slots to decide what to write to key_artifacts.
    F14 uses synthesis_mode to decide narrative (LLM) vs display (verbatim) rendering.
    """
    name: str
    description: str
    preconditions: list[str]      # human-readable strings for F02 to evaluate
    outputs: list[str]            # output slot names this worker produces
    goal_type: Literal["support", "deliverable"]
    memorable_slots: list[str]    # subset of outputs worth storing in key_artifacts across turns; [] = nothing memorable
    synthesis_mode: Literal["narrative", "display", "hidden"]  # how F14 includes this worker's output in the final response


class AnalysisResult(TypedDict):
    """
    Result from F05 (Lookup Metadata) - guides query generation.

    Contains the intent type and entity mappings resolved by the LLM.
    """
    intent_type: Literal["search", "aggregation", "comparison"]
    entity_mappings: dict[str, str]  # original -> canonical
    confidence: float                  # 0.0 - 1.0


class AmbiguityInfo(TypedDict):
    """
    Ambiguity information from workers (F05, F06).

    F02 reads this to decide whether to clarify or proceed.
    """
    field: str
    message: str
    confidence: float
    alternatives: list[str]


class MainState(TypedDict):
    """
    Agent Internal State - accumulated across rounds, reset per turn.

    This is the primary state structure used by LangGraph.
    worker_results uses Annotated with operator.add so LangGraph
    auto-concatenates results from parallel Send() branches.
    """
    original_question: str                            # original user input (preserved from F01 restatement)
    question: str                                    # restated goal from F01
    conversation_history: Optional[list["TurnSummary"]]  # prior turns for context
    sub_goals: list[SubGoal]                          # accumulated across all rounds
    completed_outputs: dict[int, dict[str, Any]]       # sub_goal_id -> {slot: value}; id=0 is reserved for F01's pre-loaded context (user query, prior artifacts, pagination state)
    round: int                                         # current round number (1-indexed)
    max_rounds: int                                    # safety cap
    status: Literal["planning", "executing", "done", "failed"]
    messages: list[dict]                               # LangGraph message list
    final_response: str                                # assembled by F14
    planner_reasoning: str                             # F02's reasoning for current action
    synthesis_inputs: Optional[dict[str, InputRef]]    # wired refs for F14 when done
    worker_results: Annotated[list[WorkerResult], worker_results_reducer]  # accumulated by Send() branches


# =============================================================================
# TurnSummary (External - maintained by main app)
# =============================================================================

class KeyArtifact(TypedDict):
    """
    A memorable output from a worker, stored in TurnSummary for cross-turn access.

    F01 reads these to resolve pagination continuations, prior query references,
    and other cross-turn context. F13 writes them based on worker memorable_slots.

    Slot contents vary by type:
      "es_query":       {es_query, hit_count, has_more, next_offset, page_size}
      "analysis_result": {analysis_result, entity_mappings}
    """
    type: str           # "es_query" | "analysis_result"
    sub_goal_id: int
    turn_id: int
    intent: str         # human-readable description for F01 matching, e.g. "shipments from China"
    slots: dict[str, Any]  # actual data; keys depend on type (see above)


class TurnSummary(TypedDict):
    """
    External memory - maintained by main app, not agent state.

    Represents ONE turn: 1 HumanMessage + 1 AI response.
    A list of TurnSummary = chat history/memory.
    """
    turn_id: int
    human_message: str
    ai_response: str
    key_artifacts: Optional[list[KeyArtifact]]


# =============================================================================
# Helper Functions
# =============================================================================

def create_initial_state(
    question: str,
    max_rounds: int = 10,
    conversation_history: Optional[list["TurnSummary"]] = None,
) -> MainState:
    """
    Create initial state for a new agent turn.

    Args:
        question: The user's question
        max_rounds: Maximum number of planning rounds (safety cap)
        conversation_history: Optional conversation history from prior turns

    Returns:
        Initial MainState
    """
    return {
        "original_question": question,
        "question": question,
        "conversation_history": conversation_history or [],
        "sub_goals": [],
        "completed_outputs": {},
        "round": 1,
        "max_rounds": max_rounds,
        "status": "planning",
        "messages": [],
        "final_response": "",
        "planner_reasoning": "",
        "synthesis_inputs": None,
        "worker_results": [],
    }


def create_sub_goal(
    id: int,
    worker: str,
    description: str,
    goal_type: Literal["support", "deliverable"],
    inputs: Optional[dict[str, InputRef]] = None,
    params: Optional[dict[str, Any]] = None,
    outputs: Optional[list[str]] = None
) -> SubGoal:
    """
    Create a new sub-goal with default values.

    Args:
        id: Unique identifier for this sub-goal
        worker: Worker name to execute this sub-goal
        description: Human-readable task description
        goal_type: Whether this produces support data or deliverable content
        inputs: Input references from other sub-goals
        params: Additional parameters for the worker
        outputs: Declared output slot names

    Returns:
        SubGoal dict
    """
    return {
        "id": id,
        "worker": worker,
        "description": description,
        "inputs": inputs or {},
        "params": params or {},
        "outputs": outputs or [],
        "goal_type": goal_type,
        "status": "pending",
        "result": None,
        "error": None
    }


def create_worker_result(
    sub_goal_id: int,
    status: Literal["success", "failed"],
    outputs: Optional[dict[str, Any]] = None,
    error: Optional[str] = None,
    message: Optional[str] = None
) -> WorkerResult:
    """
    Create a WorkerResult with defaults.

    Args:
        sub_goal_id: ID of the sub-goal that was executed
        status: Success or failure
        outputs: Output values from the worker
        error: Error message if failed
        message: Human-readable explanation

    Returns:
        WorkerResult dict
    """
    return {
        "sub_goal_id": sub_goal_id,
        "status": status,
        "outputs": outputs or {},
        "error": error,
        "message": message
    }


def get_worker_capability(worker_name: str) -> Optional[WorkerCapability]:
    """
    Get worker capability from registry by name.

    Args:
        worker_name: Name of the worker

    Returns:
        WorkerCapability or None if not found
    """
    from app.agent.main_agent4.worker_registry import WORKER_REGISTRY
    for capability in WORKER_REGISTRY:
        if capability["name"] == worker_name:
            return capability
    return None


def get_pending_sub_goals(state: MainState) -> list[SubGoal]:
    """
    Get all pending sub-goals from the state.

    Args:
        state: Current agent state

    Returns:
        List of pending sub-goals
    """
    return [sg for sg in state["sub_goals"] if sg["status"] == "pending"]


def get_completed_deliverables(state: MainState) -> list[SubGoal]:
    """
    Get all completed deliverable sub-goals.

    Args:
        state: Current agent state

    Returns:
        List of completed deliverable sub-goals
    """
    return [
        sg for sg in state["sub_goals"]
        if sg["goal_type"] == "deliverable" and sg["status"] == "success"
    ]


def get_all_deliverables(state: MainState) -> list[SubGoal]:
    """
    Get all deliverable sub-goals (regardless of status).

    Args:
        state: Current agent state

    Returns:
        List of all deliverable sub-goals
    """
    return [
        sg for sg in state["sub_goals"]
        if sg["goal_type"] == "deliverable"
    ]
