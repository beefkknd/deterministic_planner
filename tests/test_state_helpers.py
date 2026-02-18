"""
Test state helper functions.
Tests create_initial_state, create_sub_goal, get_pending_sub_goals, etc.
"""

import pytest
from app.agent.main_agent4.state import (
    create_initial_state,
    create_sub_goal,
    get_pending_sub_goals,
    get_completed_deliverables,
    get_all_deliverables,
    MainState,
)


class TestCreateInitialState:
    """Tests for create_initial_state factory function."""

    def test_creates_minimal_state(self):
        """Can create state with just question."""
        state = create_initial_state("what is total?")

        assert state["original_question"] == "what is total?"
        assert state["question"] == "what is total?"
        assert state["round"] == 1
        assert state["max_rounds"] == 10
        assert state["status"] == "planning"
        assert state["sub_goals"] == []
        assert state["completed_outputs"] == {}
        assert state["worker_results"] == []

    def test_preserves_conversation_history(self):
        """Conversation history is preserved."""
        history = [
            {
                "turn_id": 1,
                "human_message": "hello",
                "ai_response": "hi",
                "key_artifacts": None,
            }
        ]
        state = create_initial_state("question", conversation_history=history)

        assert state["conversation_history"] == history

    def test_custom_max_rounds(self):
        """Custom max_rounds is respected."""
        state = create_initial_state("q", max_rounds=5)
        assert state["max_rounds"] == 5


class TestCreateSubGoal:
    """Tests for create_sub_goal factory function."""

    def test_creates_minimal_sub_goal(self):
        """Can create sub-goal with minimal params."""
        sg = create_sub_goal(
            id=1,
            worker="metadata_lookup",
            description="Look up shipper",
            goal_type="support",
        )

        assert sg["id"] == 1
        assert sg["worker"] == "metadata_lookup"
        assert sg["description"] == "Look up shipper"
        assert sg["goal_type"] == "support"
        assert sg["status"] == "pending"
        assert sg["inputs"] == {}
        assert sg["params"] == {}
        assert sg["outputs"] == []

    def test_creates_with_inputs(self):
        """Can create sub-goal with InputRefs."""
        inputs = {
            "analysis": {"from_sub_goal": 1, "slot": "analysis_result"}
        }
        sg = create_sub_goal(
            id=2,
            worker="es_query_gen",
            description="Generate query",
            goal_type="support",
            inputs=inputs,
        )

        assert sg["inputs"] == inputs

    def test_creates_with_params(self):
        """Can create sub-goal with params."""
        params = {"size": 100}
        sg = create_sub_goal(
            id=1,
            worker="test",
            description="test",
            goal_type="support",
            params=params,
        )

        assert sg["params"] == params

    def test_creates_with_outputs(self):
        """Can create sub-goal with output slots."""
        outputs = ["es_query", "ambiguity"]
        sg = create_sub_goal(
            id=1,
            worker="test",
            description="test",
            goal_type="support",
            outputs=outputs,
        )

        assert sg["outputs"] == outputs


class TestGetPendingSubGoals:
    """Tests for get_pending_sub_goals helper."""

    def test_returns_only_pending(self):
        """Returns only sub-goals with status=pending."""
        state: MainState = {
            "original_question": "",
            "question": "",
            "conversation_history": [],
            "sub_goals": [
                {"id": 1, "status": "pending"},
                {"id": 2, "status": "success"},
                {"id": 3, "status": "pending"},
                {"id": 4, "status": "failed"},
            ],
            "completed_outputs": {},
            "round": 1,
            "max_rounds": 10,
            "status": "planning",
            "messages": [],
            "final_response": "",
            "planner_reasoning": "",
            "synthesis_inputs": None,
            "worker_results": [],
        }

        result = get_pending_sub_goals(state)

        assert len(result) == 2
        ids = [sg["id"] for sg in result]
        assert 1 in ids
        assert 3 in ids


class TestGetCompletedDeliverables:
    """Tests for get_completed_deliverables helper."""

    def test_returns_only_completed_deliverables(self):
        """Returns only deliverable sub-goals that succeeded."""
        state: MainState = {
            "original_question": "",
            "question": "",
            "conversation_history": [],
            "sub_goals": [
                {"id": 1, "goal_type": "deliverable", "status": "success"},
                {"id": 2, "goal_type": "deliverable", "status": "failed"},
                {"id": 3, "goal_type": "support", "status": "success"},
            ],
            "completed_outputs": {},
            "round": 1,
            "max_rounds": 10,
            "status": "planning",
            "messages": [],
            "final_response": "",
            "planner_reasoning": "",
            "synthesis_inputs": None,
            "worker_results": [],
        }

        result = get_completed_deliverables(state)

        assert len(result) == 1
        assert result[0]["id"] == 1


class TestGetAllDeliverables:
    """Tests for get_all_deliverables helper."""

    def test_returns_all_deliverables_regardless_of_status(self):
        """Returns all deliverable sub-goals."""
        state: MainState = {
            "original_question": "",
            "question": "",
            "conversation_history": [],
            "sub_goals": [
                {"id": 1, "goal_type": "deliverable", "status": "success"},
                {"id": 2, "goal_type": "deliverable", "status": "pending"},
                {"id": 3, "goal_type": "support", "status": "success"},
            ],
            "completed_outputs": {},
            "round": 1,
            "max_rounds": 10,
            "status": "planning",
            "messages": [],
            "final_response": "",
            "planner_reasoning": "",
            "synthesis_inputs": None,
            "worker_results": [],
        }

        result = get_all_deliverables(state)

        assert len(result) == 2
        ids = [sg["id"] for sg in result]
        assert 1 in ids
        assert 2 in ids
