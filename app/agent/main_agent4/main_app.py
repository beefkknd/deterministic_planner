"""
Simple Chat App for Deterministic Planner Agent

Interactive CLI chat interface that:
- Runs in a while loop for continuous conversation
- Manages chat_hist: list[TurnSummary]
- Invokes the agent graph for each user message
"""

import asyncio
from app.agent.main_agent4.graph import graph
from app.agent.main_agent4.state import create_initial_state, TurnSummary


async def run_chat():
    """Run the interactive chat loop."""
    chat_hist: list[TurnSummary] = []
    turn_id = 1

    print("=" * 60)
    print("Maritime Shipping Assistant - Chat")
    print("Type 'quit' or 'exit' to end the conversation")
    print("=" * 60)
    print()

    while True:
        # Get user input
        user_input = input("You: ").strip()

        # Check for exit commands
        if user_input.lower() in ("quit", "exit", "q"):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        # Create initial state with conversation history
        initial_state = create_initial_state(
            question=user_input,
            max_rounds=10,
            conversation_history=chat_hist,
        )

        try:
            # Invoke the agent graph
            print("\n[Agent is thinking...]\n")
            result = await graph.ainvoke(initial_state)

            # Get the final response
            ai_response = result.get("final_response", "")

            # Handle failure states
            if result.get("status") == "failed":
                ai_response = (
                    f"I encountered an error: {result.get('planner_reasoning', 'Unknown error')}"
                )

            # Display response
            print(f"Agent: {ai_response}\n")

            # Update chat history
            chat_hist.append({
                "turn_id": turn_id,
                "human_message": user_input,
                "ai_response": ai_response,
                "key_artifacts": None,
            })
            turn_id += 1

        except Exception as e:
            print(f"\nError: {str(e)}\n")

        print("-" * 60)


if __name__ == "__main__":
    asyncio.run(run_chat())
