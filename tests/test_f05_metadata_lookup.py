"""
Test F05 Metadata Lookup.

Tests needs_clarification flag logic:
- Clean resolution → False
- Unresolved entity → True
- Multiple matches → True
- Low confidence → True
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agent.main_agent4.nodes.f05_metadata_lookup import MetadataLookup
from app.agent.main_agent4.state import WorkerInput
from app.agent.main_agent4.nodes.utils import ESQueryGenerationState


class TestNeedsClarification:
    """Tests for needs_clarification flag in F05."""

    @pytest.fixture
    def metadata_lookup(self):
        """Create MetadataLookup instance."""
        return MetadataLookup()

    @pytest.fixture
    def base_worker_input(self):
        """Create base worker input for testing."""
        return {
            "sub_goal": {
                "id": 1,
                "worker": "metadata_lookup",
                "description": "Find shipments by shipper",
            },
            "resolved_inputs": {},
        }

    @pytest.mark.asyncio
    async def test_clean_resolution_returns_false(self, metadata_lookup, base_worker_input):
        """Clean entity resolution should set needs_clarification=False."""
        mock_query_state = ESQueryGenerationState(
            target_index="shipments",
            intent_type="search",
            extracted_entities=[
                {"field_name": "shipper_name", "original_value": "MAERSK", "resolved_value": "MAERSK", "confidence": 0.95}
            ],
            unresolved_entities=[],
        )

        with patch("app.agent.main_agent4.nodes.f05_metadata_lookup.extract_entities_with_llm", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = mock_query_state

            with patch.object(metadata_lookup._ref_list_service, "get_field_metadata", new_callable=AsyncMock) as mock_meta:
                with patch.object(metadata_lookup._ref_list_service, "get_reference_values", new_callable=AsyncMock) as mock_values:
                    # Clean resolution: single value returned
                    mock_meta.return_value = {"type": "keyword"}
                    mock_values.return_value = ["MAERSK"]

                    result = await metadata_lookup.ainvoke(base_worker_input)

        assert result["status"] == "success"
        assert result["outputs"]["needs_clarification"] is False

    @pytest.mark.asyncio
    async def test_unresolved_entity_returns_true(self, metadata_lookup, base_worker_input):
        """Unresolved entity should set needs_clarification=True."""
        mock_query_state = ESQueryGenerationState(
            target_index="shipments",
            intent_type="search",
            extracted_entities=[],
            unresolved_entities=["unknown_shipper"],
        )

        with patch("app.agent.main_agent4.nodes.f05_metadata_lookup.extract_entities_with_llm", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = mock_query_state

            with patch.object(metadata_lookup._ref_list_service, "get_field_metadata", new_callable=AsyncMock) as mock_meta:
                with patch.object(metadata_lookup._ref_list_service, "get_reference_values", new_callable=AsyncMock) as mock_values:
                    mock_meta.return_value = {}
                    mock_values.return_value = []

                    result = await metadata_lookup.ainvoke(base_worker_input)

        assert result["status"] == "success"
        assert result["outputs"]["needs_clarification"] is True

    @pytest.mark.asyncio
    async def test_multiple_matches_returns_true(self, metadata_lookup, base_worker_input):
        """Multiple matching values should set needs_clarification=True."""
        mock_query_state = ESQueryGenerationState(
            target_index="shipments",
            intent_type="search",
            extracted_entities=[
                {"field_name": "shipper_name", "original_value": "ACME", "resolved_value": "ACME", "confidence": 0.8}
            ],
            unresolved_entities=[],
        )

        with patch("app.agent.main_agent4.nodes.f05_metadata_lookup.extract_entities_with_llm", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = mock_query_state

            with patch.object(metadata_lookup._ref_list_service, "get_field_metadata", new_callable=AsyncMock) as mock_meta:
                with patch.object(metadata_lookup._ref_list_service, "get_reference_values", new_callable=AsyncMock) as mock_values:
                    # Multiple matches: list has more than one value
                    mock_meta.return_value = {"type": "keyword"}
                    mock_values.return_value = ["ACME Corp LLC", "ACME Corporation", "ACME Co"]

                    result = await metadata_lookup.ainvoke(base_worker_input)

        assert result["status"] == "success"
        assert result["outputs"]["needs_clarification"] is True

    @pytest.mark.asyncio
    async def test_low_confidence_returns_true(self, metadata_lookup, base_worker_input):
        """Low confidence (<0.7) should set needs_clarification=True."""
        mock_query_state = ESQueryGenerationState(
            target_index="shipments",
            intent_type="search",
            extracted_entities=[
                {"field_name": "shipper_name", "original_value": "some_shipper", "resolved_value": "SOME_SHIPPER", "confidence": 0.5}
            ],
            unresolved_entities=[],
        )

        with patch("app.agent.main_agent4.nodes.f05_metadata_lookup.extract_entities_with_llm", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = mock_query_state

            with patch.object(metadata_lookup._ref_list_service, "get_field_metadata", new_callable=AsyncMock) as mock_meta:
                with patch.object(metadata_lookup._ref_list_service, "get_reference_values", new_callable=AsyncMock) as mock_values:
                    mock_meta.return_value = {"type": "keyword"}
                    mock_values.return_value = ["SOME_SHIPPER"]

                    result = await metadata_lookup.ainvoke(base_worker_input)

        assert result["status"] == "success"
        assert result["outputs"]["needs_clarification"] is True

    @pytest.mark.asyncio
    async def test_boundary_confidence_at_70_is_false(self, metadata_lookup, base_worker_input):
        """Confidence exactly at 0.7 should NOT trigger clarification (threshold is < 0.7)."""
        mock_query_state = ESQueryGenerationState(
            target_index="shipments",
            intent_type="search",
            extracted_entities=[
                {"field_name": "shipper_name", "original_value": "shipper", "resolved_value": "SHIPPER", "confidence": 0.7}
            ],
            unresolved_entities=[],
        )

        with patch("app.agent.main_agent4.nodes.f05_metadata_lookup.extract_entities_with_llm", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = mock_query_state

            with patch.object(metadata_lookup._ref_list_service, "get_field_metadata", new_callable=AsyncMock) as mock_meta:
                with patch.object(metadata_lookup._ref_list_service, "get_reference_values", new_callable=AsyncMock) as mock_values:
                    mock_meta.return_value = {"type": "keyword"}
                    mock_values.return_value = ["SHIPPER"]

                    result = await metadata_lookup.ainvoke(base_worker_input)

        assert result["status"] == "success"
        assert result["outputs"]["needs_clarification"] is False

    @pytest.mark.asyncio
    async def test_single_value_not_multi_match(self, metadata_lookup, base_worker_input):
        """Single value in value_results should NOT trigger multi-match."""
        mock_query_state = ESQueryGenerationState(
            target_index="shipments",
            intent_type="search",
            extracted_entities=[
                {"field_name": "shipper_name", "original_value": "MAERSK", "resolved_value": "MAERSK", "confidence": 0.9}
            ],
            unresolved_entities=[],
        )

        with patch("app.agent.main_agent4.nodes.f05_metadata_lookup.extract_entities_with_llm", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = mock_query_state

            with patch.object(metadata_lookup._ref_list_service, "get_field_metadata", new_callable=AsyncMock) as mock_meta:
                with patch.object(metadata_lookup._ref_list_service, "get_reference_values", new_callable=AsyncMock) as mock_values:
                    mock_meta.return_value = {"type": "keyword"}
                    mock_values.return_value = ["MAERSK"]  # Single value

                    result = await metadata_lookup.ainvoke(base_worker_input)

        assert result["status"] == "success"
        assert result["outputs"]["needs_clarification"] is False
