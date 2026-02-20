"""
F13: Join Reduce Node

Collects WorkerResult objects from state (accumulated by LangGraph's
Send() reducer), updates sub-goal statuses and completed_outputs,
increments round, clears worker_results, and sets status back to
"planning" for the next F02 round.

Also writes memorable outputs to key_artifacts based on worker registry.

No LLM — pure state aggregation.
"""

from typing import Any
from app.agent.main_agent4.state import (
    MainState, SubGoal, WorkerResult, KeyArtifact,
)
from app.agent.main_agent4.worker_registry import get_capability_by_name
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
        4. Write memorable outputs to key_artifacts
        5. Increment round, clear worker_results, set status to "planning"

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
                "key_artifacts": [],
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

        # Build key_artifacts from memorable_slots
        key_artifacts = self._build_key_artifacts(
            worker_results, new_sub_goals, current_round, new_completed
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
            "key_artifacts": key_artifacts,
            "planner_reasoning": (
                f"F13 (round {current_round}): "
                f"Processed {len(worker_results)} results — "
                f"{success_count} succeeded, {failed_count} failed"
            ),
        }

    def _build_key_artifacts(
        self,
        worker_results: list[WorkerResult],
        sub_goals: list[SubGoal],
        turn_id: int,
        completed_outputs: dict[int, dict[str, Any]],
    ) -> list[KeyArtifact]:
        """
        Build key_artifacts from successful worker results.

        Reads memorable_slots from worker registry and creates KeyArtifact entries.

        Args:
            worker_results: List of worker results from this round
            sub_goals: Updated sub-goals with params
            turn_id: Current turn number
            completed_outputs: Map of completed sub-goal IDs to their outputs

        Returns:
            List of KeyArtifact entries for this turn
        """
        artifacts: list[KeyArtifact] = []

        # Map sub_goal_id to params for bundling lookup
        params_by_id = {sg["id"]: sg.get("params", {}) for sg in sub_goals}

        # Map sub_goal_id to worker name
        worker_by_id = {sg["id"]: sg.get("worker") for sg in sub_goals}

        # Track F06+F07 bundles: sub_goal_id -> F06 output
        es_query_by_id: dict[int, dict[str, Any]] = {}

        # First pass: collect es_query from F06
        for result in worker_results:
            if result["status"] != "success":
                continue

            worker_name = worker_by_id.get(result["sub_goal_id"])
            if worker_name != "es_query_gen":
                continue

            outputs = result.get("outputs", {})
            if "es_query" in outputs:
                es_query_by_id[result["sub_goal_id"]] = outputs

        # Second pass: create artifacts
        for result in worker_results:
            if result["status"] != "success":
                continue

            worker_name = worker_by_id.get(result["sub_goal_id"])
            if not worker_name:
                continue

            capability = get_capability_by_name(worker_name)
            memorable = capability.get("memorable_slots", []) if capability else []

            if not memorable:
                continue

            outputs = result.get("outputs", {})
            params = params_by_id.get(result["sub_goal_id"], {})

            # Determine artifact type and intent
            if worker_name == "es_query_gen":
                # F06: es_query - will be bundled with F07
                artifact_type = "es_query"
                intent = outputs.get("intent", f"query from sub_goal {result['sub_goal_id']}")
                slots = {"es_query": outputs.get("es_query", {})}
                artifacts.append({
                    "type": artifact_type,
                    "sub_goal_id": result["sub_goal_id"],
                    "turn_id": turn_id,
                    "intent": intent,
                    "slots": slots,
                })

            elif worker_name == "es_query_exec":
                # F07: check for bundling with F06
                bundles_with = params.get("bundles_with_sub_goal")
                if bundles_with and bundles_with in es_query_by_id:
                    # Bundle with F06: add to existing artifact
                    # Find the existing artifact and merge
                    for art in artifacts:
                        if art["sub_goal_id"] == bundles_with and art["type"] == "es_query":
                            # Add F07 slots to existing
                            art["slots"]["next_offset"] = outputs.get("next_offset")
                            art["slots"]["page_size"] = outputs.get("page_size")
                            break
                    else:
                        # F06 not in this round, create standalone
                        artifact_type = "es_query"
                        intent = f"query execution from sub_goal {result['sub_goal_id']}"
                        slots = {
                            "es_query": es_query_by_id.get(bundles_with, {}).get("es_query", {}),
                            "next_offset": outputs.get("next_offset"),
                            "page_size": outputs.get("page_size"),
                        }
                        artifacts.append({
                            "type": artifact_type,
                            "sub_goal_id": result["sub_goal_id"],
                            "turn_id": turn_id,
                            "intent": intent,
                            "slots": slots,
                        })
                else:
                    # No bundling - shouldn't happen normally but handle gracefully
                    # Try to get es_query from completed_outputs if available
                    es_query = None
                    if bundles_with and bundles_with in completed_outputs:
                        es_query = completed_outputs[bundles_with].get("es_query")
                    artifact_type = "es_query"
                    intent = f"query execution from sub_goal {result['sub_goal_id']}"
                    slots = {
                        "es_query": es_query,
                        "next_offset": outputs.get("next_offset"),
                        "page_size": outputs.get("page_size"),
                    }
                    artifacts.append({
                        "type": artifact_type,
                        "sub_goal_id": result["sub_goal_id"],
                        "turn_id": turn_id,
                        "intent": intent,
                        "slots": slots,
                    })

            elif worker_name == "page_query":
                # F08: continuation - preserve es_query for next pagination
                artifact_type = "es_query"
                intent = f"pagination continuation from sub_goal {result['sub_goal_id']}"
                slots = {
                    "es_query": outputs.get("es_query"),  # Preserve for multi-page
                    "next_offset": outputs.get("next_offset"),
                    "page_size": outputs.get("page_size"),
                }
                artifacts.append({
                    "type": artifact_type,
                    "sub_goal_id": result["sub_goal_id"],
                    "turn_id": turn_id,
                    "intent": intent,
                    "slots": slots,
                })

            elif worker_name == "metadata_lookup":
                # F05: analysis_result
                artifact_type = "analysis_result"
                intent = "entity resolution"
                slots = {"analysis_result": outputs.get("analysis_result", {})}
                artifacts.append({
                    "type": artifact_type,
                    "sub_goal_id": result["sub_goal_id"],
                    "turn_id": turn_id,
                    "intent": intent,
                    "slots": slots,
                })

        return artifacts


# =============================================================================
# Singleton
# =============================================================================

f13_join_reduce = JoinReduce()
