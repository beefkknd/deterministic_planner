"""
F01: Reiterate Intention Node

Entry node. Reads chat history + current user message, restates the user's
intent as an executable main goal. NOT a worker — operates on MainState directly.

Uses Pydantic structured output for reliable LLM response parsing.
"""

from typing import Optional, Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

from app.agent.main_agent4.logging_config import get_logger
from app.agent.main_agent4.state import MainState, TurnSummary
from app.agent.foundations.llm_service import get_llm

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
    user_query_text: str | None = Field(
        default=None,
        description=(
            "Raw ES query text if the user referenced, pasted, or asked about "
            "a query in their message. None if no query was referenced. "
            "Include even if the JSON is malformed or incomplete."
        ),
    )
    references_prior_results: bool = Field(
        default=False,
        description=(
            "True if the user is referencing prior results from a previous turn, "
            "e.g., 'show more', 'next page', 'those results', 'your last query'. "
            "False for fresh queries."
        ),
    )


# =============================================================================
# System Prompt
# =============================================================================

REITERATE_SYSTEM_PROMPT = """\
You are an intent-analysis module for a maritime shipping assistant.

Your job is to:
1. Restate the user's message as a clear, actionable goal
2. Detect if they referenced a query (pasted or asked about)
3. Detect if they referenced prior results from a previous turn

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

6. Query Detection: If the user pastes a raw ES query or asks about a query
   (e.g., "here's my query", "run this", "explain this query"), extract the
   raw text into user_query_text. Include even if the JSON is malformed.

7. Prior Result Detection: If the user references previous results from this
   conversation (e.g., "show more", "next page", "those results", "your last
   query", "keep going"), set references_prior_results to true.
"""

REITERATE_TEMPLATE = """\
Chat history:
{chat_history}

Current user message:
{question}

Restate the user's intent as a clear, actionable goal."""

PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", REITERATE_SYSTEM_PROMPT),
    ("human", REITERATE_TEMPLATE)
])


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
            # Include artifact intents so LLM can reason about prior queries
            artifact_summaries = []
            for artifact in key_artifacts:
                artifact_summaries.append(artifact.get("intent", artifact.get("type", "unknown")))
            ai_content = f"{ai_content}\n[Prior queries: {', '.join(artifact_summaries)}]"
        lines.append(f"AI: {ai_content}")

    return "\n".join(lines)


def _find_prior_agent_query(
    history: Optional[list[TurnSummary]],
) -> dict[str, Any] | None:
    """
    Find the most recent es_query key_artifact from conversation history.

    Scans history most-recent-first and returns the first artifact
    with type == "es_query". Returns None if no match found.

    Args:
        history: List of prior turn summaries

    Returns:
        Dict with artifact slots (es_query, next_offset, page_size, etc.)
        or None if no matching artifact found.
    """
    if not history:
        return None

    # Scan most-recent-first
    for turn in reversed(history):
        key_artifacts = turn.get("key_artifacts")
        if not key_artifacts:
            continue

        for artifact in key_artifacts:
            if artifact.get("type") == "es_query":
                # Return the slots dict
                return artifact.get("slots")

    return None


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
        llm = get_llm()
        self._chain = PROMPT_TEMPLATE | llm.with_structured_output(ReiterateResult)

    async def ainvoke(self, state: MainState) -> MainState:
        """
        Restate the user's intent as a clear, actionable goal.

        Detects user-referenced queries and prior result references,
        writing them to completed_outputs[0] for F02 to use.

        Args:
            state: Current MainState

        Returns:
            New MainState with restated question, planner_reasoning,
            and completed_outputs[0] populated with context slots.
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

            # Build completed_outputs[0] - the synthetic context sub-goal
            completed_outputs_0: dict[str, Any] = {}

            # 1. User-referenced query - write raw text for F07 validation
            if result.user_query_text:
                completed_outputs_0["user_es_query"] = result.user_query_text
                logger.info(f"F01: Detected user-referenced query")

            # 2. Prior result reference - look up from key_artifacts
            # Write individual slots so F02 can wire via InputRef
            if result.references_prior_results:
                prior_query = _find_prior_agent_query(conversation_history)
                if prior_query:
                    # Write individual slots for InputRef wiring
                    completed_outputs_0["prior_es_query"] = prior_query.get("es_query")
                    completed_outputs_0["prior_next_offset"] = prior_query.get("next_offset")
                    completed_outputs_0["prior_page_size"] = prior_query.get("page_size")
                    logger.info(f"F01: Found prior agent query")
                else:
                    logger.info(
                        "F01: references_prior_results=True but no matching artifact"
                    )
                    # Don't write anything - downstream handles gracefully

            # Build updated completed_outputs dict
            existing_completed = state.get("completed_outputs", {})
            new_completed = {**existing_completed, 0: completed_outputs_0}

            logger.info(f"F01: Restated goal: {main_goal[:100]}...")
            logger.info(
                f"F01: completed_outputs[0] slots: {list(completed_outputs_0.keys())}"
            )

            return {
                **state,
                "question": main_goal,
                "planner_reasoning": f"F01: {result.reasoning}",
                "completed_outputs": new_completed,
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
