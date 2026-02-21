"""
F06: ES Query Gen Node

Generates search or aggregation ES queries based on analysis_result.intent_type.
Uses structured output for reliable JSON parsing.
"""

from typing import Any

from app.agent.main_agent4.nodes import BaseWorker
from app.agent.main_agent4.nodes.utils import ESQueryResult, generate_es_query_with_llm
from app.agent.main_agent4.state import WorkerInput, WorkerResult, create_worker_result
from app.agent.main_agent4.worker_registry import worker_tool


# =============================================================================
# Worker Class
# =============================================================================


class ESQueryGen(BaseWorker):
    """
    ES Query Gen Worker.

    Uses LLM with structured output to generate ES query JSON based on
    intent and entity mappings.
    """

    def __init__(self):
        super().__init__("es_query_gen")

    @worker_tool(
        preconditions=[
            "has metadata_results from metadata_lookup",
            "has analysis_result with intent_type",
            "needs_clarification=False from metadata_lookup",
        ],
        outputs=["es_query", "intent", "query_summary", "ambiguity", "needs_clarification"],
        goal_type="support",
        name="es_query_gen",
        description="Generates search or aggregation ES query based on analysis_result.intent_type; signals needs_clarification if query cannot reliably cover user intent",
        memorable_slots=["es_query"],
        synthesis_mode="hidden",
    )
    async def ainvoke(self, worker_input: WorkerInput) -> WorkerResult:
        """
        Generate an ES query from metadata and analysis result.

        Args:
            worker_input: WorkerInput with sub_goal and resolved_inputs

        Returns:
            WorkerResult with es_query and optional ambiguity
        """
        sub_goal = worker_input["sub_goal"]
        resolved = worker_input.get("resolved_inputs", {})

        analysis_result = resolved.get("analysis_result", {})
        metadata_results = resolved.get("metadata_results", {})
        # sub_goal["description"] contains the work instruction from F02
        question = sub_goal.get("description", "")

        intent_type = analysis_result.get("intent_type", "search")
        entity_mappings = analysis_result.get("entity_mappings", {})

        if not entity_mappings and not question:
            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="failed",
                error="No entity mappings or question provided for query generation",
            )

        try:
            # Use structured output - no manual JSON parsing needed
            query_result: ESQueryResult = await generate_es_query_with_llm(
                intent_type=intent_type,
                entity_mappings=entity_mappings,
                metadata_results=metadata_results,
                question=question,
            )

            es_query = query_result.query or {}
            ambiguity = query_result.ambiguity

            # Build intent description for key_artifacts storage
            intent_parts = []
            if entity_mappings:
                for orig, canon in entity_mappings.items():
                    intent_parts.append(f"{canon}")
            if intent_type == "aggregation":
                intent_description = f"aggregation: {', '.join(intent_parts) or question}"
            else:
                intent_description = f"{', '.join(intent_parts) or question}"

            outputs: dict[str, Any] = {
                "es_query": es_query,
                "intent": intent_description,
                "needs_clarification": query_result.needs_clarification,
            }
            if query_result.query_summary:
                outputs["query_summary"] = query_result.query_summary
            if ambiguity:
                outputs["ambiguity"] = ambiguity

            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="success",
                outputs=outputs,
                message=f"Generated {query_result.query_type or intent_type} ES query",
            )

        except Exception as e:
            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="failed",
                error=f"ES query generation failed: {str(e)}",
            )


# =============================================================================
# Instantiate for export
# =============================================================================

f06_es_query_gen = ESQueryGen()
