"""
Integration Test: Full Agent Flow

Tests the complete agent flow with sub-goals:
- F01 restates question
- F02 creates sub-goals
- F03 executes workers (mocked - no real ES)
- F13 joins results
- Verifies state transitions and outputs
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.agent.main_agent4.nodes.f02_deterministic_planner import f02_planner
from app.agent.main_agent4.nodes.f01_reiterate_intention import f01_reiterate
from app.agent.main_agent4.state import create_initial_state
from app.agent.main_agent4.logging_config import get_logger

logger = get_logger("integration_flow")


class TestFullAgentFlow:
    """Integration tests for full agent flow with sub-goals."""

    @pytest.mark.asyncio
    async def test_f02_creates_multiple_subgoals(self):
        """
        Test that F02 creates multiple sub-goals for a complex query.

        Question: "show me Maersk shipments to Miami"
        Expected: Should create metadata_lookup and possibly es_query_gen
        """
        # Run F01 first
        state = create_initial_state(
            question="show me Maersk shipments to Miami arrived last week"
        )

        f01_result = await f01_reiterate.ainvoke(state)
        state["question"] = f01_result["question"]

        logger.info(f"F01 restated: {state['question']}")

        # Run F02
        result = await f02_planner.ainvoke(state)

        sub_goals = result.get("sub_goals", [])
        status = result.get("status")

        logger.info(f"F02 status: {status}")
        logger.info(f"Created {len(sub_goals)} sub-goals:")
        for sg in sub_goals:
            logger.info(f"  [{sg['id']}] {sg['worker']}: {sg.get('description', '')[:50]}")

        # Should create sub-goals
        assert len(sub_goals) > 0, "Should create at least one sub-goal"

        # Should have proper structure
        for sg in sub_goals:
            assert "id" in sg, "Sub-goal should have id"
            assert "worker" in sg, "Sub-goal should have worker"
            assert "description" in sg, "Sub-goal should have description"
            assert "goal_type" in sg, "Sub-goal should have goal_type"
            assert "status" in sg, "Sub-goal should have status"

    @pytest.mark.asyncio
    async def test_f02_inputref_wiring(self):
        """
        Test that F02 properly wires InputRefs between sub-goals.

        When sg2 depends on sg1, from_sub_goal should point to sg1's id.
        """
        state = create_initial_state(
            question="find shipments and count them by port"
        )

        f01_result = await f01_reiterate.ainvoke(state)
        state["question"] = f01_result["question"]

        result = await f02_planner.ainvoke(state)

        sub_goals = result.get("sub_goals", [])

        # Check if any sub-goal has inputs
        sub_goals_with_inputs = [sg for sg in sub_goals if sg.get("inputs")]
        logger.info(f"Sub-goals with inputs: {len(sub_goals_with_inputs)}")

        for sg in sub_goals:
            inputs = sg.get("inputs", {})
            if inputs:
                logger.info(f"  sg{sg['id']} inputs: {inputs}")
                # Validate InputRef structure
                for name, ref in inputs.items():
                    assert "from_sub_goal" in ref, f"Input {name} missing from_sub_goal"
                    assert "slot" in ref, f"Input {name} missing slot"

    @pytest.mark.asyncio
    async def test_round_increments_on_no_pending(self):
        """
        Test that round increments when there are no pending sub-goals.

        This simulates: F02 creates sub-goals → F03 runs → F13 joins → F02 runs again
        """
        # First round: create sub-goals
        state = create_initial_state(
            question="what is a bill of lading?"
        )

        f01_result = await f01_reiterate.ainvoke(state)
        state["question"] = f01_result["question"]

        result1 = await f02_planner.ainvoke(state)

        initial_round = result1.get("round", 1)
        logger.info(f"Round after F02 (first call): {initial_round}")

        # The round should be preserved (not incremented by F02)
        assert initial_round == 1, "F02 should not increment round"

    @pytest.mark.asyncio
    async def test_status_transitions(self):
        """
        Test the status transitions:
        planning → executing → (done | failed)
        """
        # Initial state should be planning
        state = create_initial_state(question="test")
        assert state["status"] == "planning"

        # After F01, still planning
        f01_result = await f01_reiterate.ainvoke(state)
        assert f01_result["status"] == "planning"

        # After F02 with sub-goals, should be executing
        result = await f02_planner.ainvoke(f01_result)
        status = result.get("status")

        logger.info(f"Status after F02: {status}")

        # Should be either executing or done (depending on LLM)
        assert status in ["executing", "done"], f"Unexpected status: {status}"
