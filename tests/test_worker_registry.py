"""
Test worker registry.
Tests that workers register with correct capabilities.
"""

import pytest
from app.agent.main_agent4.worker_registry import WORKER_REGISTRY
from app.agent.main_agent4.state import get_worker_capability


class TestWorkerRegistry:
    """Tests for worker registry."""

    def test_registry_not_empty(self):
        """Registry should have registered workers."""
        assert len(WORKER_REGISTRY) > 0

    def test_metadata_lookup_registered(self):
        """metadata_lookup should be registered."""
        cap = get_worker_capability("metadata_lookup")
        assert cap is not None
        assert cap["name"] == "metadata_lookup"
        assert "outputs" in cap

    def test_es_query_gen_registered(self):
        """es_query_gen should be registered."""
        cap = get_worker_capability("es_query_gen")
        assert cap is not None
        assert cap["name"] == "es_query_gen"

    def test_common_helpdesk_registered(self):
        """common_helpdesk should be registered."""
        cap = get_worker_capability("common_helpdesk")
        assert cap is not None
        assert cap["name"] == "common_helpdesk"

    def test_unknown_worker_returns_none(self):
        """Unknown worker should return None."""
        cap = get_worker_capability("nonexistent_worker")
        assert cap is None

    def test_all_workers_have_required_fields(self):
        """All registered workers should have required fields."""
        required_fields = ["name", "description", "preconditions", "outputs", "goal_type"]

        for cap in WORKER_REGISTRY:
            for field in required_fields:
                assert field in cap, f"Worker {cap.get('name')} missing {field}"

    def test_all_workers_have_outputs(self):
        """All workers should declare outputs."""
        for cap in WORKER_REGISTRY:
            assert len(cap["outputs"]) > 0, f"Worker {cap['name']} has no outputs"

    def test_goal_type_is_valid(self):
        """All workers should have valid goal_type."""
        valid_types = ["support", "deliverable"]

        for cap in WORKER_REGISTRY:
            assert cap["goal_type"] in valid_types, f"Invalid goal_type for {cap['name']}"

    def test_no_duplicate_names(self):
        """Registry should not have duplicate worker names."""
        names = [cap["name"] for cap in WORKER_REGISTRY]
        assert len(names) == len(set(names)), "Duplicate worker names found"
