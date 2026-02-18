"""
F03: Worker Executor Node

Receives WorkerInput via LangGraph Send() and dispatches to the correct
worker based on sub_goal["worker"]. Returns {"worker_results": [result]}
so the reducer can concatenate across parallel branches.

This is the target node for Send() calls from the fan-out edge.
"""

from typing import Any

from app.agent.main_agent4.state import WorkerInput, WorkerResult
from app.agent.main_agent4.logging_config import get_logger

logger = get_logger("f03_executor")


# =============================================================================
# Worker Map
# =============================================================================

# Map worker name -> worker instance
# Import all workers to ensure they're registered in WORKER_REGISTRY
from app.agent.main_agent4.nodes.f04_common_helpdesk import f04_common_helpdesk
from app.agent.main_agent4.nodes.f05_metadata_lookup import f05_metadata_lookup
from app.agent.main_agent4.nodes.f06_es_query_gen import f06_es_query_gen
from app.agent.main_agent4.nodes.f07_es_query_exec import f07_es_query_exec
from app.agent.main_agent4.nodes.f08_page_query import f08_page_query
from app.agent.main_agent4.nodes.f09_clarify_question import f09_clarify_question
from app.agent.main_agent4.nodes.f10_explain_metadata import f10_explain_metadata
from app.agent.main_agent4.nodes.f11_show_results import f11_show_results
from app.agent.main_agent4.nodes.f12_analyze_results import f12_analyze_results

WORKER_MAP: dict[str, Any] = {
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


# =============================================================================
# Node Class
# =============================================================================

class WorkerExecutor:
    """
    F03: Worker Executor.

    Receives WorkerInput (via Send() payload), looks up the correct worker
    by name, invokes it, and wraps the result in the worker_results format.
    """

    async def ainvoke(self, worker_input: WorkerInput) -> dict[str, Any]:
        """
        Execute the appropriate worker for the given sub-goal.

        This node is the target of Send() calls from the fan-out edge.
        It receives WorkerInput directly (not MainState) because Send()
        passes the second argument as the payload.

        Args:
            worker_input: WorkerInput with sub_goal and resolved_inputs

        Returns:
            Partial state dict with worker_results list containing one result
        """
        sub_goal = worker_input["sub_goal"]
        worker_name = sub_goal.get("worker", "")
        sub_goal_id = sub_goal.get("id", -1)

        logger.info(f"F03: Executing sub-goal {sub_goal_id} -> {worker_name}")

        if not worker_name:
            logger.error(f"F03: Sub-goal {sub_goal_id} has no worker specified")
            return {
                "worker_results": [{
                    "sub_goal_id": sub_goal_id,
                    "status": "failed",
                    "outputs": {},
                    "error": "No worker specified in sub_goal",
                    "message": None,
                }]
            }

        worker = WORKER_MAP.get(worker_name)
        if not worker:
            logger.error(f"F03: Unknown worker '{worker_name}' for sub-goal {sub_goal_id}")
            return {
                "worker_results": [{
                    "sub_goal_id": sub_goal_id,
                    "status": "failed",
                    "outputs": {},
                    "error": f"Unknown worker: {worker_name}",
                    "message": None,
                }]
            }

        try:
            result: WorkerResult = await worker.ainvoke(worker_input)
            if result["status"] == "success":
                logger.info(f"F03: Sub-goal {sub_goal_id} SUCCEEDED - {result.get('message', '')}")
            else:
                logger.error(f"F03: Sub-goal {sub_goal_id} FAILED - {result.get('error', 'unknown')}")
            return {"worker_results": [result]}
        except Exception as e:
            return {
                "worker_results": [{
                    "sub_goal_id": sub_goal.get("id", -1),
                    "status": "failed",
                    "outputs": {},
                    "error": f"Worker execution failed: {str(e)}",
                    "message": None,
                }]
            }


# =============================================================================
# Singleton
# =============================================================================

f03_worker_executor = WorkerExecutor()
