"""
Test F06 ES Query Gen.

Tests needs_clarification flag logic:
- Clean query → False
- No field match → True
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.agent.main_agent4.nodes.f06_es_query_gen import ESQueryGen
from app.agent.main_agent4.state import WorkerInput
from app.agent.main_agent4.nodes.utils import ESQueryResult


class TestNeedsClarification:
    """Tests for needs_clarification flag in F06."""

    @pytest.fixture
    def es_query_gen(self):
        """Create ESQueryGen instance."""
        return ESQueryGen()

    @pytest.fixture
    def base_worker_input(self):
        """Create base worker input for testing."""
        return {
            "sub_goal": {
                "id": 1,
                "worker": "es_query_gen",
                "description": "Find shipments by shipper",
            },
            "resolved_inputs": {
                "analysis_result": {
                    "intent_type": "search",
                    "entity_mappings": {"MAERSK": "shipper_name:MAERSK"},
                },
                "metadata_results": {"shipper_name": {"type": "keyword"}},
            },
        }

    @pytest.mark.asyncio
    async def test_clean_query_returns_false(self, es_query_gen, base_worker_input):
        """Clean query generation should set needs_clarification=False."""
        mock_query_result = ESQueryResult(
            query={"query": {"bool": {"must": [{"term": {"shipper_name.keyword": "MAERSK"}}]}}},
            query_type="search",
            query_summary="Generated a bool query filtering on shipper_name=MAERSK.",
            ambiguity=None,
            needs_clarification=False,
        )

        with patch("app.agent.main_agent4.nodes.f06_es_query_gen.generate_es_query_with_llm", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_query_result

            result = await es_query_gen.ainvoke(base_worker_input)

        assert result["status"] == "success"
        assert result["outputs"]["needs_clarification"] is False
        assert result["outputs"]["es_query"] is not None

    @pytest.mark.asyncio
    async def test_no_field_match_returns_true(self, es_query_gen, base_worker_input):
        """No matching field should set needs_clarification=True."""
        mock_query_result = ESQueryResult(
            query={"query": {"term": {"consignee_name.keyword": "ACME"}}},
            query_type="search",
            query_summary="Generated a term query on consignee_name. User mentioned 'owner' which has no direct field match.",
            ambiguity={
                "field": "owner",
                "message": "No matching field for 'owner'",
                "alternatives": ["consignee_name", "shipper_name"],
                "confidence": 0.5,
            },
            needs_clarification=True,
        )

        with patch("app.agent.main_agent4.nodes.f06_es_query_gen.generate_es_query_with_llm", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_query_result

            result = await es_query_gen.ainvoke(base_worker_input)

        assert result["status"] == "success"
        assert result["outputs"]["needs_clarification"] is True
        assert result["outputs"]["ambiguity"] is not None

    @pytest.mark.asyncio
    async def test_field_uncertainty_returns_true(self, es_query_gen, base_worker_input):
        """High field uncertainty should set needs_clarification=True."""
        mock_query_result = ESQueryResult(
            query={"query": {"term": {"arrival_date": "2024-01-15"}}},
            query_type="search",
            query_summary="Used arrival_date as best guess. User may have meant eta_date or departure_date.",
            ambiguity={
                "field": "date",
                "message": "Uncertain which date field user means",
                "alternatives": ["arrival_date", "eta_date", "departure_date"],
                "confidence": 0.4,
            },
            needs_clarification=True,
        )

        with patch("app.agent.main_agent4.nodes.f06_es_query_gen.generate_es_query_with_llm", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_query_result

            result = await es_query_gen.ainvoke(base_worker_input)

        assert result["status"] == "success"
        assert result["outputs"]["needs_clarification"] is True

    @pytest.mark.asyncio
    async def test_preserves_query_summary(self, es_query_gen, base_worker_input):
        """query_summary should be preserved in outputs."""
        mock_query_result = ESQueryResult(
            query={"query": {"bool": {"must": [{"term": {"shipper_name.keyword": "MAERSK"}}]}}},
            query_type="search",
            query_summary="Generated a bool query filtering on shipper_name=MAERSK.",
            ambiguity=None,
            needs_clarification=False,
        )

        with patch("app.agent.main_agent4.nodes.f06_es_query_gen.generate_es_query_with_llm", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_query_result

            result = await es_query_gen.ainvoke(base_worker_input)

        assert result["status"] == "success"
        assert "query_summary" in result["outputs"]
        assert result["outputs"]["query_summary"] == "Generated a bool query filtering on shipper_name=MAERSK."

    @pytest.mark.asyncio
    async def test_preserves_ambiguity_when_present(self, es_query_gen, base_worker_input):
        """ambiguity should be preserved in outputs when present."""
        mock_query_result = ESQueryResult(
            query={"query": {"term": {"some_field": "value"}}},
            query_type="search",
            query_summary="Generated query with ambiguity.",
            ambiguity={"field": "date", "message": "unclear", "alternatives": ["a", "b"], "confidence": 0.5},
            needs_clarification=True,
        )

        with patch("app.agent.main_agent4.nodes.f06_es_query_gen.generate_es_query_with_llm", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_query_result

            result = await es_query_gen.ainvoke(base_worker_input)

        assert result["status"] == "success"
        assert "ambiguity" in result["outputs"]
        assert result["outputs"]["ambiguity"]["field"] == "date"

    @pytest.mark.asyncio
    async def test_query_summary_none_not_in_outputs(self, es_query_gen, base_worker_input):
        """When query_summary is None, the key should be absent from outputs (not None value)."""
        mock_query_result = ESQueryResult(
            query={"query": {"bool": {"must": [{"term": {"shipper_name.keyword": "MAERSK"}}]}}},
            query_type="search",
            query_summary=None,  # Explicitly None
            ambiguity=None,
            needs_clarification=False,
        )

        with patch("app.agent.main_agent4.nodes.f06_es_query_gen.generate_es_query_with_llm", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_query_result

            result = await es_query_gen.ainvoke(base_worker_input)

        assert result["status"] == "success"
        # query_summary should NOT be in outputs when None
        assert "query_summary" not in result["outputs"]

    @pytest.mark.asyncio
    async def test_needs_clarification_true_without_ambiguity(self, es_query_gen, base_worker_input):
        """needs_clarification=True can be set without ambiguity — they are independent."""
        mock_query_result = ESQueryResult(
            query={"query": {"term": {"shipper_name.keyword": "SOME_SHIPPER"}}},
            query_type="search",
            query_summary="Generated query but user may want different field.",
            ambiguity=None,  # No structured ambiguity
            needs_clarification=True,  # But still needs clarification
        )

        with patch("app.agent.main_agent4.nodes.f06_es_query_gen.generate_es_query_with_llm", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_query_result

            result = await es_query_gen.ainvoke(base_worker_input)

        assert result["status"] == "success"
        assert result["outputs"]["needs_clarification"] is True
        # ambiguity should be absent since it's None
        assert "ambiguity" not in result["outputs"]

    @pytest.mark.asyncio
    async def test_force_execute_overrides_needs_clarification_true_to_false(self, es_query_gen, base_worker_input):
        """params["force_execute"]=True should override needs_clarification=True to False."""
        # LLM returns needs_clarification=True (would normally route to F09)
        mock_query_result = ESQueryResult(
            query={"query": {"term": {"arrival_date": "2024-01-15"}}},
            query_type="search",
            query_summary="Used arrival_date as best guess. Uncertain which date field.",
            ambiguity={
                "field": "date",
                "message": "Uncertain which date field user means",
                "alternatives": ["arrival_date", "eta_date", "departure_date"],
                "confidence": 0.4,
            },
            needs_clarification=True,
        )

        # But force_execute=True in params should override it
        worker_input_with_force = {
            **base_worker_input,
            "sub_goal": {
                "id": 1,
                "worker": "es_query_gen",
                "description": "Find shipments from yesterday",
                "params": {"force_execute": True},
            },
        }

        with patch("app.agent.main_agent4.nodes.f06_es_query_gen.generate_es_query_with_llm", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_query_result

            result = await es_query_gen.ainvoke(worker_input_with_force)

        assert result["status"] == "success"
        # force_execute overrides needs_clarification to False
        assert result["outputs"]["needs_clarification"] is False

    @pytest.mark.asyncio
    async def test_force_execute_no_effect_when_needs_clarification_already_false(self, es_query_gen, base_worker_input):
        """When needs_clarification is already False, force_execute has no additional effect."""
        mock_query_result = ESQueryResult(
            query={"query": {"bool": {"must": [{"term": {"shipper_name.keyword": "MAERSK"}}]}}},
            query_type="search",
            query_summary="Generated a bool query filtering on shipper_name=MAERSK.",
            ambiguity=None,
            needs_clarification=False,
        )

        worker_input_with_force = {
            **base_worker_input,
            "sub_goal": {
                "id": 1,
                "worker": "es_query_gen",
                "description": "Find Maersk shipments",
                "params": {"force_execute": True},
            },
        }

        with patch("app.agent.main_agent4.nodes.f06_es_query_gen.generate_es_query_with_llm", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_query_result

            result = await es_query_gen.ainvoke(worker_input_with_force)

        assert result["status"] == "success"
        assert result["outputs"]["needs_clarification"] is False

    @pytest.mark.asyncio
    async def test_without_force_execute_param_passes_through(self, es_query_gen, base_worker_input):
        """Without force_execute param, needs_clarification passes through unchanged."""
        mock_query_result = ESQueryResult(
            query={"query": {"term": {"some_field": "value"}}},
            query_type="search",
            query_summary="Generated query with ambiguity.",
            ambiguity={"field": "date", "message": "unclear", "alternatives": ["a", "b"], "confidence": 0.5},
            needs_clarification=True,
        )

        # No force_execute in params
        worker_input_no_force = {
            **base_worker_input,
            "sub_goal": {
                "id": 1,
                "worker": "es_query_gen",
                "description": "Find shipments",
                "params": {},  # Empty params
            },
        }

        with patch("app.agent.main_agent4.nodes.f06_es_query_gen.generate_es_query_with_llm", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_query_result

            result = await es_query_gen.ainvoke(worker_input_no_force)

        assert result["status"] == "success"
        # needs_clarification should pass through unchanged
        assert result["outputs"]["needs_clarification"] is True

    @pytest.mark.asyncio
    async def test_force_execute_false_does_not_override(self, es_query_gen, base_worker_input):
        """params["force_execute"]=False should not override LLM's needs_clarification."""
        mock_query_result = ESQueryResult(
            query={"query": {"term": {"arrival_date": "2024-01-15"}}},
            query_type="search",
            query_summary="Used arrival_date as best guess.",
            ambiguity={"field": "date", "message": "unclear", "confidence": 0.4},
            needs_clarification=True,
        )

        worker_input_with_force_false = {
            **base_worker_input,
            "sub_goal": {
                "id": 1,
                "worker": "es_query_gen",
                "description": "Find shipments",
                "params": {"force_execute": False},
            },
        }

        with patch("app.agent.main_agent4.nodes.f06_es_query_gen.generate_es_query_with_llm", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_query_result

            result = await es_query_gen.ainvoke(worker_input_with_force_false)

        assert result["status"] == "success"
        # force_execute=False should not override - needs_clarification stays True
        assert result["outputs"]["needs_clarification"] is True
