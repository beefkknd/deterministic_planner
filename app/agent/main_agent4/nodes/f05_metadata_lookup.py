"""
F05: Lookup Metadata Node

Resolves entity names via LLM (structured output), then looks up field metadata
and reference values from ES mappings.
"""

import asyncio
from typing import Any

from app.agent.main_agent4.nodes import BaseWorker
from app.agent.main_agent4.nodes.utils import ESQueryGenerationState, extract_entities_with_llm
from app.agent.main_agent4.state import (
    WorkerInput, WorkerResult, AnalysisResult,
    create_worker_result,
)
from app.agent.main_agent4.worker_registry import worker_tool
from app.agent.foundations.es_query_service import get_ref_list_service


# =============================================================================
# Worker Class
# =============================================================================


class MetadataLookup(BaseWorker):
    """
    Metadata Lookup Worker.

    Uses LLM with structured output to resolve entity names, then looks up
    field metadata and reference values from ES mappings.
    """

    def __init__(self):
        super().__init__("metadata_lookup")
        self._ref_list_service = get_ref_list_service()

    async def _lookup_field_metadata(
        self, extracted_entities: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Look up field metadata from ES for resolved entities.

        Args:
            extracted_entities: List of entity dicts with field_name

        Returns:
            Dict of field_name -> metadata
        """
        metadata = {}
        for entity in extracted_entities:
            field_name = entity.get("field_name")
            if field_name and field_name not in metadata:
                field_meta = await self._ref_list_service.get_field_metadata(
                    index="shipments", field_name=field_name
                )
                metadata[field_name] = field_meta

        return metadata

    async def _lookup_reference_values(
        self, extracted_entities: list[dict[str, Any]]
    ) -> dict[str, list[str]]:
        """
        Look up reference values for resolved entities.

        Args:
            extracted_entities: List of entity dicts with field_name and resolved_value

        Returns:
            Dict of field_name -> list of reference values
        """
        value_results = {}
        for entity in extracted_entities:
            field_name = entity.get("field_name")
            resolved_value = entity.get("resolved_value")

            if field_name and field_name not in value_results:
                # Use resolved_value as prefix for lookup
                values = await self._ref_list_service.get_reference_values(
                    index="shipments",
                    field_name=field_name,
                    prefix=resolved_value,
                )
                value_results[field_name] = values

        return value_results

    @worker_tool(
        preconditions=["has entity or reference to look up"],
        outputs=["metadata_results", "value_results", "analysis_result"],
        goal_type="support",
        name="metadata_lookup",
        description="Resolves entity names via LLM, then looks up field metadata and reference values from ES mappings",
        memorable_slots=["analysis_result"],
        synthesis_mode="hidden",
    )
    async def ainvoke(self, worker_input: WorkerInput) -> WorkerResult:
        """
        Execute metadata lookup.

        Args:
            worker_input: WorkerInput with sub_goal and resolved_inputs

        Returns:
            WorkerResult with metadata_results, value_results, analysis_result
        """
        sub_goal = worker_input["sub_goal"]

        # sub_goal["description"] contains the work instruction from F02
        question = sub_goal.get("description", "")

        if not question:
            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="failed",
                error="No question provided for metadata lookup",
            )

        try:
            # Step 1: LLM entity resolution with structured output
            query_state: ESQueryGenerationState = await extract_entities_with_llm(question)

            intent_type = query_state.intent_type or "search"
            extracted_entities = query_state.extracted_entities or []
            unresolved_entities = query_state.unresolved_entities or []

            # Convert extracted_entities to entity_mappings for analysis_result
            entity_mappings = {}
            for entity in extracted_entities:
                original = entity.get("original_value", "")
                field = entity.get("field_name", "")
                resolved = entity.get("resolved_value", "")
                if original and field:
                    entity_mappings[original] = f"{field}:{resolved}"

            confidence = sum(
                e.get("confidence", 0.5) for e in extracted_entities
            ) / len(extracted_entities) if extracted_entities else 0.5

            # Step 2 & 3: Look up field metadata and reference values in parallel
            metadata_results, value_results = await asyncio.gather(
                self._lookup_field_metadata(extracted_entities),
                self._lookup_reference_values(extracted_entities),
            )

            # Build analysis result
            analysis_result: AnalysisResult = {
                "intent_type": intent_type,
                "entity_mappings": entity_mappings,
                "confidence": confidence,
            }

            outputs: dict[str, Any] = {
                "metadata_results": metadata_results,
                "value_results": value_results,
                "analysis_result": analysis_result,
            }

            # Attach unresolved entities if any
            if unresolved_entities:
                outputs["unresolved_entities"] = unresolved_entities

            entity_count = len(entity_mappings)
            unresolved_count = len(unresolved_entities)
            message = f"Resolved {entity_count} entities with {intent_type} intent"
            if unresolved_count > 0:
                message += f" ({unresolved_count} unresolved)"

            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="success",
                outputs=outputs,
                message=message,
            )

        except Exception as e:
            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="failed",
                error=f"Metadata lookup failed: {str(e)}",
            )


# =============================================================================
# Instantiate for export
# =============================================================================

f05_metadata_lookup = MetadataLookup()
