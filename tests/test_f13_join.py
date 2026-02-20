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


class TestBuildKeyArtifacts:
    """Tests for _build_key_artifacts method."""

    @pytest.fixture
    def join_reducer(self):
        return JoinReduce()

    def test_f06_f07_bundle_creates_single_artifact(self, join_reducer):
        """F06+F07 should be bundled into single key_artifact."""
        worker_results = [
            {
                "sub_goal_id": 1,
                "status": "success",
                "outputs": {"es_query": {"match_all": {}}, "intent": "find all shipments"},
            },
            {
                "sub_goal_id": 2,
                "status": "success",
                "outputs": {"next_offset": 20, "page_size": 20},
            },
        ]
        sub_goals = [
            {"id": 1, "worker": "es_query_gen", "params": {}},
            {"id": 2, "worker": "es_query_exec", "params": {"bundles_with_sub_goal": 1}},
        ]

        result = join_reducer._build_key_artifacts(worker_results, sub_goals, 1, {})

        # Should have 1 artifact with both es_query and pagination
        assert len(result) == 1
        assert result[0]["type"] == "es_query"
        assert result[0]["slots"]["es_query"] == {"match_all": {}}
        assert result[0]["slots"]["next_offset"] == 20
        assert result[0]["slots"]["page_size"] == 20

    def test_f08_continuation_preserves_es_query(self, join_reducer):
        """F08 should preserve es_query for multi-page continuation."""
        worker_results = [
            {
                "sub_goal_id": 3,
                "status": "success",
                "outputs": {
                    "es_query": {"match_all": {}},
                    "next_offset": 40,
                    "page_size": 20,
                },
            }
        ]
        sub_goals = [
            {"id": 3, "worker": "page_query", "params": {}},
        ]

        result = join_reducer._build_key_artifacts(worker_results, sub_goals, 2, {})

        # Should have 1 artifact with es_query preserved
        assert len(result) == 1
        assert result[0]["type"] == "es_query"
        assert result[0]["slots"]["es_query"] == {"match_all": {}}
        assert result[0]["slots"]["next_offset"] == 40

    def test_f05_standalone_creates_analysis_artifact(self, join_reducer):
        """F05 standalone should create analysis_result artifact."""
        worker_results = [
            {
                "sub_goal_id": 1,
                "status": "success",
                "outputs": {
                    "analysis_result": {"intent_type": "search", "entity_mappings": {"ship": "shipment"}}
                },
            }
        ]
        sub_goals = [
            {"id": 1, "worker": "metadata_lookup", "params": {}},
        ]

        result = join_reducer._build_key_artifacts(worker_results, sub_goals, 1, {})

        assert len(result) == 1
        assert result[0]["type"] == "analysis_result"
        assert result[0]["slots"]["analysis_result"]["intent_type"] == "search"

    def test_skips_failed_workers(self, join_reducer):
        """Failed workers should not create artifacts."""
        worker_results = [
            {
                "sub_goal_id": 1,
                "status": "failed",
                "outputs": {"es_query": {}},
            }
        ]
        sub_goals = [
            {"id": 1, "worker": "es_query_gen", "params": {}},
        ]

        result = join_reducer._build_key_artifacts(worker_results, sub_goals, 1, {})

        assert len(result) == 0
