"""
LangGraph Topology

Defines the node graph for the Deterministic Planner agent.

Flow:
  F01 (reiterate) → F02 (planner) → [conditional edge: fan_out]
                                              ├── Send("f03_worker_executor", ...) × N (parallel)
                                              ├── "f14_synthesizer" (if done)
                                              └── END (if failed)

  f03_worker_executor (×N parallel) → f13_join_reduce → F02 (loop back)
"""

from typing import Union
from langgraph.graph import StateGraph, END
from langgraph.types import Send

from app.agent.main_agent4.logging_config import get_logger
from app.agent.main_agent4.state import MainState, SubGoal, WorkerInput, get_pending_sub_goals

logger = get_logger("graph")


# =============================================================================
# Import Nodes
# =============================================================================

from app.agent.main_agent4.nodes.f01_reiterate_intention import f01_reiterate
from app.agent.main_agent4.nodes.f02_deterministic_planner import f02_planner
from app.agent.main_agent4.nodes.f03_worker_executor import f03_worker_executor
from app.agent.main_agent4.nodes.f13_join_reduce import f13_join_reduce
from app.agent.main_agent4.nodes.f14_synthesizer import f14_synthesizer


# =============================================================================
# Fan-Out Routing Logic (Conditional Edge Function)
# =============================================================================

def _is_sub_goal_ready(sub_goal: SubGoal, state: MainState) -> bool:
    """
    Check if all InputRefs for a sub-goal are satisfied.

    A sub-goal is ready when every input it declares has its
    source sub-goal completed and the referenced slot present
    in completed_outputs.
    """
    completed_outputs = state.get("completed_outputs", {})
    inputs = sub_goal.get("inputs", {})

    for _input_name, input_ref in inputs.items():
        from_id = input_ref["from_sub_goal"]
        slot = input_ref["slot"]

        if from_id not in completed_outputs:
            return False

        if slot not in completed_outputs[from_id]:
            return False

    return True


def _hydrate_worker_input(sub_goal: SubGoal, state: MainState) -> WorkerInput:
    """
    Hydrate the input for a worker by resolving InputRefs from
    completed_outputs in the main state.
    """
    completed_outputs = state.get("completed_outputs", {})
    inputs = sub_goal.get("inputs", {})

    resolved_inputs = {}
    for input_name, input_ref in inputs.items():
        from_id = input_ref["from_sub_goal"]
        slot = input_ref["slot"]
        resolved_inputs[input_name] = completed_outputs[from_id][slot]

    return {
        "sub_goal": sub_goal,
        "resolved_inputs": resolved_inputs,
    }


def route_after_planner(state: MainState) -> Union[list[Send], str]:
    """
    Conditional edge function after F02.

    Checks which pending sub-goals have all inputs satisfied,
    hydrates their WorkerInput, and returns Send() objects for parallel
    dispatch. Routes to synthesizer or end when not executing.

    This is used with add_conditional_edges - it returns:
    - A list of Send() objects for parallel fan-out
    - A string node name for sequential flow (synthesizer or END)
    """
    status = state.get("status", "failed")
    round_num = state.get("round", "?")

    if status == "executing":
        pending = get_pending_sub_goals(state)
        if not pending:
            logger.info(f"[R{round_num}] No pending sub-goals, routing to F13")
            return "f13_join_reduce"

        ready_count = 0
        blocked_count = 0
        sends = []
        for sg in pending:
            if _is_sub_goal_ready(sg, state):
                ready_count += 1
                worker_input = _hydrate_worker_input(sg, state)
                sends.append(Send("f03_worker_executor", worker_input))
            else:
                blocked_count += 1

        if not sends:
            logger.info(f"[R{round_num}] All {blocked_count} sub-goals blocked, routing to F13")
            return "f13_join_reduce"

        logger.info(f"[R{round_num}] Dispatching {len(sends)} sub-goals ({ready_count} ready, {blocked_count} blocked)")
        return sends

    elif status == "done":
        logger.info(f"[R{round_num}] Status=done, routing to synthesizer")
        return "f14_synthesizer"

    else:
        logger.info(f"[R{round_num}] Status={status}, routing to END")
        return END


# =============================================================================
# Build Graph
# =============================================================================

def create_graph() -> StateGraph:
    """
    Create and configure the LangGraph for the Deterministic Planner.

    Returns:
        Compiled StateGraph ready for invocation
    """
    graph = StateGraph(MainState)

    # Add nodes - pass async functions directly (LangGraph handles them correctly)
    graph.add_node("f01_reiterate", f01_reiterate.ainvoke)
    graph.add_node("f02_planner", f02_planner.ainvoke)
    # Note: f03_worker_executor receives WorkerInput via Send(), not MainState
    graph.add_node("f03_worker_executor", f03_worker_executor.ainvoke)
    graph.add_node("f13_join_reduce", f13_join_reduce.ainvoke)
    graph.add_node("f14_synthesizer", f14_synthesizer.ainvoke)

    # Add edges
    graph.add_edge("__start__", "f01_reiterate")
    graph.add_edge("f01_reiterate", "f02_planner")

    # Conditional edge: fan-out after planner
    # route_after_planner returns:
    #   - list[Send] for parallel fan-out (status="executing" with ready sub-goals)
    #   - END constant for failed/blocked/no pending
    #   - "f14_synthesizer" string when done
    graph.add_conditional_edges("f02_planner", route_after_planner)

    # Worker executor → join reduce (parallel branches converge here)
    graph.add_edge("f03_worker_executor", "f13_join_reduce")

    # Join reduce → planner (loop back for next round)
    graph.add_edge("f13_join_reduce", "f02_planner")

    # Synthesizer → END
    graph.add_edge("f14_synthesizer", END)

    # Compile
    return graph.compile()


# =============================================================================
# Singleton
# =============================================================================

graph = create_graph()
