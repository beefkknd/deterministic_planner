"""
F09: Clarify Question Node

Generates a markdown clarification message when the planner detects ambiguity.
"""

from app.agent.main_agent4.nodes import BaseWorker
from app.agent.main_agent4.state import WorkerInput, WorkerResult, create_worker_result
from app.agent.main_agent4.worker_registry import worker_tool
from app.agent.foundations.llm_service import LLMService


# =============================================================================
# System Prompt
# =============================================================================

CLARIFY_PROMPT = """\
You are a helpful maritime shipping assistant.

Your task is to generate a friendly clarification question for the user.
You've been given ambiguity information about their query.

Guidelines:
- Be polite and concise
- Present alternatives clearly as a numbered list
- Ask the user to pick one or clarify further
- Use markdown formatting
- Do NOT guess or assume the answer
"""

CLARIFY_TEMPLATE = """\
Original question: {question}

Ambiguity details:
- Field: {field}
- Issue: {message}
- Alternatives: {alternatives}

Generate a clarification message in markdown."""


# =============================================================================
# Worker Class
# =============================================================================

class ClarifyQuestion(BaseWorker):
    """
    Clarify Question Worker.

    Generates user-friendly markdown clarification when ambiguity is detected.
    No human interrupt — message becomes part of final response.
    """

    def __init__(self):
        super().__init__("clarify_question")
        self._llm_service = LLMService.get_instance()
        self._chain = self._llm_service.create_chain(
            system_message=CLARIFY_PROMPT,
            prompt_template=CLARIFY_TEMPLATE,
        )

    @worker_tool(
        preconditions=["planner identified ambiguity requiring clarification"],
        outputs=["clarification_message"],
        goal_type="deliverable",
        name="clarify_question",
        description="Generates a markdown clarification message when planner detects ambiguity",
    )
    async def ainvoke(self, worker_input: WorkerInput) -> WorkerResult:
        """
        Generate a clarification message.

        Args:
            worker_input: WorkerInput with sub_goal and resolved_inputs

        Returns:
            WorkerResult with clarification_message
        """
        sub_goal = worker_input["sub_goal"]
        resolved = worker_input.get("resolved_inputs", {})
        params = sub_goal.get("params", {})

        # sub_goal["description"] contains the work instruction from F02
        question = sub_goal.get("description", "")
        ambiguity = resolved.get("ambiguity") or params.get("ambiguity", {})

        field = ambiguity.get("field", "unknown")
        message = ambiguity.get("message", "The query is ambiguous")
        alternatives = ambiguity.get("alternatives", [])

        try:
            clarification = await self._chain.ainvoke({
                "question": question,
                "field": field,
                "message": message,
                "alternatives": ", ".join(alternatives) if alternatives else "none specified",
            })

            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="success",
                outputs={"clarification_message": clarification},
                message=f"Generated clarification for ambiguous field: {field}",
            )

        except Exception as e:
            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="failed",
                error=f"Failed to generate clarification: {str(e)}",
            )


# =============================================================================
# Singleton
# =============================================================================

f09_clarify_question = ClarifyQuestion()
