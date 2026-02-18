"""
F07: ES Query Exec Node

Executes Elasticsearch queries. No LLM involved.
"""

from typing import Any
from app.agent.main_agent4.nodes import BaseWorker
from app.agent.main_agent4.state import WorkerInput, WorkerResult, create_worker_result
from app.agent.main_agent4.worker_registry import worker_tool
from app.agent.foundations.es_query_service import get_shipment_service


# =============================================================================
# Worker Class
# =============================================================================

class ESQueryExec(BaseWorker):
    """
    ES Query Exec Worker.

    Executes ES queries and returns raw results with hit count.
    No LLM — pure execution.
    """

    def __init__(self):
        super().__init__("es_query_exec")
        self._es_service = get_shipment_service()

    @worker_tool(
        preconditions=["has ES query"],
        outputs=["es_results", "hit_count"],
        goal_type="support",
        name="es_query_exec",
        description="Executes Elasticsearch queries"
    )
    async def ainvoke(self, worker_input: WorkerInput) -> WorkerResult:
        """
        Execute an ES query.

        Args:
            worker_input: WorkerInput with sub_goal and resolved_inputs

        Returns:
            WorkerResult with es_results and hit_count
        """
        sub_goal = worker_input["sub_goal"]
        resolved = worker_input.get("resolved_inputs", {})

        es_query = resolved.get("es_query") or sub_goal.get("params", {}).get("es_query")

        if not es_query:
            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="failed",
                error="No ES query provided"
            )

        try:
            result = await self._es_service.search(
                index="shipments",
                query=es_query
            )

            # Return raw ES response so downstream workers can parse it
            hit_count = result.get("hits", {}).get("total", {}).get("value", 0)

            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="success",
                outputs={
                    "es_results": result,  # Raw ES response dict
                    "hit_count": hit_count,
                },
                message=f"ES query returned {hit_count} hits"
            )

        except Exception as e:
            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="failed",
                error=f"ES query execution failed: {str(e)}"
            )


# =============================================================================
# Singleton
# =============================================================================

f07_es_query_exec = ESQueryExec()
