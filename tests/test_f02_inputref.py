"""
Test F02 InputRef validation and hydration.
Tests _is_sub_goal_ready and _hydrate_worker_input functions.
"""

import pytest
from app.agent.main_agent4.graph import _is_sub_goal_ready, _hydrate_worker_input


class TestIsSubGoalReady:
    """Tests for InputRef readiness check."""

    def test_no_inputs_is_ready(self):
        """Sub-goal with no inputs is always ready."""
        state = {"completed_outputs": {}}
        sub_goal = {"id": 1, "inputs": {}}

        assert _is_sub_goal_ready(sub_goal, state) is True

    def test_all_inputs_satisfied(self):
        """Sub-goal ready when all dependencies are met."""
        state = {
            "completed_outputs": {
                1: {"out1": "value1"},
                2: {"out2": "value2"},
            }
        }
        sub_goal = {
            "id": 3,
            "inputs": {
                "x": {"from_sub_goal": 1, "slot": "out1"},
                "y": {"from_sub_goal": 2, "slot": "out2"},
            },
        }

        assert _is_sub_goal_ready(sub_goal, state) is True

    def test_missing_source_sub_goal(self):
        """Not ready when source sub-goal not completed."""
        state = {"completed_outputs": {1: {"out": "value"}}}
        sub_goal = {
            "id": 2,
            "inputs": {"x": {"from_sub_goal": 99, "slot": "out"}},
        }

        assert _is_sub_goal_ready(sub_goal, state) is False

    def test_missing_slot(self):
        """Not ready when slot doesn't exist in completed output."""
        state = {"completed_outputs": {1: {"other": "value"}}}
        sub_goal = {
            "id": 2,
            "inputs": {"x": {"from_sub_goal": 1, "slot": "missing"}},
        }

        assert _is_sub_goal_ready(sub_goal, state) is False


class TestHydrateWorkerInput:
    """Tests for InputRef hydration (resolving references)."""

    def test_no_inputs_returns_empty(self):
        """Hydrate with no inputs returns empty resolved_inputs."""
        state = {"completed_outputs": {}}
        sub_goal = {"id": 1, "inputs": {}}

        result = _hydrate_worker_input(sub_goal, state)

        assert result["resolved_inputs"] == {}
        assert result["sub_goal"] == sub_goal

    def test_resolves_single_input(self):
        """Correctly resolves a single InputRef."""
        state = {"completed_outputs": {1: {"ship_name": "Maersk Alabama"}}}
        sub_goal = {
            "id": 2,
            "inputs": {"vessel": {"from_sub_goal": 1, "slot": "ship_name"}},
        }

        result = _hydrate_worker_input(sub_goal, state)

        assert result["resolved_inputs"]["vessel"] == "Maersk Alabama"

    def test_resolves_multiple_inputs(self):
        """Correctly resolves multiple InputRefs."""
        state = {
            "completed_outputs": {
                1: {"name": "Maersk", "code": "MAEU"},
                2: {"port": "Shanghai", "code": "CNSHA"},
            }
        }
        sub_goal = {
            "id": 3,
            "inputs": {
                "carrier": {"from_sub_goal": 1, "slot": "name"},
                "port": {"from_sub_goal": 2, "slot": "port"},
            },
        }

        result = _hydrate_worker_input(sub_goal, state)

        assert result["resolved_inputs"]["carrier"] == "Maersk"
        assert result["resolved_inputs"]["port"] == "Shanghai"
