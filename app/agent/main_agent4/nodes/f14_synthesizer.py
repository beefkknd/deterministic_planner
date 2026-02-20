"""
F14: Synthesizer Node

Collects completed deliverables and synthesizes a final response to the user.
Orchestrates the final output based on synthesis_inputs from F02.

Two-phase synthesis:
- Phase 1: LLM synthesis with narrative deliverables (prose)
- Phase 2: Append display deliverables verbatim (tables, lists)

NOT a worker — operates on MainState directly.
"""

from typing import Any
from langchain_core.prompts import ChatPromptTemplate

from app.agent.main_agent4.state import MainState, get_completed_deliverables, InputRef
from app.agent.main_agent4.worker_registry import get_capability_by_name
from app.agent.foundations.llm_service import get_llm


# =============================================================================
# Output Key Formatters
# =============================================================================

# Keys that should be returned as-is (converted to string)
PASSTHROUGH_KEYS = {"answer", "formatted_results", "analysis",
                     "clarification_message", "explanation"}


def _format_output(key: str, value: Any) -> str:
    """
    Format a worker output into a human-readable string.

    Args:
        key: Output slot name (e.g., "answer", "formatted_results")
        value: The actual output value

    Returns:
        Formatted string for the final response
    """
    if key in PASSTHROUGH_KEYS:
        return str(value)
    return f"{key}: {value}"


# =============================================================================
# System Prompt for LLM Synthesis
# =============================================================================

SYNTHESIS_SYSTEM_PROMPT = """\
You are a maritime shipping assistant. Synthesize a coherent response from
multiple deliverables. Weave narrative content into a natural answer.
"""


SYNTHESIS_TEMPLATE = """\
User question: {question}

Deliverables to synthesize:
{deliverables}

Synthesize a coherent response that addresses the user's question."""


# =============================================================================
# Node Class
# =============================================================================

class Synthesizer:
    """
    F14: Synthesizer.

    Two-phase synthesis:
    - Phase 1: LLM synthesis with narrative deliverables (prose)
    - Phase 2: Append display deliverables verbatim (tables, lists)
    """

    def __init__(self):
        self._chain = None  # Lazy init

    def _get_chain(self):
        """Lazy initialization of LLM chain."""
        if self._chain is None:
            prompt = ChatPromptTemplate.from_messages([
                ("system", SYNTHESIS_SYSTEM_PROMPT),
                ("human", SYNTHESIS_TEMPLATE)
            ])
            self._chain = prompt | get_llm()
        return self._chain

    async def ainvoke(self, state: MainState) -> MainState:
        """
        Synthesize final response using two-phase approach.

        Phase 1: LLM synthesis with narrative deliverables
        Phase 2: Append display deliverables verbatim

        Args:
            state: Current MainState with completed_outputs and synthesis_inputs

        Returns:
            New MainState with final_response populated
        """
        synthesis_inputs = state.get("synthesis_inputs") or {}
        completed_outputs = state.get("completed_outputs", {})
        question = state.get("question", "")

        # Collect deliverables and split by synthesis_mode
        narrative_outputs = []  # For LLM synthesis
        display_outputs = []    # Append verbatim

        deliverables = get_completed_deliverables(state)

        for sg in deliverables:
            worker_name = sg.get("worker")
            capability = get_capability_by_name(worker_name)
            synthesis_mode = capability.get("synthesis_mode", "hidden") if capability else "hidden"

            # Get the output value
            sg_id = sg["id"]
            outputs = completed_outputs.get(sg_id, {})

            # Find the deliverable output key
            deliverable_key = None
            for key in ["answer", "formatted_results", "analysis",
                        "clarification_message", "explanation"]:
                if key in outputs:
                    deliverable_key = key
                    break

            if not deliverable_key:
                continue

            value = outputs[deliverable_key]

            if synthesis_mode == "narrative":
                narrative_outputs.append({
                    "worker": worker_name,
                    "key": deliverable_key,
                    "value": value,
                })
            elif synthesis_mode == "display":
                display_outputs.append({
                    "worker": worker_name,
                    "key": deliverable_key,
                    "value": value,
                })
            # hidden: skip

        # Phase 1: LLM synthesis for narrative outputs
        if narrative_outputs:
            # Build deliverables string for LLM
            deliverables_str = []
            for item in narrative_outputs:
                deliverables_str.append(
                    f"[{item['worker']}]: {item['value']}"
                )

            try:
                llm_response = await self._get_chain().ainvoke({
                    "question": question,
                    "deliverables": "\n\n".join(deliverables_str),
                })
                narrative_response = str(llm_response.content)
            except Exception as e:
                # Fallback to simple concatenation
                narrative_response = "\n\n".join(
                    str(item["value"]) for item in narrative_outputs
                )
        else:
            narrative_response = None

        # Phase 2: Append display outputs verbatim
        display_response_parts = []
        for item in display_outputs:
            display_response_parts.append(str(item["value"]))
        display_response = "\n\n".join(display_response_parts) if display_response_parts else None

        # Combine: narrative first, then display
        final_parts = []
        if narrative_response:
            final_parts.append(narrative_response)
        if display_response:
            final_parts.append(display_response)

        if not final_parts:
            final_response = (
                "I wasn't able to complete your request. "
                "No deliverables were successfully generated."
            )
        else:
            final_response = "\n\n".join(final_parts)

        return {
            **state,
            "final_response": final_response,
            "status": "done",
            "planner_reasoning": (
                f"F14: Synthesized {len(narrative_outputs)} narrative, "
                f"{len(display_outputs)} display outputs"
            ),
        }


# =============================================================================
# Singleton
# =============================================================================

f14_synthesizer = Synthesizer()
