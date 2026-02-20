"""
F08: Paginate ES Query Node

Handles paginated ES queries with offset/limit. No LLM involved.
"""

from typing import Any
from app.agent.main_agent4.nodes import BaseWorker
from app.agent.main_agent4.state import WorkerInput, WorkerResult, create_worker_result
from app.agent.main_agent4.worker_registry import worker_tool
from app.agent.foundations.es_query_service import get_shipment_service


# =============================================================================
# Constants
# =============================================================================

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


# =============================================================================
# Worker Class
# =============================================================================

class PageQuery(BaseWorker):
    """
    Paginate ES Query Worker.

    Executes ES queries with offset/limit pagination.
    No LLM — pure execution with pagination metadata.
    """

    def __init__(self):
        super().__init__("page_query")
        self._es_service = get_shipment_service()

    @worker_tool(
        preconditions=["prior_es_query is available in context (user referenced prior results or requested next page)"],
        outputs=["page_results", "next_offset", "page_size", "es_query"],
        goal_type="support",
        name="page_query",
        description="Handles paginated ES queries with offset/limit",
        memorable_slots=["es_query", "next_offset", "page_size"],
        synthesis_mode="hidden",
    )
    async def ainvoke(self, worker_input: WorkerInput) -> WorkerResult:
        """
        Execute a paginated ES query.

        Args:
            worker_input: WorkerInput with sub_goal and resolved_inputs

        Returns:
            WorkerResult with page_results, next_offset, page_size, es_query
        """
        sub_goal = worker_input["sub_goal"]
        resolved = worker_input.get("resolved_inputs", {})
        params = sub_goal.get("params", {})

        es_query = resolved.get("es_query") or params.get("es_query")
        index = params.get("index", "shipments")
        # Read pagination values from resolved_inputs (via InputRef) or params fallback
        offset = int(resolved.get("offset", params.get("offset", 0)))
        limit = min(int(resolved.get("limit", params.get("limit", DEFAULT_PAGE_SIZE))), MAX_PAGE_SIZE)

        if not es_query:
            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="failed",
                error="No ES query provided for pagination"
            )

        try:
            result = await self._es_service.search(
                index=index,
                query=es_query,
                size=limit,
                from_=offset
            )

            hits = result.get("hits", {})
            total = hits.get("total", {}).get("value", 0)
            page_results = hits.get("hits", [])
            next_offset = offset + limit

            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="success",
                outputs={
                    "page_results": page_results,
                    "next_offset": next_offset,
                    "page_size": limit,
                    "es_query": es_query,  # Echo back for artifact preservation
                },
                message=f"Page returned {len(page_results)} of {total} total hits"
            )

        except Exception as e:
            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="failed",
                error=f"Paginated ES query failed: {str(e)}"
            )


# =============================================================================
# Singleton
# =============================================================================

f08_page_query = PageQuery()
