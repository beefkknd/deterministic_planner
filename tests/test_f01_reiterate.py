"""
Test F01 Reiterate Intention node.
Tests helper functions that don't require LLM.
"""

import pytest
from app.agent.main_agent4.nodes.f01_reiterate_intention import (
    _convert_history_to_messages,
    _find_prior_agent_query,
    ReiterateResult,
)


class TestConvertHistoryToMessages:
    """Tests for _convert_history_to_messages helper."""

    def test_empty_history_returns_default(self):
        """Empty history returns default message."""
        result = _convert_history_to_messages(None)
        assert result == "(no prior conversation)"

    def test_empty_list_returns_default(self):
        """Empty list returns default message."""
        result = _convert_history_to_messages([])
        assert result == "(no prior conversation)"

    def test_single_turn_converted(self):
        """Single turn is correctly formatted."""
        history = [
            {
                "turn_id": 1,
                "human_message": "show me Maersk shipments",
                "ai_response": "Here are Maersk shipments",
                "key_artifacts": None,
            }
        ]

        result = _convert_history_to_messages(history)

        assert "Human: show me Maersk shipments" in result
        assert "AI: Here are Maersk shipments" in result

    def test_key_artifacts_appended(self):
        """Key artifacts intents are rendered in Prior queries format."""
        history = [
            {
                "turn_id": 1,
                "human_message": "what is total?",
                "ai_response": "Total is 100",
                "key_artifacts": [
                    {"type": "es_query", "intent": "shipments from China"}
                ],
            }
        ]

        result = _convert_history_to_messages(history)

        assert "[Prior queries: shipments from China]" in result

    def test_limited_to_last_5_turns(self):
        """Only last 5 turns are included."""
        history = [
            {"turn_id": i, "human_message": f"q{i}", "ai_response": f"a{i}", "key_artifacts": None}
            for i in range(10)
        ]

        result = _convert_history_to_messages(history)

        assert "q0" not in result  # Should not include first turn
        assert "q9" in result  # Should include last turn
        assert "q5" in result

    def test_multiple_turns_joined(self):
        """Multiple turns are joined with newlines."""
        history = [
            {"turn_id": 1, "human_message": "q1", "ai_response": "a1", "key_artifacts": None},
            {"turn_id": 2, "human_message": "q2", "ai_response": "a2", "key_artifacts": None},
        ]

        result = _convert_history_to_messages(history)

        assert "Human: q1" in result
        assert "Human: q2" in result
        assert "AI: a1" in result
        assert "AI: a2" in result


class TestReiterateResult:
    """Tests for ReiterateResult Pydantic model."""

    def test_can_create_with_main_goal(self):
        """Can create result with main_goal."""
        result = ReiterateResult(main_goal="Find shipments", reasoning="User wants to find")

        assert result.main_goal == "Find shipments"
        assert result.reasoning == "User wants to find"

    def test_requires_main_goal(self):
        """main_goal is required."""
        with pytest.raises(Exception):
            ReiterateResult(reasoning="test")

    def test_model_validation(self):
        """Model validates on creation."""
        result = ReiterateResult(
            main_goal="Find Maersk",
            reasoning="User asked for Maersk",
        )

        assert result.main_goal == "Find Maersk"
        assert result.reasoning == "User asked for Maersk"

    def test_user_query_text_optional(self):
        """user_query_text is optional and defaults to None."""
        result = ReiterateResult(
            main_goal="Find shipments",
            reasoning="User wants to find",
        )

        assert result.user_query_text is None

    def test_references_prior_results_default_false(self):
        """references_prior_results defaults to False."""
        result = ReiterateResult(
            main_goal="Find shipments",
            reasoning="User wants to find",
        )

        assert result.references_prior_results is False

    def test_can_set_user_query_text(self):
        """Can set user_query_text field."""
        result = ReiterateResult(
            main_goal="Run this query",
            reasoning="User pasted a query",
            user_query_text='{"query": {"match_all": {}}}',
        )

        assert result.user_query_text == '{"query": {"match_all": {}}}'

    def test_can_set_references_prior_results(self):
        """Can set references_prior_results field."""
        result = ReiterateResult(
            main_goal="Show more",
            reasoning="User wants pagination",
            references_prior_results=True,
        )

        assert result.references_prior_results is True


class TestFindPriorAgentQuery:
    """Tests for _find_prior_agent_query helper."""

    def test_empty_history_returns_none(self):
        """Empty history returns None."""
        result = _find_prior_agent_query(None)
        assert result is None

    def test_empty_list_returns_none(self):
        """Empty list returns None."""
        result = _find_prior_agent_query([])
        assert result is None

    def test_no_artifacts_returns_none(self):
        """History with no key_artifacts returns None."""
        history = [
            {"turn_id": 1, "human_message": "q", "ai_response": "a", "key_artifacts": None}
        ]
        result = _find_prior_agent_query(history)
        assert result is None

    def test_finds_es_query_artifact(self):
        """Finds es_query type artifact and returns its slots."""
        history = [
            {
                "turn_id": 1,
                "human_message": "q",
                "ai_response": "a",
                "key_artifacts": [
                    {"type": "es_query", "slots": {"es_query": {"match_all": {}}, "next_offset": 20, "page_size": 10}}
                ],
            }
        ]
        result = _find_prior_agent_query(history)
        assert result == {"es_query": {"match_all": {}}, "next_offset": 20, "page_size": 10}

    def test_ignores_non_es_query_artifacts(self):
        """Ignores artifacts that are not es_query type."""
        history = [
            {
                "turn_id": 1,
                "human_message": "q",
                "ai_response": "a",
                "key_artifacts": [
                    {"type": "analysis_result", "slots": {"result": "data"}}
                ],
            }
        ]
        result = _find_prior_agent_query(history)
        assert result is None

    def test_returns_most_recent_first(self):
        """Returns the most recent es_query artifact (scans reversed)."""
        history = [
            {
                "turn_id": 1,
                "human_message": "q1",
                "ai_response": "a1",
                "key_artifacts": [
                    {"type": "es_query", "slots": {"es_query": "old"}}
                ],
            },
            {
                "turn_id": 2,
                "human_message": "q2",
                "ai_response": "a2",
                "key_artifacts": [
                    {"type": "es_query", "slots": {"es_query": "new"}}
                ],
            },
        ]
        result = _find_prior_agent_query(history)
        assert result == {"es_query": "new"}

    def test_skips_turns_without_matching_artifacts(self):
        """Skips turns until finding a matching es_query artifact."""
        history = [
            {
                "turn_id": 1,
                "human_message": "q1",
                "ai_response": "a1",
                "key_artifacts": [
                    {"type": "analysis_result", "slots": {"result": "data"}}
                ],
            },
            {
                "turn_id": 2,
                "human_message": "q2",
                "ai_response": "a2",
                "key_artifacts": [
                    {"type": "es_query", "slots": {"es_query": "found"}}
                ],
            },
        ]
        result = _find_prior_agent_query(history)
        assert result == {"es_query": "found"}
