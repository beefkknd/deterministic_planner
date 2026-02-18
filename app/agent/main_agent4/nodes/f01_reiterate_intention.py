"""
F01: Reiterate Intention Node

Entry node. Reads chat history + current user message, restates the user's
intent as an executable main goal. NOT a worker — operates on MainState directly.

Uses Pydantic structured output for reliable LLM response parsing.
"""

from typing import Optional
from pydantic import BaseModel, Field

from app.agent.main_agent4.logging_config import get_logger
from app.agent.main_agent4.state import MainState, TurnSummary
from app.agent.foundations.llm_service import LLMService

logger = get_logger("f01_reiterate")


# =============================================================================
# Pydantic Output Type
# =============================================================================

class ReiterateResult(BaseModel):
    """Structured output from the F01 intent restatement."""
    main_goal: str = Field(
        description=(
            "Clear, actionable restatement of the user's intent. "
            "Multi-intent queries are decomposed into numbered goals."
        ),
    )
    reasoning: str = Field(
        description=(
            "Brief explanation of how the intent was interpreted, "
            "including any context resolution from chat history."
        ),
    )


# =============================================================================
# System Prompt
# =============================================================================

REITERATE_SYSTEM_PROMPT = """\
You are an intent-analysis module for a maritime shipping assistant.

Your ONLY job is to restate the user's message as a clear, actionable goal.
Do NOT answer the question — only restate it.

Rules:
1. Decompose multi-intent queries into numbered goals.
   Example: "what's a shipment and find me one from yesterday"
   → "(1) Explain what a shipment is (2) Find shipments that arrived yesterday"

2. Resolve pronouns and references using conversation history.
   Example: User says "show me those" after asking about Maersk
   → "Show the Maersk shipments from the previous query"

3. Normalize vague language into precise intent.
   Example: "anything from China lately"
   → "Find recent shipments with port_of_loading in China"

4. Preserve the user's original scope — do not add or remove intents.

5. If the message is already clear and single-intent, return it as-is
   with minimal rewording.
"""

REITERATE_TEMPLATE = """\
Chat history:
{chat_history}

Current user message:
{question}

Restate the user's intent as a clear, actionable goal."""


# =============================================================================
# Helpers
# =============================================================================

def _convert_history_to_messages(
    history: Optional[list[TurnSummary]],
) -> str:
    """
    Convert conversation history (TurnSummaries) into a chat transcript
    string with Human/AI messages and optional key artifacts.

    Each turn is rendered as:
      Human: <question>
      AI: <response>
      [Key artifacts: <artifacts>]  (only if present)

    Args:
        history: List of prior turn summaries, or None

    Returns:
        Formatted chat history string
    """
    if not history:
        return "(no prior conversation)"

    lines = []
    for turn in history[-5:]:  # Last 5 turns max
        lines.append(f"Human: {turn['human_message']}")

        ai_content = turn["ai_response"]
        key_artifacts = turn.get("key_artifacts")
        if key_artifacts:
            ai_content = f"{ai_content}\nKey artifacts: {key_artifacts}"
        lines.append(f"AI: {ai_content}")

    return "\n".join(lines)


# =============================================================================
# Node Class
# =============================================================================

class ReiterateIntention:
    """
    F01: Reiterate Intention.

    Restates user intent as a clear, actionable goal using LLM
    with structured output. Chain is created once at init.
    """

    def __init__(self):
        self._llm_service = LLMService.get_instance()
        self._chain = self._llm_service.create_structured_chain(
            system_message=REITERATE_SYSTEM_PROMPT,
            prompt_template=REITERATE_TEMPLATE,
            output_schema=ReiterateResult,
        )

    async def ainvoke(self, state: MainState) -> MainState:
        """
        Restate the user's intent as a clear, actionable goal.

        Args:
            state: Current MainState

        Returns:
            New MainState with restated question and planner_reasoning
        """
        question = state.get("question", "")
        logger.info(f"F01: Input question: {question[:100]}...")

        if not question:
            logger.warning("F01: No user message provided")
            return {
                **state,
                "question": "",
                "planner_reasoning": "F01: No user message provided",
            }

        conversation_history: Optional[list[TurnSummary]] = state.get(
            "conversation_history"
        )

        try:
            chat_history = _convert_history_to_messages(conversation_history)

            result: ReiterateResult = await self._chain.ainvoke({
                "chat_history": chat_history,
                "question": question,
            })

            main_goal = result.main_goal.strip()
            if not main_goal:
                main_goal = question

            logger.info(f"F01: Restated goal: {main_goal[:100]}...")
            return {
                **state,
                "question": main_goal,
                "planner_reasoning": f"F01: {result.reasoning}",
            }

        except Exception as e:
            logger.error(f"F01: LLM failed - {str(e)}, using original question")
            return {
                **state,
                "planner_reasoning": (
                    f"F01: LLM failed ({str(e)}), using original question"
                ),
            }


# =============================================================================
# Singleton
# =============================================================================

f01_reiterate = ReiterateIntention()
