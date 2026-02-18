"""
Streamlit Chat App for Deterministic Planner

Features:
- Human message input
- AI response with collapsed nodes showing current sub-node working
- Final response with collapsed steps
- Left sidebar shows Q/A history per round
- Markdown as general output format
"""

import streamlit as st
import asyncio
from typing import Optional

from app.agent.main_agent4.graph import graph
from app.agent.main_agent4.state import create_initial_state, TurnSummary
from app.agent.main_agent4.logging_config import setup_logging, get_logger, print_worker_registry

# Setup logging
setup_logging()
logger = get_logger("streamlit")


# =============================================================================
# Session State Helpers
# =============================================================================

def init_session_state():
    """Initialize Streamlit session state variables."""
    if "chat_history" not in st.session_state:
        st.session_state.chat_history: list[TurnSummary] = []
    if "current_round" not in st.session_state:
        st.session_state.current_round = 0
    if "agent_state" not in st.session_state:
        st.session_state.agent_state = None
    if "is_running" not in st.session_state:
        st.session_state.is_running = False


def add_to_history(human_msg: str, ai_msg: str, key_artifacts: Optional[str] = None):
    """Add a turn to chat history."""
    turn_id = len(st.session_state.chat_history) + 1
    st.session_state.chat_history.append({
        "turn_id": turn_id,
        "human_message": human_msg,
        "ai_response": ai_msg,
        "key_artifacts": key_artifacts,
    })


# =============================================================================
# UI Components
# =============================================================================

def render_subgoal_collapsed(subgoal: dict, expanded: bool = False):
    """Render a sub-goal as a collapsed/expanded block."""
    with st.expander(expanded=expanded):
        st.markdown(f"**[{subgoal.get('id', '?')}] {subgoal.get('worker', 'unknown')}**")
        st.markdown(f"_{subgoal.get('description', '')[:100]}..._")

        status = subgoal.get('status', 'pending')
        if status == 'success':
            st.success(f"Status: {status}")
        elif status == 'failed':
            st.error(f"Status: {status} - {subgoal.get('error', 'unknown')}")
        else:
            st.info(f"Status: {status}")

        # Show outputs if available
        result = subgoal.get('result')
        if result:
            st.json(result)


def render_agent_state(state: dict):
    """Render the current agent state with collapsible sections."""
    if not state:
        return

    # Current status
    status = state.get('status', 'unknown')
    round_num = state.get('round', 1)

    st.markdown(f"### Agent Status")
    st.markdown(f"**Round:** {round_num} | **Status:** `{status}`")

    # Current working node
    planner_reasoning = state.get('planner_reasoning', '')
    if planner_reasoning:
        st.info(f"📍 {planner_reasoning}")

    # Sub-goals
    sub_goals = state.get('sub_goals', [])
    if sub_goals:
        with st.expander(f"📋 Sub-goals ({len(sub_goals)})", expanded=False):
            for sg in sub_goals:
                render_subgoal_collapsed(sg)

    # Completed outputs
    completed = state.get('completed_outputs', {})
    if completed:
        with st.expander(f"✅ Completed Outputs ({len(completed)})", expanded=False):
            for sg_id, outputs in completed.items():
                st.markdown(f"**Sub-goal {sg_id}:**")
                st.json(outputs)


def render_final_response(state: dict):
    """Render the final response from the synthesizer."""
    final_response = state.get('final_response', '')
    if final_response:
        st.markdown("---")
        st.markdown("## Final Response")
        st.markdown(final_response)


def render_sidebar_history():
    """Render Q/A history in the left sidebar."""
    st.sidebar.title("📚 Chat History")

    if not st.session_state.chat_history:
        st.sidebar.markdown("_No conversation yet_")
        return

    for turn in st.session_state.chat_history:
        with st.sidebar.expander(f"Turn {turn['turn_id']}", expanded=False):
            st.markdown(f"**Q:** {turn['human_message'][:100]}...")
            st.markdown(f"**A:** {turn['ai_response'][:100]}...")


def run_agent(question: str):
    """
    Run the agent with the given question.

    Returns the final state after execution.
    """
    # Create initial state
    initial_state = create_initial_state(
        question=question,
        max_rounds=10,
        conversation_history=st.session_state.chat_history or None,
    )

    # Run the graph
    logger.info(f"Running agent with question: {question}")

    # Use asyncio to run the async graph
    result = asyncio.run(graph.ainvoke(initial_state))

    return result


# =============================================================================
# Main App
# =============================================================================

def main():
    st.set_page_config(
        page_title="Deterministic Planner",
        page_icon="🚢",
        layout="wide",
    )

    init_session_state()

    # Print worker registry on first run
    if "registry_printed" not in st.session_state:
        print_worker_registry()
        st.session_state.registry_printed = True

    # Title
    st.title("🚢 Deterministic Planner")
    st.markdown("Maritime Shipping Assistant with LangGraph")

    # Left sidebar
    render_sidebar_history()

    # Main chat area
    col1, col2 = st.columns([3, 1])

    with col1:
        # Display existing messages
        for turn in st.session_state.chat_history:
            with st.chat_message("user"):
                st.markdown(turn['human_message'])

            with st.chat_message("assistant"):
                st.markdown(turn['ai_response'])

        # Current agent state (if running)
        if st.session_state.is_running and st.session_state.agent_state:
            with st.chat_message("assistant"):
                render_agent_state(st.session_state.agent_state)

        # Chat input
        if prompt := st.chat_input("Ask a question about maritime shipping..."):
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)

            # Run agent
            st.session_state.is_running = True
            st.session_state.agent_state = None

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        result = run_agent(prompt)

                        # Display results
                        render_agent_state(result)
                        render_final_response(result)

                        # Get final response for history
                        final_resp = result.get('final_response', 'Agent completed but no response generated')

                        # Add to history
                        add_to_history(prompt, final_resp)

                        st.session_state.agent_state = None
                        st.session_state.is_running = False

                        # Force rerun to update UI
                        st.rerun()

                    except Exception as e:
                        st.error(f"Error: {str(e)}")
                        logger.error(f"Agent error: {str(e)}")
                        st.session_state.is_running = False

    with col2:
        # Info panel
        st.markdown("### ℹ️ Info")
        st.markdown(f"**Rounds:** {st.session_state.current_round}")
        st.markdown(f"**History:** {len(st.session_state.chat_history)} turns")

        if st.button("Clear History"):
            st.session_state.chat_history = []
            st.session_state.current_round = 0
            st.rerun()


if __name__ == "__main__":
    main()
