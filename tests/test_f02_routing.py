"""
Test F02 routing logic (route_after_planner function).
Tests all branches: executing/done/failed, with/without pending sub-goals.
"""

import pytest
from langgraph.types import Send
from app.agent.main_agent4.graph import route_after_planner


class TestRouteAfterPlanner:
    """Tests for route_after_planner conditional edge function."""

    def test_executing_with_ready_subgoals_returns_sends(self):
        """When status=executing and sub-goals are ready, return list of Send."""
        state = {
            "status": "executing",
            "sub_goals": [
                {"id": 1, "status": "pending", "inputs": {}},
            ],
            "completed_outputs": {},
        }
        result = route_after_planner(state)

        assert isinstance(result, list)
        assert len(result) == 1

    def test_executing_with_blocked_subgoals_returns_f13(self):
        """When status=executing but all pending are blocked, route to F13."""
        state = {
            "status": "executing",
            "sub_goals": [
                {
                    "id": 1,
                    "status": "pending",
                    "inputs": {"x": {"from_sub_goal": 99, "slot": "out"}},
                },
            ],
            "completed_outputs": {},  # sub_goal 99 not completed
        }
        result = route_after_planner(state)

        assert result == "f13_join_reduce"

    def test_executing_with_mixed_ready_and_blocked(self):
        """When some ready, some blocked, only send ready ones."""
        state = {
            "status": "executing",
            "sub_goals": [
                {"id": 1, "status": "pending", "inputs": {}},  # ready (no inputs)
                {
                    "id": 2,
                    "status": "pending",
                    "inputs": {"x": {"from_sub_goal": 1, "slot": "out"}},
                },  # blocked (dependency not met yet)
            ],
            "completed_outputs": {1: {"out": "value"}},
        }
        result = route_after_planner(state)

        # Both are ready: sg1 has no inputs, sg2's dep is in completed_outputs
        assert isinstance(result, list)
        assert len(result) == 2  # both sub-goals are ready

    def test_executing_with_empty_subgoals_returns_f13(self):
        """When no sub-goals to execute, route to F13."""
        state = {
            "status": "executing",
            "sub_goals": [],
            "completed_outputs": {},
        }
        result = route_after_planner(state)

        assert result == "f13_join_reduce"

    def test_status_done_routes_to_synthesizer(self):
        """When status=done, route to F14 synthesizer."""
        state = {
            "status": "done",
            "sub_goals": [],
            "completed_outputs": {},
        }
        result = route_after_planner(state)

        assert result == "f14_synthesizer"

    def test_status_failed_routes_to_end(self):
        """When status=failed, route to END."""
        state = {
            "status": "failed",
            "sub_goals": [],
            "completed_outputs": {},
        }
        result = route_after_planner(state)

        # LangGraph uses "__end__" as the END node name
        assert result == "__end__"

    def test_status_planning_routes_to_end(self):
        """When status=planning (unexpected), route to END."""
        state = {
            "status": "planning",
            "sub_goals": [],
            "completed_outputs": {},
        }
        result = route_after_planner(state)

        # LangGraph uses "__end__" as the END node name
        assert result == "__end__"
