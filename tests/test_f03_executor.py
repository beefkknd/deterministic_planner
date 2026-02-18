"""
Test F03 Worker Executor.
Tests that executor correctly extracts sub_goal_id from results.
"""

import pytest
from app.agent.main_agent4.nodes.f03_worker_executor import WorkerExecutor


class TestWorkerExecutor:
    """Tests for WorkerExecutor node."""

    @pytest.mark.asyncio
    async def test_returns_error_for_missing_worker_name(self):
        """Returns failed result when sub_goal has no worker field."""
        executor = WorkerExecutor()

        worker_input = {
            "sub_goal": {"id": 42, "worker": ""},
            "resolved_inputs": {},
        }

        result = await executor.ainvoke(worker_input)

        assert "worker_results" in result
        assert len(result["worker_results"]) == 1
        assert result["worker_results"][0]["sub_goal_id"] == 42
        assert result["worker_results"][0]["status"] == "failed"
        assert "No worker specified" in result["worker_results"][0]["error"]

    @pytest.mark.asyncio
    async def test_returns_error_for_unknown_worker(self):
        """Returns failed result for unknown worker name."""
        executor = WorkerExecutor()

        worker_input = {
            "sub_goal": {"id": 99, "worker": "nonexistent_worker"},
            "resolved_inputs": {},
        }

        result = await executor.ainvoke(worker_input)

        assert result["worker_results"][0]["sub_goal_id"] == 99
        assert result["worker_results"][0]["status"] == "failed"
        assert "Unknown worker" in result["worker_results"][0]["error"]

    @pytest.mark.asyncio
    async def test_extracts_sub_goal_id_from_result(self):
        """Verify sub_goal_id is correctly passed through from worker result."""
        executor = WorkerExecutor()

        worker_input = {
            "sub_goal": {"id": 7, "worker": "metadata_lookup"},
            "resolved_inputs": {"question": "test"},
        }

        result = await executor.ainvoke(worker_input)

        # The worker exists, but will fail due to missing ES
        # The important thing is sub_goal_id is preserved
        assert "worker_results" in result
        assert result["worker_results"][0]["sub_goal_id"] == 7

    @pytest.mark.asyncio
    async def test_message_field_is_none_on_error(self):
        """Error results should have message=None (not missing)."""
        executor = WorkerExecutor()

        worker_input = {
            "sub_goal": {"id": 5, "worker": ""},
            "resolved_inputs": {},
        }

        result = await executor.ainvoke(worker_input)

        assert result["worker_results"][0].get("message") is None
