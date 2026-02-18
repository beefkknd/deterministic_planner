"""
F13: Join Reduce Node

Collects WorkerResult objects from state (accumulated by LangGraph's
Send() reducer), updates sub-goal statuses and completed_outputs,
increments round, clears worker_results, and sets status back to
"planning" for the next F02 round.

No LLM — pure state aggregation.
"""

from typing import Any
from app.agent.main_agent4.state import (
    MainState, SubGoal, WorkerResult,
)
from app.agent.main_agent4.logging_config import get_logger

logger = get_logger("f13_join")


# =============================================================================
# Node Class
# =============================================================================

class JoinReduce:
    """
    F13: Join Reduce.

    Reduce phase of the Map/Reduce pattern. Reads worker_results
    from state (accumulated by LangGraph's operator.add reducer),
    updates sub-goals and completed_outputs, prepares for next round.
    """

    async def ainvoke(self, state: MainState) -> MainState:
        """
        Process worker results and prepare state for the next planning round.

        1. Read worker_results from state
        2. Update each sub-goal's status/result/error
        3. Store successful outputs in completed_outputs
        4. Increment round, clear worker_results, set status to "planning"

        Args:
            state: Current MainState with worker_results accumulated

        Returns:
            New MainState ready for the next F02 round
        """
        worker_results = state.get("worker_results", [])
        current_round = state.get("round", 1)

        logger.info(f"F13: Joining {len(worker_results)} worker results")

        if not worker_results:
            logger.info(f"F13: No worker results, incrementing round to {current_round + 1}")
            return {
                **state,
                "round": current_round + 1,
                "status": "planning",
                "worker_results": [],
                "planner_reasoning": (
                    f"F13 (round {current_round}): "
                    "No worker results received"
                ),
            }

        # Index results by sub_goal_id
        results_by_id = {r["sub_goal_id"]: r for r in worker_results}

        # Update sub-goals with results (immutable — build new list)
        new_sub_goals = []
        for sg in state.get("sub_goals", []):
            result = results_by_id.get(sg["id"])
            if result is not None:
                new_sub_goals.append({
                    **sg,
                    "status": result["status"],
                    "result": result.get("outputs", {}),
                    "error": result.get("error"),
                })
            else:
                new_sub_goals.append(sg)

        # Store successful outputs for next round's InputRef resolution
        new_completed = {**state.get("completed_outputs", {})}
        for result in worker_results:
            if result["status"] == "success":
                new_completed[result["sub_goal_id"]] = result.get(
                    "outputs", {}
                )

        success_count = sum(
            1 for r in worker_results if r["status"] == "success"
        )
        failed_count = len(worker_results) - success_count

        logger.info(f"F13: Round {current_round} complete - {success_count} succeeded, {failed_count} failed. Moving to round {current_round + 1}")

        return {
            **state,
            "sub_goals": new_sub_goals,
            "completed_outputs": new_completed,
            "round": current_round + 1,
            "status": "planning",
            "worker_results": [],
            "planner_reasoning": (
                f"F13 (round {current_round}): "
                f"Processed {len(worker_results)} results — "
                f"{success_count} succeeded, {failed_count} failed"
            ),
        }


# =============================================================================
# Singleton
# =============================================================================

f13_join_reduce = JoinReduce()
