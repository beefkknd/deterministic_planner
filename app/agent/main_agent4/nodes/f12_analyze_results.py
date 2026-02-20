"""
F12: Analyze Results Node

Deep LLM analysis of query results — comparisons, trends, insights.
"""

import json
from typing import Any
from langchain_core.prompts import ChatPromptTemplate

from app.agent.main_agent4.nodes import BaseWorker
from app.agent.main_agent4.state import WorkerInput, WorkerResult, create_worker_result
from app.agent.main_agent4.worker_registry import worker_tool
from app.agent.foundations.llm_service import get_llm


# =============================================================================
# System Prompt
# =============================================================================

ANALYSIS_PROMPT = """\
You are a maritime shipping data analyst.

Your task is to analyze query results and provide meaningful insights.

Guidelines:
- Identify key patterns, trends, and outliers
- For comparisons, clearly contrast the entities
- Use specific numbers and percentages from the data
- Structure your analysis with markdown headers
- Provide a brief summary at the top
- Highlight notable findings
- Be factual — only state what the data shows
"""

ANALYSIS_TEMPLATE = """\
User question: {question}

Query results:
{results}

Provide a detailed analysis of these results."""

PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", ANALYSIS_PROMPT),
    ("human", ANALYSIS_TEMPLATE)
])


# =============================================================================
# Worker Class
# =============================================================================

class AnalyzeResults(BaseWorker):
    """
    Analyze Results Worker.

    Uses LLM for deep analysis: comparisons, trends, insights.
    For queries like "compare X vs Y" or "what's the trend?"
    """

    def __init__(self):
        super().__init__("analyze_results")
        self._chain = PROMPT_TEMPLATE | get_llm()

    def _prepare_results_text(self, resolved: dict[str, Any]) -> str:
        """
        Combine available results into a text representation for the LLM.

        Args:
            resolved: Resolved inputs dict

        Returns:
            JSON string of combined results
        """
        combined = {}

        es_results = resolved.get("es_results")
        if es_results:
            combined["es_results"] = es_results

        page_results = resolved.get("page_results")
        if page_results:
            combined["page_results"] = page_results

        return json.dumps(combined, indent=2, default=str) if combined else "No results available"

    @worker_tool(
        preconditions=[
            "has es_results",
            "user intent requires analysis beyond template display",
        ],
        outputs=["analysis"],
        goal_type="deliverable",
        name="analyze_results",
        description="Deep LLM analysis of query results — comparisons, trends, insights",
        memorable_slots=[],
        synthesis_mode="narrative",
    )
    async def ainvoke(self, worker_input: WorkerInput) -> WorkerResult:
        """
        Analyze query results.

        Args:
            worker_input: WorkerInput with sub_goal and resolved_inputs

        Returns:
            WorkerResult with analysis
        """
        sub_goal = worker_input["sub_goal"]
        resolved = worker_input.get("resolved_inputs", {})

        # sub_goal["description"] contains the work instruction from F02
        question = sub_goal.get("description", "")
        results_text = self._prepare_results_text(resolved)

        if results_text == "No results available":
            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="failed",
                error="No query results provided for analysis",
            )

        try:
            analysis = await self._chain.ainvoke({
                "question": question,
                "results": results_text,
            })
            # Extract string content from AIMessage
            analysis_content = analysis.content if hasattr(analysis, 'content') else str(analysis)

            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="success",
                outputs={"analysis": analysis_content},
                message="Generated analysis of query results",
            )

        except Exception as e:
            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="failed",
                error=f"Failed to analyze results: {str(e)}",
            )


# =============================================================================
# Singleton
# =============================================================================

f12_analyze_results = AnalyzeResults()
