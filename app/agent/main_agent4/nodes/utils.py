"""
Shared utilities for worker nodes.
"""

import json
from typing import Any, Literal, TypeVar, Type

from pydantic import BaseModel, Field


T = TypeVar("T", bound=BaseModel)


# =============================================================================
# ES Query Generation State (for F05/F06)
# =============================================================================


class ESQueryGenerationState(BaseModel):
    """
    Structured output from LLM entity extraction for ES queries.

    Used as JSON output parser to get structured entity resolution
    from the LLM.
    """

    target_index: str = Field(
        default="shipments",
        description="Elasticsearch index to query",
    )
    intent_type: Literal["search", "aggregation"] = Field(
        description="Type of query: search (bool query) or aggregation",
    )
    extracted_entities: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "List of extracted entities with resolved field names and values. "
            "Each dict should have: field_name, original_value, resolved_value, confidence"
        ),
    )
    metadata_vector_query_results: dict[str, list[dict[str, Any]]] = Field(
        default_factory=dict,
        description="Field metadata from ES mappings (field_name -> metadata)",
    )
    value_lookup_results: dict[str, list[dict[str, Any]]] = Field(
        default_factory=dict,
        description="Reference values from ES (field_name -> list of valid values)",
    )
    unresolved_entities: list[str] = Field(
        default_factory=list,
        description="Entities that could not be resolved",
    )


def parse_to_model(raw: str, model_cls: Type[T]) -> T:
    """
    Parse LLM JSON response to a Pydantic model (flexible, no validation).

    Uses model_construct() which:
    - Skips validation (flexible for LLM output)
    - Allows extra fields
    - Defaults missing optional fields to None

    Args:
        raw: Raw LLM output string
        model_cls: Pydantic BaseModel class

    Returns:
        Instance of the model with typed access
    """
    # Parse JSON, stripping markdown fences if present
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]
    parsed = json.loads(text)

    return model_cls.model_construct(**parsed)


# =============================================================================
# LLM Entity Extraction Utility
# =============================================================================

ENTITY_EXTRACTION_PROMPT = """\
You are a maritime shipping entity extractor for Elasticsearch queries.

Given a user question, extract entities and determine the query intent.

Available ES fields:
- shipper_name, consignee_name, vessel_name
- port_of_loading, port_of_discharge
- container_number, bill_of_lading_number
- carrier_name, commodity_description, hs_code
- weight_kg, volume_teu

Rules:
1. Determine if intent is "search" (filter) or "aggregation" (group/match by)
2. Extract entities and map to canonical field names
3. For each entity, estimate confidence (0.0-1.0)
4. Mark uncertain entities as unresolved

Respond with valid JSON matching the ESQueryGenerationState schema."""


ENTITY_EXTRACTION_TEMPLATE = """\
User question: {question}

Extract entities and determine intent."""


async def extract_entities_with_llm(question: str) -> ESQueryGenerationState:
    """
    Use LLM to extract entities from a question.

    This is a convenience function that uses structured output
    to parse LLM response directly into ESQueryGenerationState.

    Args:
        question: User's natural language question

    Returns:
        ESQueryGenerationState with extracted entities and intent
    """
    from app.agent.foundations.llm_service import LLMService

    llm_service = LLMService.get_instance()
    chain = llm_service.create_structured_chain(
        system_message=ENTITY_EXTRACTION_PROMPT,
        prompt_template=ENTITY_EXTRACTION_TEMPLATE,
        output_schema=ESQueryGenerationState,
    )

    result: ESQueryGenerationState = await chain.ainvoke({"question": question})
    return result


# =============================================================================
# ES Query Generation Result (for F06)
# =============================================================================


class ESQueryResult(BaseModel):
    """
    Structured output from LLM ES query generation.

    Used as JSON output parser to get structured ES query
    from the LLM.
    """

    query: dict[str, Any] = Field(
        default_factory=dict,
        description="Elasticsearch query body (bool query or aggregation)",
    )
    query_type: Literal["search", "aggregation"] = Field(
        description="Type of query generated",
    )
    ambiguity: dict[str, Any] | None = Field(
        default=None,
        description="Ambiguity info if field/value is uncertain",
    )


# =============================================================================
# LLM ES Query Generation Utility
# =============================================================================

QUERY_GEN_PROMPT = """\
You are an Elasticsearch query generator for maritime shipping data.

Given entity mappings, field metadata, and an intent type, generate an ES query JSON.

Intent types:
- "search": Generate a bool query with filters for exact matches
- "aggregation": Generate an aggregation query (terms, date_histogram, etc.)

Rules:
- Use "keyword" suffix for exact match fields (e.g., shipper_name.keyword)
- Use "match" for text search fields
- For aggregations, include a meaningful aggregation name
- Always include a size parameter for search queries

Respond with JSON matching the ESQueryResult schema."""


QUERY_GEN_TEMPLATE = """\
Intent type: {intent_type}
Entity mappings: {entity_mappings}
Field metadata: {metadata_results}
Original question: {question}

Generate the ES query."""


async def generate_es_query_with_llm(
    intent_type: str,
    entity_mappings: dict[str, str],
    metadata_results: dict[str, Any],
    question: str,
) -> ESQueryResult:
    """
    Use LLM to generate an ES query from analysis results.

    Args:
        intent_type: "search" or "aggregation"
        entity_mappings: Map of original_term -> field:value
        metadata_results: Field metadata from ES
        question: Original user question

    Returns:
        ESQueryResult with generated query and ambiguity info
    """
    from app.agent.foundations.llm_service import LLMService

    llm_service = LLMService.get_instance()
    chain = llm_service.create_structured_chain(
        system_message=QUERY_GEN_PROMPT,
        prompt_template=QUERY_GEN_TEMPLATE,
        output_schema=ESQueryResult,
    )

    result: ESQueryResult = await chain.ainvoke({
        "intent_type": intent_type,
        "entity_mappings": str(entity_mappings),
        "metadata_results": str(metadata_results),
        "question": question,
    })
    return result
