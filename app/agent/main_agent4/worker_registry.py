"""
Worker Registry

Provides WORKER_REGISTRY and @worker_tool decorator for worker nodes.
"""

import functools
from typing import Callable, Any, Optional, Literal

from app.agent.main_agent4.state import WorkerCapability


# =============================================================================
# Global Worker Registry
# =============================================================================

WORKER_REGISTRY: list[WorkerCapability] = []


# =============================================================================
# Worker Tool Decorator
# =============================================================================

def worker_tool(
    preconditions: list[str],
    outputs: list[str],
    goal_type: Literal["support", "deliverable"],
    name: str,
    description: str,
    memorable_slots: Optional[list[str]] = None,
    synthesis_mode: Literal["narrative", "display", "hidden"] = "hidden",
) -> Callable:
    """
    Decorator to register a worker function with metadata.

    This decorator:
    1. Attaches metadata (name, description, preconditions, outputs, goal_type,
       memorable_slots, synthesis_mode)
    2. Registers the function to the global WORKER_REGISTRY

    Args:
        preconditions: List of precondition strings for F02 to evaluate
        outputs: List of output slot names this worker produces
        goal_type: "support" (intermediate data) or "deliverable" (user-facing content)
        name: Unique worker name
        description: Human-readable description
        memorable_slots: Subset of outputs to store in key_artifacts across turns.
            Defaults to [] (nothing memorable). F13 uses this.
        synthesis_mode: How F14 includes this worker's output in the final response.
            "narrative" = include in LLM synthesis prompt (prose outputs).
            "display"   = append verbatim after LLM prose (tables, lists).
            "hidden"    = exclude from final response (support workers).
            Defaults to "hidden".

    Returns:
        Decorator function

    Example:
        @worker_tool(
            preconditions=["user query is a common/general question"],
            outputs=["answer"],
            goal_type="deliverable",
            name="common_helpdesk",
            description="Answers FAQ and general assistance questions",
            memorable_slots=[],
            synthesis_mode="narrative",
        )
        async def common_helpdesk(worker_input: WorkerInput) -> WorkerResult:
            ...
    """
    def decorator(func: Callable) -> Callable:
        # Create capability entry
        capability: WorkerCapability = {
            "name": name,
            "description": description,
            "preconditions": preconditions,
            "outputs": outputs,
            "goal_type": goal_type,
            "memorable_slots": memorable_slots or [],
            "synthesis_mode": synthesis_mode,
        }

        # Register to global registry (dedup by name)
        existing_names = {cap["name"] for cap in WORKER_REGISTRY}
        if name not in existing_names:
            WORKER_REGISTRY.append(capability)

        # Attach metadata to the function
        func._worker_tool_metadata = capability

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        # Copy metadata to wrapper
        wrapper._worker_tool_metadata = func._worker_tool_metadata
        return wrapper

    return decorator


def get_worker_tool_metadata(func: Callable) -> Optional[dict[str, Any]]:
    """
    Get worker tool metadata from a function.

    Args:
        func: Function decorated with @worker_tool

    Returns:
        Metadata dict or None if not decorated
    """
    return getattr(func, "_worker_tool_metadata", None)


def get_capability_by_name(name: str) -> Optional[WorkerCapability]:
    """
    Get worker capability from registry by name.

    Args:
        name: Worker name

    Returns:
        WorkerCapability or None if not found
    """
    for cap in WORKER_REGISTRY:
        if cap["name"] == name:
            return cap
    return None
