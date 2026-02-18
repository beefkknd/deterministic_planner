"""
Test state reducer functions.
Tests worker_results_reducer for parallel branch concatenation.
"""

import pytest
from app.agent.main_agent4.state import worker_results_reducer


class TestWorkerResultsReducer:
    """Tests for worker_results_reducer function."""

    def test_concatenates_parallel_results(self):
        """Reducer should concatenate results from parallel branches."""
        existing = [
            {"sub_goal_id": 1, "status": "success"},
            {"sub_goal_id": 2, "status": "success"},
        ]
        update = [{"sub_goal_id": 3, "status": "failed"}]

        result = worker_results_reducer(existing, update)

        assert len(result) == 3
        assert result[0]["sub_goal_id"] == 1
        assert result[1]["sub_goal_id"] == 2
        assert result[2]["sub_goal_id"] == 3

    def test_clears_on_empty_update(self):
        """Empty update (F13 case) should clear results."""
        existing = [{"sub_goal_id": 1, "status": "success"}]
        update = []

        result = worker_results_reducer(existing, update)

        assert result == []

    def test_handles_empty_existing(self):
        """Empty existing with update should work."""
        existing = []
        update = [{"sub_goal_id": 1, "status": "success"}]

        result = worker_results_reducer(existing, update)

        assert len(result) == 1
        assert result[0]["sub_goal_id"] == 1

    def test_handles_both_empty(self):
        """Both empty should return empty."""
        result = worker_results_reducer([], [])

        assert result == []
