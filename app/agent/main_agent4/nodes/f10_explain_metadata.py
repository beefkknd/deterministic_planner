"""
F10: Explain Metadata Node

Explains mapping fields and data structure to the user.
"""

import json
from langchain_core.prompts import ChatPromptTemplate

from app.agent.main_agent4.nodes import BaseWorker
from app.agent.main_agent4.state import WorkerInput, WorkerResult, create_worker_result
from app.agent.main_agent4.worker_registry import worker_tool
from app.agent.foundations.llm_service import get_llm


# =============================================================================
# System Prompt
# =============================================================================

EXPLAIN_PROMPT = """\
You are a helpful maritime shipping data assistant.

Your task is to explain the available data fields and structure to the user
in clear, non-technical language.

Guidelines:
- Use simple language, avoid ES/database jargon
- Group related fields together
- Explain what each field means in a shipping context
- Use markdown formatting with headers and bullet points
- Be concise but thorough
"""

EXPLAIN_TEMPLATE = """\
User question: {question}

Available field metadata:
{metadata}

Explain these fields and data structure to the user."""

PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", EXPLAIN_PROMPT),
    ("human", EXPLAIN_TEMPLATE)
])


# =============================================================================
# Worker Class
# =============================================================================

class ExplainMetadata(BaseWorker):
    """
    Explain Metadata Worker.

    Uses LLM to generate plain-language explanation of fields and schema.
    For queries like "what data do you have about shipments?"
    """

    def __init__(self):
        super().__init__("explain_metadata")
        self._chain = PROMPT_TEMPLATE | get_llm()

    @worker_tool(
        preconditions=["has metadata_results to explain"],
        outputs=["explanation"],
        goal_type="deliverable",
        name="explain_metadata",
        description="Explains mapping fields and data structure to the user",
    )
    async def ainvoke(self, worker_input: WorkerInput) -> WorkerResult:
        """
        Generate a metadata explanation.

        Args:
            worker_input: WorkerInput with sub_goal and resolved_inputs

        Returns:
            WorkerResult with explanation
        """
        sub_goal = worker_input["sub_goal"]
        resolved = worker_input.get("resolved_inputs", {})

        # sub_goal["description"] contains the work instruction from F02
        question = sub_goal.get("description", "")
        metadata_results = resolved.get("metadata_results", {})

        if not metadata_results:
            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="failed",
                error="No metadata results provided to explain",
            )

        try:
            explanation = await self._chain.ainvoke({
                "question": question,
                "metadata": json.dumps(metadata_results, indent=2),
            })

            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="success",
                outputs={"explanation": explanation},
                message="Generated metadata explanation",
            )

        except Exception as e:
            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="failed",
                error=f"Failed to generate explanation: {str(e)}",
            )


# =============================================================================
# Instantiate for export
# =============================================================================

f10_explain_metadata = ExplainMetadata()
