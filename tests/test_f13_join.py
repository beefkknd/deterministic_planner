"""
Test F13 Join Reduce node.
Tests round increment, status update, and worker_results clearing.
"""

import pytest
from app.agent.main_agent4.nodes.f13_join_reduce import JoinReduce


class TestJoinReduce:
    """Tests for JoinReduce node."""

    @pytest.fixture
    def join_reducer(self):
        return JoinReduce()

    @pytest.mark.asyncio
    async def test_increments_round(self, join_reducer):
        """Round should increment after processing."""
        state = {
            "round": 1,
            "status": "executing",
            "worker_results": [],
            "sub_goals": [],
            "completed_outputs": {},
        }

        result = await join_reducer.ainvoke(state)

        assert result["round"] == 2

    @pytest.mark.asyncio
    async def test_sets_status_to_planning(self, join_reducer):
        """Status should be set to planning after join."""
        state = {
            "round": 1,
            "status": "executing",
            "worker_results": [],
            "sub_goals": [],
            "completed_outputs": {},
        }

        result = await join_reducer.ainvoke(state)

        assert result["status"] == "planning"

    @pytest.mark.asyncio
    async def test_clears_worker_results(self, join_reducer):
        """worker_results should be cleared after join."""
        state = {
            "round": 1,
            "status": "executing",
            "worker_results": [{"sub_goal_id": 1, "status": "success"}],
            "sub_goals": [],
            "completed_outputs": {},
        }

        result = await join_reducer.ainvoke(state)

        assert result["worker_results"] == []

    @pytest.mark.asyncio
    async def test_updates_sub_goal_status_from_result(self, join_reducer):
        """Sub-goal status should be updated from worker result."""
        state = {
            "round": 1,
            "status": "executing",
            "worker_results": [
                {"sub_goal_id": 1, "status": "success", "outputs": {"out": "val"}}
            ],
            "sub_goals": [{"id": 1, "status": "pending"}],
            "completed_outputs": {},
        }

        result = await join_reducer.ainvoke(state)

        assert result["sub_goals"][0]["status"] == "success"
        assert result["sub_goals"][0]["result"] == {"out": "val"}

    @pytest.mark.asyncio
    async def test_stores_outputs_on_success(self, join_reducer):
        """Successful results should be stored in completed_outputs."""
        state = {
            "round": 1,
            "status": "executing",
            "worker_results": [
                {
                    "sub_goal_id": 1,
                    "status": "success",
                    "outputs": {"query": {"match": "test"}},
                }
            ],
            "sub_goals": [{"id": 1, "status": "pending"}],
            "completed_outputs": {},
        }

        result = await join_reducer.ainvoke(state)

        assert 1 in result["completed_outputs"]
        assert result["completed_outputs"][1] == {"query": {"match": "test"}}

    @pytest.mark.asyncio
    async def test_preserves_failed_sub_goal_status(self, join_reducer):
        """Failed sub-goals should keep their failed status."""
        state = {
            "round": 1,
            "status": "executing",
            "worker_results": [
                {"sub_goal_id": 1, "status": "failed", "outputs": {}, "error": "oops"}
            ],
            "sub_goals": [{"id": 1, "status": "pending"}],
            "completed_outputs": {},
        }

        result = await join_reducer.ainvoke(state)

        assert result["sub_goals"][0]["status"] == "failed"
        assert result["sub_goals"][0]["error"] == "oops"

    @pytest.mark.asyncio
    async def test_preserves_other_sub_goals(self, join_reducer):
        """Sub-goals not in results should be preserved."""
        state = {
            "round": 1,
            "status": "executing",
            "worker_results": [{"sub_goal_id": 1, "status": "success", "outputs": {}}],
            "sub_goals": [
                {"id": 1, "status": "pending"},
                {"id": 2, "status": "pending"},
            ],
            "completed_outputs": {},
        }

        result = await join_reducer.ainvoke(state)

        assert len(result["sub_goals"]) == 2
        ids = [sg["id"] for sg in result["sub_goals"]]
        assert 1 in ids
        assert 2 in ids

    @pytest.mark.asyncio
    async def test_empty_results_still_increments_round(self, join_reducer):
        """Empty worker_results should still increment round."""
        state = {
            "round": 5,
            "status": "executing",
            "worker_results": [],
            "sub_goals": [],
            "completed_outputs": {},
        }

        result = await join_reducer.ainvoke(state)

        assert result["round"] == 6

    @pytest.mark.asyncio
    async def test_includes_reasoning_message(self, join_reducer):
        """planner_reasoning should summarize the results."""
        state = {
            "round": 1,
            "status": "executing",
            "worker_results": [
                {"sub_goal_id": 1, "status": "success", "outputs": {}},
                {"sub_goal_id": 2, "status": "failed", "outputs": {}, "error": "fail"},
            ],
            "sub_goals": [],
            "completed_outputs": {},
        }

        result = await join_reducer.ainvoke(state)

        assert "Processed 2 results" in result["planner_reasoning"]
        assert "1 succeeded" in result["planner_reasoning"]
        assert "1 failed" in result["planner_reasoning"]
