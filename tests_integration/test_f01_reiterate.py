"""
Integration Test: F01 Reiterate Intention

Tests F01 with a real LLM to verify:
1. Multi-intent decomposition works
2. Question is restated correctly
3. Uses sentence transformers for semantic similarity (85% threshold)
"""

import pytest
from app.agent.main_agent4.nodes.f01_reiterate_intention import f01_reiterate
from app.agent.main_agent4.state import create_initial_state
from app.agent.main_agent4.logging_config import get_logger
from tests_integration.similarity import compute_similarity, is_similar

logger = get_logger("integration_f01")


class TestF01ReiterateIntegration:
    """Integration tests for F01 with real LLM."""

    @pytest.mark.asyncio
    async def test_multi_intent_decomposition(self):
        """
        Test question: "what's shipment and find me a shipment arrived last week at port of Miami"

        Expected: Should decompose into two intents:
        1. Explain what a shipment is
        2. Find shipments arrived last week at port of Miami
        """
        # Create initial state with the test question
        state = create_initial_state(
            question="what's shipment and find me a shipment arrived last week at port of Miami"
        )

        # Run F01
        result = await f01_reiterate.ainvoke(state)

        restated = result.get("question", "")

        logger.info(f"F01 input: {state['question']}")
        logger.info(f"F01 output: {restated}")

        # Should contain both intents
        # Check 1: Should mention "shipment" or explain it
        assert "shipment" in restated.lower(), f"Should mention 'shipment': {restated}"

        # Check 2: Should mention Miami
        assert "miami" in restated.lower(), f"Should mention 'Miami': {restated}"

        # Check 3: Should mention last week or recent
        assert "last week" in restated.lower() or "recent" in restated.lower(), \
            f"Should mention 'last week' or 'recent': {restated}"

        # Check 4: Should be multi-intent (numbered or separated)
        # Semantic check: the output should be semantically similar to expected decomposition
        expected_meaning = "explain what a shipment is and find shipments that arrived last week at port of Miami"
        similarity = compute_similarity(restated, expected_meaning)
        logger.info(f"Semantic similarity to expected: {similarity:.2%}")

        assert is_similar(restated, expected_meaning), \
            f"Output not semantically similar to expected. Similarity: {similarity:.2%}"

    @pytest.mark.asyncio
    async def test_simple_question_passthrough(self):
        """Test that simple single-intent questions are just restated."""
        state = create_initial_state(
            question="How many shipments did we have yesterday?"
        )

        result = await f01_reiterate.ainvoke(state)

        restated = result.get("question", "")

        logger.info(f"F01 input: {state['question']}")
        logger.info(f"F01 output: {restated}")

        # Should preserve the question about shipments
        assert "shipment" in restated.lower(), f"Should mention 'shipment': {restated}"

    @pytest.mark.asyncio
    async def test_pronoun_resolution(self):
        """Test that pronouns are resolved using conversation history."""
        # First turn
        history = [{
            "turn_id": 1,
            "human_message": "Show me Maersk shipments",
            "ai_response": "Here are Maersk shipments",
            "key_artifacts": None,
        }]

        # Second turn with pronoun
        state = create_initial_state(
            question="Show me those from yesterday",
            conversation_history=history,
        )

        result = await f01_reiterate.ainvoke(state)

        restated = result.get("question", "")

        logger.info(f"F01 input: {state['question']}")
        logger.info(f"F01 output: {restated}")

        # Should resolve "those" to refer to Maersk shipments
        assert "maersk" in restated.lower(), f"Should resolve 'those' to Maersk: {restated}"
