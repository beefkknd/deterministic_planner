"""
F14: Synthesizer Node

Collects completed deliverables and synthesizes a final response to the user.
Orchestrates the final output based on synthesis_inputs from F02.

NOT a worker — operates on MainState directly.
"""

from typing import Any
from app.agent.main_agent4.state import MainState, get_completed_deliverables, InputRef


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
# Node Class
# =============================================================================

class Synthesizer:
    """
    F14: Synthesizer.

    Reads synthesis_inputs from F02 (which outputs to use),
    resolves them from completed_outputs, and assembles the final response.
    """

    async def ainvoke(self, state: MainState) -> MainState:
        """
        Synthesize final response based on synthesis_inputs from F02.

        F02 provides synthesis_inputs as a dict of {output_name: InputRef}.
        Each InputRef points to a specific sub_goal and slot to include.

        Args:
            state: Current MainState with completed_outputs and synthesis_inputs

        Returns:
            New MainState with final_response populated
        """
        synthesis_inputs = state.get("synthesis_inputs") or {}
        completed_outputs = state.get("completed_outputs", {})

        if not synthesis_inputs:
            # Fallback: collect all deliverables if no synthesis_inputs specified
            deliverables = get_completed_deliverables(state)
            if not deliverables:
                final_response = (
                    "I wasn't able to complete your request. "
                    "No deliverables were successfully generated."
                )
            else:
                response_parts = []
                for sg in deliverables:
                    sg_id = sg["id"]
                    outputs = completed_outputs.get(sg_id, {})
                    # Get the first deliverable output key
                    for key in ["answer", "formatted_results", "analysis",
                                "clarification_message", "explanation"]:
                        if key in outputs:
                            response_parts.append(_format_output(key, outputs[key]))
                            break
                final_response = "\n\n".join(response_parts) if response_parts else \
                    "Completed but no output to display."
        else:
            # Use synthesis_inputs to resolve specific outputs
            response_parts = []
            for output_name, input_ref in synthesis_inputs.items():
                from_id: int = input_ref["from_sub_goal"]
                slot: str = input_ref["slot"]

                outputs = completed_outputs.get(from_id, {})
                if slot in outputs:
                    response_parts.append(_format_output(slot, outputs[slot]))
                else:
                    response_parts.append(
                        f"[Missing output: {output_name} from sub_goal {from_id}]"
                    )

            final_response = "\n\n".join(response_parts) if response_parts else \
                "No outputs to synthesize."

        return {
            **state,
            "final_response": final_response,
            "status": "done",
            "planner_reasoning": (
                f"F14: Synthesized response from {len(synthesis_inputs)} "
                f"referenced outputs"
            ),
        }


# =============================================================================
# Singleton
# =============================================================================

f14_synthesizer = Synthesizer()
