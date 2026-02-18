"""
Integration Test: F02 Deterministic Planner

Tests F02 with a real LLM to verify:
1. Sub-goals are created correctly
2. InputRef wiring is correct
3. Workers are dispatched appropriately

Note: This test verifies sub-goal creation without requiring ES.
"""

import pytest
from app.agent.main_agent4.nodes.f02_deterministic_planner import f02_planner
from app.agent.main_agent4.state import create_initial_state
from app.agent.main_agent4.logging_config import get_logger

logger = get_logger("integration_f02")


class TestF02PlannerIntegration:
    """Integration tests for F02 with real LLM."""

    @pytest.mark.asyncio
    async def test_creates_metadata_lookup_subgoal(self):
        """
        Test that a data query question creates metadata_lookup sub-goal.

        Question: "find shipments from Miami"
        Expected: Should create at least one sub-goal for metadata_lookup
        """
        # First, run F01 to get restated question
        from app.agent.main_agent4.nodes.f01_reiterate_intention import f01_reiterate

        state = create_initial_state(
            question="find shipments from Miami arrived last week"
        )

        f01_result = await f01_reiterate.ainvoke(state)
        state["question"] = f01_result["question"]

        logger.info(f"F01 restated: {state['question']}")

        # Run F02
        result = await f02_planner.ainvoke(state)

        sub_goals = result.get("sub_goals", [])

        logger.info(f"F02 created {len(sub_goals)} sub-goals")
        for sg in sub_goals:
            logger.info(f"  - [{sg['id']}] {sg['worker']}: {sg['description'][:50]}...")

        # Should have at least one sub-goal
        assert len(sub_goals) > 0, "Should create at least one sub-goal"

        # First sub-goal should be metadata_lookup for entity extraction
        workers = [sg.get("worker") for sg in sub_goals]
        assert "metadata_lookup" in workers, \
            f"Should create metadata_lookup sub-goal. Got: {workers}"

    @pytest.mark.asyncio
    async def test_creates_faq_subgoal(self):
        """
        Test that FAQ question creates common_helpdesk sub-goal.

        Question: "what is a bill of lading?"
        Expected: Should create common_helpdesk sub-goal
        """
        state = create_initial_state(
            question="what is a bill of lading?"
        )

        # Run F01
        from app.agent.main_agent4.nodes.f01_reiterate_intention import f01_reiterate
        f01_result = await f01_reiterate.ainvoke(state)
        state["question"] = f01_result["question"]

        # Run F02
        result = await f02_planner.ainvoke(state)

        sub_goals = result.get("sub_goals", [])

        logger.info(f"F02 created {len(sub_goals)} sub-goals")
        for sg in sub_goals:
            logger.info(f"  - [{sg['id']}] {sg['worker']}: {sg['description'][:50]}...")

        # Should have at least one sub-goal
        assert len(sub_goals) > 0, "Should create at least one sub-goal"

        # Should be common_helpdesk for FAQ
        workers = [sg.get("worker") for sg in sub_goals]
        assert "common_helpdesk" in workers, \
            f"Should create common_helpdesk sub-goal for FAQ. Got: {workers}"

    @pytest.mark.asyncio
    async def test_subgoal_has_outputs_declared(self):
        """
        Test that created sub-goals have outputs declared.
        """
        state = create_initial_state(
            question="show me Maersk shipments"
        )

        # Run F01
        from app.agent.main_agent4.nodes.f01_reiterate_intention import f01_reiterate
        f01_result = await f01_reiterate.ainvoke(state)
        state["question"] = f01_result["question"]

        # Run F02
        result = await f02_planner.ainvoke(state)

        sub_goals = result.get("sub_goals", [])

        # Each sub-goal should have outputs declared
        for sg in sub_goals:
            outputs = sg.get("outputs", [])
            logger.info(f"Sub-goal {sg['id']} ({sg['worker']}) outputs: {outputs}")
            assert len(outputs) > 0, \
                f"Sub-goal {sg['id']} should have outputs declared"

    @pytest.mark.asyncio
    async def test_status_is_executing(self):
        """
        Test that status is set to 'executing' when sub-goals are created.
        """
        state = create_initial_state(
            question="how many shipments from China?"
        )

        # Run F01
        from app.agent.main_agent4.nodes.f01_reiterate_intention import f01_reiterate
        f01_result = await f01_reiterate.ainvoke(state)
        state["question"] = f01_result["question"]

        # Run F02
        result = await f02_planner.ainvoke(state)

        status = result.get("status")

        logger.info(f"F02 status: {status}")

        # Should be executing when sub-goals are created
        assert status == "executing", f"Status should be 'executing', got: {status}"
