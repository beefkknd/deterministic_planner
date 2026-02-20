"""
Test F02 InputRef validation and hydration.
Tests _is_sub_goal_ready and _hydrate_worker_input functions.
"""

import pytest
from app.agent.main_agent4.graph import _is_sub_goal_ready, _hydrate_worker_input
from app.agent.main_agent4.nodes.f02_deterministic_planner import _format_f01_context


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


class TestFormatF01Context:
    """Tests for _format_f01_context helper function."""

    def test_empty_completed_outputs_returns_empty(self):
        """Empty completed_outputs returns empty string."""
        state = {"completed_outputs": {}}
        result = _format_f01_context(state)
        assert result == ""

    def test_no_completed_outputs_returns_empty(self):
        """Missing completed_outputs returns empty string."""
        state = {}
        result = _format_f01_context(state)
        assert result == ""

    def test_slot_0_empty_returns_empty(self):
        """Empty slot 0 returns empty string."""
        state = {"completed_outputs": {0: {}}}
        result = _format_f01_context(state)
        assert result == ""

    def test_has_prior_es_query(self):
        """prior_es_query flag is included."""
        state = {
            "completed_outputs": {
                0: {"prior_es_query": {"query": {}}, "prior_next_offset": 10}
            },
            "round": 1,
        }
        result = _format_f01_context(state)
        assert "has_prior_es_query" in result
        assert "Context from F01:" in result

    def test_has_user_es_query(self):
        """user_es_query flag is included."""
        state = {
            "completed_outputs": {
                0: {"user_es_query": '{"query": {}}'}
            },
            "round": 1,
        }
        result = _format_f01_context(state)
        assert "has_user_es_query" in result

    def test_has_both_flags(self):
        """Both flags are included when both present."""
        state = {
            "completed_outputs": {
                0: {
                    "user_es_query": '{"query": {}}',
                    "prior_es_query": {"query": {}},
                    "prior_next_offset": 10,
                }
            },
            "round": 1,
        }
        result = _format_f01_context(state)
        assert "has_prior_es_query" in result
        assert "has_user_es_query" in result

    def test_with_completed_sub_goals(self):
        """Works when there are also completed sub-goals."""
        state = {
            "completed_outputs": {
                0: {"prior_es_query": {"query": {}}},
                1: {"es_results": []},
            },
            "sub_goals": [
                {"id": 1, "status": "success", "worker": "es_query_exec"}
            ],
            "round": 1,
        }
        result = _format_f01_context(state)
        assert "has_prior_es_query" in result

    def test_round_greater_than_1_returns_empty(self):
        """Round > 1 suppresses F01 context (only relevant in round 1)."""
        state = {
            "completed_outputs": {
                0: {"prior_es_query": {"query": {}}, "user_es_query": '{"query": {}}'}
            },
            "round": 2,
        }
        result = _format_f01_context(state)
        assert result == ""

    def test_round_1_returns_context(self):
        """Round 1 includes F01 context."""
        state = {
            "completed_outputs": {
                0: {"prior_es_query": {"query": {}}}
            },
            "round": 1,
        }
        result = _format_f01_context(state)
        assert "has_prior_es_query" in result


class TestConvertPlannedSubGoalsWithIdZero:
    """Tests for InputRef validation with sub_goal id=0."""

    def test_inputref_from_sub_goal_0_passes_validation(self):
        """InputRef with from_sub_goal=0 should pass validation."""
        from app.agent.main_agent4.nodes.f02_deterministic_planner import _convert_planned_sub_goals, PlannedInputRef, PlannedSubGoal

        # Create a planned sub-goal that wires from id=0 (F01 context)
        planned = [
            PlannedSubGoal(
                worker="page_query",
                description="Get next page of results",
                inputs={
                    "es_query": PlannedInputRef(from_sub_goal=0, slot="prior_es_query"),
                    "offset": PlannedInputRef(from_sub_goal=0, slot="prior_next_offset"),
                },
                params={"limit": 20},
                goal_type="support",
            )
        ]

        # State has F01 context in completed_outputs[0]
        existing_sub_goals = []
        completed_outputs = {
            0: {
                "prior_es_query": {"query": {"match_all": {}}},
                "prior_next_offset": 20,
                "prior_page_size": 10,
            }
        }

        result = _convert_planned_sub_goals(planned, 1, existing_sub_goals, completed_outputs)

        # Should create one sub-goal, not marked as failed
        assert len(result) == 1
        assert result[0]["status"] == "pending"
        assert result[0]["error"] is None
        # Verify inputs were correctly converted
        assert result[0]["inputs"]["es_query"]["from_sub_goal"] == 0
        assert result[0]["inputs"]["es_query"]["slot"] == "prior_es_query"

    def test_inputref_from_sub_goal_0_missing_slot_fails(self):
        """InputRef from id=0 with missing slot should fail validation."""
        from app.agent.main_agent4.nodes.f02_deterministic_planner import _convert_planned_sub_goals, PlannedInputRef, PlannedSubGoal

        # Create a planned sub-goal that wires from id=0 but requests non-existent slot
        planned = [
            PlannedSubGoal(
                worker="page_query",
                description="Get next page",
                inputs={
                    "es_query": PlannedInputRef(from_sub_goal=0, slot="nonexistent_slot"),
                },
                params={},
                goal_type="support",
            )
        ]

        existing_sub_goals = []
        completed_outputs = {
            0: {
                "prior_es_query": {"query": {}},
            }
        }

        result = _convert_planned_sub_goals(planned, 1, existing_sub_goals, completed_outputs)

        # Should fail because slot doesn't exist
        assert len(result) == 1
        assert result[0]["status"] == "failed"
        assert "nonexistent_slot" in result[0]["error"]
