"""
Test LangGraph topology.
Tests that graph compiles and has correct nodes/edges.
"""

import pytest
from app.agent.main_agent4.graph import create_graph


class TestGraphTopology:
    """Tests for LangGraph topology and compilation."""

    def test_graph_compiles(self):
        """Graph should compile without errors."""
        g = create_graph()
        assert g is not None

    def test_graph_singleton_exists(self):
        """Graph singleton should exist (the module itself is the compiled graph)."""
        from app.agent.main_agent4.graph import graph
        # The import gives us the compiled graph directly
        assert graph is not None

    def test_graph_has_required_nodes(self):
        """Graph should have all required nodes."""
        g = create_graph()
        internal = g.get_graph()
        node_names = list(internal.nodes.keys())

        assert "f01_reiterate" in node_names
        assert "f02_planner" in node_names
        assert "f03_worker_executor" in node_names
        assert "f13_join_reduce" in node_names
        assert "f14_synthesizer" in node_names

    def test_graph_starts_at_f01(self):
        """Graph should start at f01_reiterate."""
        g = create_graph()
        internal = g.get_graph()
        edges = internal.edges

        # Find edges from __start__
        start_edges = [e for e in edges if e[0] == "__start__"]

        assert len(start_edges) > 0
        assert start_edges[0][1] == "f01_reiterate"

    def test_f01_connects_to_f02(self):
        """f01 should connect to f02."""
        g = create_graph()
        internal = g.get_graph()
        edges = internal.edges

        edge_exists = any(e[0] == "f01_reiterate" and e[1] == "f02_planner" for e in edges)
        assert edge_exists

    def test_f02_has_conditional_edge(self):
        """f02 should have conditional edges (fan-out)."""
        g = create_graph()
        internal = g.get_graph()
        edges = internal.edges

        # Conditional edges appear as edges from f02 with conditional=True
        f02_edges = [e for e in edges if e[0] == "f02_planner"]
        assert len(f02_edges) > 0

    def test_has_end_node(self):
        """Graph should have __end__ node."""
        g = create_graph()
        internal = g.get_graph()
        node_names = list(internal.nodes.keys())

        assert "__end__" in node_names
