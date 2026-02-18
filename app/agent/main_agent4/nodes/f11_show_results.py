"""
F11: Show Results Node

Template-based rendering of ES query results. No LLM involved.
"""

from typing import Any
from app.agent.main_agent4.nodes import BaseWorker
from app.agent.main_agent4.state import WorkerInput, WorkerResult, create_worker_result
from app.agent.main_agent4.worker_registry import worker_tool


# =============================================================================
# Template Helpers
# =============================================================================

def _format_as_markdown_table(hits: list[dict[str, Any]]) -> str:
    """
    Format ES hits as a markdown table.

    Args:
        hits: List of ES hit dicts (each with _source)

    Returns:
        Markdown table string
    """
    if not hits:
        return "_No results found._"

    # Extract source fields from hits
    rows = [hit.get("_source", hit) for hit in hits]
    if not rows:
        return "_No results found._"

    # Collect all column names
    columns = list(dict.fromkeys(
        col for row in rows for col in row.keys()
    ))

    # Build header
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"

    # Build rows
    body_lines = []
    for row in rows:
        values = [str(row.get(col, "")) for col in columns]
        body_lines.append("| " + " | ".join(values) + " |")

    return "\n".join([header, separator] + body_lines)


def _format_aggregations(aggs: dict[str, Any]) -> str:
    """
    Format ES aggregation results as markdown.

    Args:
        aggs: ES aggregation response

    Returns:
        Markdown formatted string
    """
    if not aggs:
        return "_No aggregation results._"

    lines = []
    for agg_name, agg_data in aggs.items():
        lines.append(f"### {agg_name}")
        buckets = agg_data.get("buckets", [])
        if buckets:
            lines.append("| Key | Count |")
            lines.append("| --- | --- |")
            for bucket in buckets:
                lines.append(f"| {bucket.get('key', '')} | {bucket.get('doc_count', 0)} |")
        else:
            value = agg_data.get("value")
            if value is not None:
                lines.append(f"**Value:** {value}")
        lines.append("")

    return "\n".join(lines)


# =============================================================================
# Worker Class
# =============================================================================

class ShowResults(BaseWorker):
    """
    Show Results Worker.

    Template-based rendering of ES query results into markdown.
    No LLM — saves tokens for straightforward display.
    """

    def __init__(self):
        super().__init__("show_results")

    @worker_tool(
        preconditions=["has es_results to display"],
        outputs=["formatted_results"],
        goal_type="deliverable",
        name="show_results",
        description="Template-based rendering of ES query results (no LLM)"
    )
    async def ainvoke(self, worker_input: WorkerInput) -> WorkerResult:
        """
        Render ES results as formatted markdown.

        Args:
            worker_input: WorkerInput with sub_goal and resolved_inputs

        Returns:
            WorkerResult with formatted_results
        """
        sub_goal = worker_input["sub_goal"]
        resolved = worker_input.get("resolved_inputs", {})

        es_results = resolved.get("es_results") or resolved.get("page_results")

        if es_results is None:
            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="failed",
                error="No ES results provided to display"
            )

        try:
            # Handle both search hits and aggregation results
            if isinstance(es_results, dict):
                hits = es_results.get("hits", {}).get("hits", [])
                aggs = es_results.get("aggregations")
            elif isinstance(es_results, list):
                hits = es_results
                aggs = None
            else:
                hits = []
                aggs = None

            parts = []

            if hits:
                parts.append(_format_as_markdown_table(hits))
                parts.append(f"\n_Showing {len(hits)} result(s)._")

            if aggs:
                parts.append(_format_aggregations(aggs))

            if not parts:
                parts.append("_No results to display._")

            formatted = "\n\n".join(parts)

            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="success",
                outputs={"formatted_results": formatted},
                message=f"Rendered {len(hits)} results as markdown"
            )

        except Exception as e:
            return create_worker_result(
                sub_goal_id=sub_goal["id"],
                status="failed",
                error=f"Failed to render results: {str(e)}"
            )


# =============================================================================
# Singleton
# =============================================================================

f11_show_results = ShowResults()
