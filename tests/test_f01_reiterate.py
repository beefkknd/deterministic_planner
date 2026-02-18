"""
Test F01 Reiterate Intention node.
Tests helper functions that don't require LLM.
"""

import pytest
from app.agent.main_agent4.nodes.f01_reiterate_intention import (
    _convert_history_to_messages,
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
        """Key artifacts are appended to AI response."""
        history = [
            {
                "turn_id": 1,
                "human_message": "what is total?",
                "ai_response": "Total is 100",
                "key_artifacts": "shipments: 100",
            }
        ]

        result = _convert_history_to_messages(history)

        assert "Key artifacts: shipments: 100" in result

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
