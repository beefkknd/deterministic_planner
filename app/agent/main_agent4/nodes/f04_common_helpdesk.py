"""
F04: Common Helpdesk Node

Answers FAQ and general assistance questions.
"""

from typing import Optional
from langchain_core.prompts import ChatPromptTemplate

from app.agent.main_agent4.nodes import BaseWorker
from app.agent.main_agent4.state import WorkerInput, WorkerResult, create_worker_result
from app.agent.main_agent4.worker_registry import worker_tool
from app.agent.foundations.llm_service import get_llm


# =============================================================================
# System Prompt
# =============================================================================

SYSTEM_PROMPT = """You are a helpful maritime shipping assistant.

Your role is to answer general questions about shipping, logistics, and maritime terms.

Guidelines:
- Be concise and informative
- Use clear, simple language
- If you don't know something, say so
- Focus on factual information about shipping concepts
"""

PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "{question}")
])


# =============================================================================
# FAQ Knowledge Base
# =============================================================================

FAQ_ANSWERS = {
    "shipment": "A shipment refers to goods being transported from an origin location to a destination. In maritime shipping, a shipment typically includes information about the container, shipper, consignee, origin/destination ports, and transit details.",

    "container": "A container is a standardized metal box used for transporting goods. Common sizes include 20ft and 40ft containers. They come in various types: dry, refrigerated (reefer), open-top, and flat rack.",

    "shipper": "The shipper is the person or company who sends goods. They are responsible for preparing the cargo for shipment and providing shipping documentation.",

    "consignee": "The consignee is the person or company who receives the shipment. They are typically listed on the bill of lading and are responsible for taking delivery of the cargo.",

    "bill of lading": "A bill of lading (BOL) is a legal document between the shipper and carrier detailing the type, quantity, and destination of goods. It serves as a receipt of shipment and a document of title.",

    "teu": "TEU stands for Twenty-foot Equivalent Unit. It's the standard unit for measuring container capacity. A 20ft container = 1 TEU, a 40ft container = 2 TEU.",

    "port of loading": "The port where cargo is loaded onto the vessel for transport.",

    "port of discharge": "The port where cargo is unloaded from the vessel at the destination.",

    "eta": "ETA stands for Estimated Time of Arrival. It's the predicted date and time when a vessel is expected to arrive at its destination.",

    "transit time": "Transit time is the duration from when cargo leaves the origin port to when it arrives at the destination port.",

    "freight": "Freight refers to the goods being transported, or the cost of transporting goods. Freight charges are based on factors like weight, volume, distance, and container type.",
}


# =============================================================================
# Worker Class
# =============================================================================

class CommonHelpdesk(BaseWorker):
    """
    Common Helpdesk Worker.

    Answers FAQ and general assistance questions using LLM and knowledge base.
    """

    def __init__(self):
        super().__init__("common_helpdesk")
        self._chain = PROMPT_TEMPLATE | get_llm()

    @worker_tool(
        preconditions=["user query is a common/general question"],
        outputs=["answer"],
        goal_type="deliverable",
        name="common_helpdesk",
        description="Answers FAQ and general assistance questions",
    )
    async def ainvoke(self, worker_input: WorkerInput) -> WorkerResult:
        """
        Answer a general shipping question.

        Args:
            worker_input: WorkerInput with sub_goal and resolved_inputs

        Returns:
            WorkerResult with answer
        """
        sub_goal = worker_input["sub_goal"]
        question = sub_goal.get("description", "")

        if not question:
            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="failed",
                error="No question provided",
            )

        try:
            # Try FAQ first
            question_lower = question.lower()
            for key, answer in FAQ_ANSWERS.items():
                if key in question_lower:
                    return create_worker_result(
                        sub_goal_id=sub_goal["id"],
                        status="success",
                        outputs={"answer": answer},
                        message=f"Found FAQ match for '{key}'",
                    )

            # Fall back to LLM
            response: str = await self._chain.ainvoke({"question": question})

            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="success",
                outputs={"answer": response},
                message="Generated answer via LLM",
            )

        except Exception as e:
            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="failed",
                error=f"Failed to generate answer: {str(e)}",
            )


# =============================================================================
# Singleton
# =============================================================================

common_helpdesk = CommonHelpdesk()
f04_common_helpdesk = common_helpdesk  # Alias for import compatibility
