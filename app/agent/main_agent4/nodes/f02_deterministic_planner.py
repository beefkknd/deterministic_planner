"""
F02: Deterministic Planner Node

Central orchestrator. Each round: reads worker registry, checks preconditions,
creates sub-goals with InputRef wiring to completed goals, decides
continue/done/failed. NOT a worker — operates on MainState directly.

Uses Pydantic structured output for reliable LLM response parsing.
"""

import json
from typing import Any, Literal
from pydantic import BaseModel, Field

from app.agent.main_agent4.state import (
    MainState, SubGoal, InputRef,
    create_sub_goal,
)
from app.agent.main_agent4.worker_registry import WORKER_REGISTRY
from app.agent.main_agent4.logging_config import get_logger
from app.agent.foundations.llm_service import LLMService

logger = get_logger("f02_planner")


# =============================================================================
# Pydantic Output Types
# =============================================================================

class PlannedInputRef(BaseModel):
    """Reference to an output slot from a completed or planned sub-goal."""
    from_sub_goal: int = Field(description="ID of the source sub-goal")
    slot: str = Field(description="Output slot name from the source sub-goal")


class PlannedSubGoal(BaseModel):
    """A sub-goal the planner wants to dispatch."""
    worker: str = Field(description="Worker name from the registry")
    description: str = Field(description="Human-readable task description")
    inputs: dict[str, PlannedInputRef] = Field(
        default_factory=dict,
        description="Named inputs wired from other sub-goals via InputRef",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional static parameters for the worker",
    )
    goal_type: Literal["support", "deliverable"] = Field(
        description="Whether this produces intermediate data or user-facing content",
    )


class PlannerDecision(BaseModel):
    """The planner's decision for the current round."""
    action: Literal["continue", "done", "failed"] = Field(
        description=(
            "continue = dispatch sub-goals, "
            "done = all deliverables satisfied, "
            "failed = unrecoverable"
        ),
    )
    reasoning: str = Field(
        description="Human-readable explanation for the decision",
    )
    sub_goals: list[PlannedSubGoal] = Field(
        default_factory=list,
        description="Sub-goals to dispatch (only when action=continue)",
    )
    synthesis_inputs: dict[str, PlannedInputRef] = Field(
        default_factory=dict,
        description="References for the synthesizer (only when action=done)",
    )


# =============================================================================
# System Prompt
# =============================================================================

PLANNER_SYSTEM_PROMPT = """\
You are the deterministic planner for a maritime shipping assistant.

Your job: given a user goal and the current execution state, decide the NEXT action.

## Available Workers

{worker_registry}

## Rules

1. PRECONDITIONS: Never dispatch a worker whose preconditions aren't met by \
completed_outputs or the user query itself.

2. DEPENDENCY WIRING: When a new sub-goal needs output from a completed \
sub-goal, wire it via inputs with from_sub_goal (the completed goal's ID) \
and slot (the output slot name). This is how data flows between rounds.

3. ROUND BUDGET: You are on round {round} of {max_rounds}. Plan efficiently.

4. AMBIGUITY: If a worker reports ambiguity, decide:
   - Low confidence (< 0.6): dispatch clarify_question
   - High confidence (>= 0.6): proceed with best guess

5. PARTIAL SUCCESS: If some deliverables succeeded and others failed after \
retries, you may declare "done" with partial results.

6. FIRST ROUND: For the first round, analyze the user goal and choose the \
right starting workers. FAQ questions → common_helpdesk. Data queries → \
metadata_lookup first.

7. WIRING BETWEEN ROUNDS: When creating sub-goals that depend on outputs \
from previous rounds, always set inputs with the correct from_sub_goal ID \
and slot name matching the completed sub-goal's output.

8. PENDING SUB-GOALS: Sub-goals listed as "pending" were already created \
in a previous round but are waiting for their input dependencies to be \
satisfied. Do NOT create new sub-goals that duplicate pending ones. \
They will be dispatched automatically once their dependencies are met. \
Only create new sub-goals for work that is NOT already covered by \
pending sub-goals.
"""

PLANNER_TEMPLATE = """\
User goal: {question}

Completed sub-goals and their outputs:
{completed_context}

Failed sub-goals:
{failed_context}

Pending sub-goals (awaiting dependencies):
{pending_context}

Current round: {round} / {max_rounds}

Decide the next action."""


# =============================================================================
# Helpers
# =============================================================================

def _format_worker_registry() -> str:
    """Format WORKER_REGISTRY into a readable string for the LLM."""
    lines = []
    for w in WORKER_REGISTRY:
        lines.append(
            f"- {w['name']} ({w['goal_type']}): {w['description']}\n"
            f"  preconditions: {w['preconditions']}\n"
            f"  outputs: {w['outputs']}"
        )
    return "\n".join(lines)


def _format_completed_context(state: MainState) -> str:
    """Format completed sub-goals with their outputs for the planner."""
    completed = [
        sg for sg in state["sub_goals"] if sg["status"] == "success"
    ]
    if not completed:
        return "(none yet)"

    lines = []
    for sg in completed:
        outputs = state["completed_outputs"].get(sg["id"], {})
        truncated = {}
        for k, v in outputs.items():
            s = str(v)
            truncated[k] = s[:200] + "..." if len(s) > 200 else s
        lines.append(
            f"- sub_goal {sg['id']} ({sg['worker']}): {sg['description']}\n"
            f"  outputs: {json.dumps(truncated)}"
        )
    return "\n".join(lines)


def _format_failed_context(state: MainState) -> str:
    """Format failed sub-goals with their errors for the planner."""
    failed = [
        sg for sg in state["sub_goals"] if sg["status"] == "failed"
    ]
    if not failed:
        return "(none)"

    lines = []
    for sg in failed:
        lines.append(
            f"- sub_goal {sg['id']} ({sg['worker']}): "
            f"{sg.get('error', 'unknown error')}"
        )
    return "\n".join(lines)


def _format_pending_context(state: MainState) -> str:
    """
    Format pending sub-goals that are awaiting dependencies.

    This helps F02 avoid duplicate dispatch — it can see what was already
    planned but hasn't run yet due to unmet dependencies.
    """
    pending = [
        sg for sg in state["sub_goals"] if sg["status"] == "pending"
    ]
    if not pending:
        return "(none)"

    lines = []
    for sg in pending:
        inputs = sg.get("inputs", {})
        if inputs:
            input_deps = ", ".join(
                f"{name}: from sg{ref['from_sub_goal']}.{ref['slot']}"
                for name, ref in inputs.items()
            )
            lines.append(
                f"- sub_goal {sg['id']} ({sg['worker']}): {sg['description']}\n"
                f"  waiting for: {input_deps}"
            )
        else:
            lines.append(
                f"- sub_goal {sg['id']} ({sg['worker']}): {sg['description']}"
            )
    return "\n".join(lines)


def _next_sub_goal_id(state: MainState) -> int:
    """Get the next available sub-goal ID."""
    if not state["sub_goals"]:
        return 1
    return max(sg["id"] for sg in state["sub_goals"]) + 1


def _convert_planned_sub_goals(
    planned: list[PlannedSubGoal],
    id_start: int,
    existing_sub_goals: list[SubGoal],
    completed_outputs: dict[int, dict[str, Any]],
) -> list[SubGoal]:
    """
    Convert Pydantic PlannedSubGoal list into SubGoal TypedDicts.

    Assigns sequential IDs starting from id_start. Converts PlannedInputRef
    objects into InputRef TypedDicts so outputs from completed goals wire
    into the new goal's inputs.

    Validates that InputRef targets exist (both existing sub-goals and new ones
    being created in the same batch).

    Args:
        planned: LLM-produced sub-goal models
        id_start: Starting ID for new sub-goals
        existing_sub_goals: List of existing sub-goals to validate InputRefs against
        completed_outputs: Map of completed sub-goal IDs to their output slots

    Returns:
        List of SubGoal dicts ready for state
    """
    # Build set of valid IDs: existing sub-goals + new ones being created
    existing_ids = {sg["id"] for sg in existing_sub_goals}
    new_ids = {id_start + i for i in range(len(planned))}
    valid_ids = existing_ids | new_ids

    # Build map of existing outputs for slot validation
    # For completed sub-goals, use actual runtime outputs; for others, use declared
    existing_outputs = {
        sg["id"]: (
            set(completed_outputs[sg["id"]].keys())
            if sg["id"] in completed_outputs
            else set(sg.get("outputs", []))
        )
        for sg in existing_sub_goals
    }

    registry_outputs = {
        w["name"]: w["outputs"] for w in WORKER_REGISTRY
    }

    # Pre-compute declared outputs for NEW sub-goals being created in this batch
    # This allows validating InputRefs between sub-goals in the same batch
    new_declared_outputs: dict[int, set[str]] = {}
    for i, p in enumerate(planned):
        new_id = id_start + i
        declared = registry_outputs.get(p.worker, [])
        new_declared_outputs[new_id] = set(declared)

    result = []
    failed_sub_goals = []
    for i, p in enumerate(planned):
        # Validate InputRefs - fail the sub-goal if any InputRef is invalid
        inputs: dict[str, InputRef] = {}
        input_error = None

        for name, ref in p.inputs.items():
            from_id = ref.from_sub_goal
            slot = ref.slot

            # Check ID exists
            if from_id not in valid_ids:
                input_error = f"Invalid InputRef: sub_goal {from_id} does not exist"
                break

            # Check slot exists in the source sub-goal
            # Check against both existing sub-goals AND new sub-goals in this batch
            valid_slots: set[str] = set()
            if from_id in existing_outputs:
                valid_slots = existing_outputs[from_id]
            elif from_id in new_declared_outputs:
                valid_slots = new_declared_outputs[from_id]

            if valid_slots and slot not in valid_slots:
                input_error = f"Invalid InputRef: slot '{slot}' not found in sub_goal {from_id}"
                break

            inputs[name] = {"from_sub_goal": from_id, "slot": slot}

        declared_outputs = registry_outputs.get(p.worker, [])

        # If any InputRef was invalid, mark the sub-goal as failed
        if input_error:
            sg = create_sub_goal(
                id=id_start + i,
                worker=p.worker,
                description=p.description,
                goal_type=p.goal_type,
                inputs=None,
                params=p.params if p.params else None,
                outputs=declared_outputs if declared_outputs else None,
            )
            # Set status and error after creation (create_sub_goal doesn't accept these params)
            sg["status"] = "failed"
            sg["error"] = input_error
            failed_sub_goals.append(sg)
            continue

        sg = create_sub_goal(
            id=id_start + i,
            worker=p.worker,
            description=p.description,
            goal_type=p.goal_type,
            inputs=inputs if inputs else None,
            params=p.params if p.params else None,
            outputs=declared_outputs if declared_outputs else None,
        )
        result.append(sg)

    # Return both successful and failed sub-goals
    return result + failed_sub_goals


# =============================================================================
# Node Class
# =============================================================================

class DeterministicPlanner:
    """
    F02: Deterministic Planner.

    Central orchestrator that creates sub-goals with InputRef wiring.
    Structured chain is built once at init with PlannerDecision schema.
    System prompt is rebuilt per-call (includes dynamic round/registry info).
    """

    def __init__(self):
        self._llm_service = LLMService.get_instance()

    async def ainvoke(self, state: MainState) -> MainState:
        """
        Plan the next round of sub-goals.

        Reads current state, calls LLM with structured output to get a
        PlannerDecision, creates sub-goals with InputRef wiring to
        completed goals, returns new state.

        Args:
            state: Current MainState

        Returns:
            New MainState with appended sub-goals and updated status/reasoning
        """
        current_round = state.get("round", 1)
        max_rounds = state.get("max_rounds", 10)

        logger.info(f"F02: === Round {current_round}/{max_rounds} ===")

        if current_round > max_rounds:
            logger.error(f"F02: Exceeded max rounds ({max_rounds})")
            return {
                **state,
                "status": "failed",
                "planner_reasoning": (
                    f"F02: Exceeded max rounds ({max_rounds})"
                ),
            }

        question = state.get("question", "")
        if not question:
            logger.error("F02: No question available")
            return {
                **state,
                "status": "failed",
                "planner_reasoning": "F02: No question available",
            }

        try:
            # System prompt changes per round (round number, registry snapshot)
            system_prompt = PLANNER_SYSTEM_PROMPT.format(
                worker_registry=_format_worker_registry(),
                round=current_round,
                max_rounds=max_rounds,
            )

            chain = self._llm_service.create_structured_chain(
                system_message=system_prompt,
                prompt_template=PLANNER_TEMPLATE,
                output_schema=PlannerDecision,
            )

            decision: PlannerDecision = await chain.ainvoke({
                "question": question,
                "completed_context": _format_completed_context(state),
                "failed_context": _format_failed_context(state),
                "pending_context": _format_pending_context(state),
                "round": str(current_round),
                "max_rounds": str(max_rounds),
            })

            reasoning = decision.reasoning
            logger.info(f"F02: Decision={decision.action}, reasoning={reasoning[:100]}...")

            if decision.action == "continue":
                if not decision.sub_goals:
                    logger.error("F02: 'continue' but no sub-goals planned")
                    return {
                        **state,
                        "status": "failed",
                        "planner_reasoning": (
                            f"F02: 'continue' with no sub-goals — {reasoning}"
                        ),
                    }

                id_start = _next_sub_goal_id(state)
                new_sub_goals = _convert_planned_sub_goals(
                    decision.sub_goals,
                    id_start,
                    state["sub_goals"],
                    state.get("completed_outputs", {}),
                )

                # Log created sub-goals
                for sg in new_sub_goals:
                    if sg["status"] == "failed":
                        logger.error(f"F02: Sub-goal {sg['id']} FAILED - {sg.get('error', 'unknown')}")
                    else:
                        logger.info(f"F02: Created sub-goal {sg['id']}: {sg['worker']} - {sg['description'][:50]}...")

                return {
                    **state,
                    "sub_goals": state["sub_goals"] + new_sub_goals,
                    "status": "executing",
                    "round": current_round,
                    "planner_reasoning": (
                        f"F02 (round {current_round}): {reasoning}"
                    ),
                }

            elif decision.action == "done":
                logger.info(f"F02: Action=done, synthesizing results")
                # Validate synthesis_inputs - must reference completed sub-goals
                completed = state.get("completed_outputs", {})
                validated_inputs: dict[str, InputRef] = {}
                for name, ref in decision.synthesis_inputs.items():
                    from_id = ref.from_sub_goal
                    slot = ref.slot
                    # Check that the referenced sub-goal has the required output slot
                    if from_id in completed and slot in completed[from_id]:
                        validated_inputs[name] = {
                            "from_sub_goal": from_id,
                            "slot": slot,
                        }
                    else:
                        logger.warning(f"F02: Skipping invalid synthesis input: {name} -> sg{from_id}.{slot}")

                return {
                    **state,
                    "status": "done",
                    "synthesis_inputs": validated_inputs,
                    "planner_reasoning": (
                        f"F02 (round {current_round}): {reasoning}"
                    ),
                }

            else:  # "failed"
                return {
                    **state,
                    "status": "failed",
                    "planner_reasoning": (
                        f"F02 (round {current_round}): {reasoning}"
                    ),
                }

        except Exception as e:
            return {
                **state,
                "status": "failed",
                "planner_reasoning": f"F02: Unexpected error — {str(e)}",
            }


# =============================================================================
# Singleton
# =============================================================================

f02_planner = DeterministicPlanner()
