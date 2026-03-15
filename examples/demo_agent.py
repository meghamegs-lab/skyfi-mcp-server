#!/usr/bin/env python3
"""
SkyFi Geospatial Research Agent — A LangChain/LangGraph multi-turn agent
demonstrating the full capabilities of the SkyFi MCP server.

This agent supports complex multi-step workflows:
  1. Geocode locations to WKT format
  2. Search archive satellite imagery
  3. Check feasibility of new captures
  4. Get pricing information
  5. Place orders with human-in-loop confirmation

The agent enforces a confirmation flow before any orders are placed, ensuring
users review pricing and feasibility before charges are incurred.

Usage:
    python examples/demo_agent.py --mcp-url http://localhost:8000/mcp --model gpt-4o
    python examples/demo_agent.py --mcp-url http://localhost:8000/mcp --model claude-3-5-sonnet
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from typing import Any, Literal

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.tools import tool
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None

try:
    from langchain_anthropic import ChatAnthropic
except ImportError:
    ChatAnthropic = None

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# ──────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ──────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a geospatial research assistant powered by the SkyFi platform.
You help users find, analyze, and order satellite imagery for their research and
monitoring needs.

CAPABILITIES:
- Search archive satellite imagery (optical, SAR, multispectral)
- Check feasibility of new satellite tasking captures
- Get pricing for imagery orders
- Place satellite imagery orders
- Monitor areas of interest for new imagery
- Convert place names to coordinates and reverse geocode

IMPORTANT WORKFLOW CONSTRAINTS:
1. ALWAYS geocode location names to WKT format using geocode_location() before
   searching for imagery.
2. Before placing ANY order (archive or tasking), you MUST:
   - Get pricing using get_pricing_options() or check_feasibility()
   - Present the pricing and feasibility results to the user
   - Get explicit user confirmation
   - Use the confirmation_token from those responses when placing orders
3. Display pricing in USD and explain what the user will be charged for.
4. If the user approves an order, use the confirmation_token to call create_archive_order
   or create_tasking_order.
5. Always explain what each step does and present results clearly.

TOOL ORGANIZATION:
- Geocoding: geocode_location, reverse_geocode_location, search_nearby_pois
- Archive Search: search_archive, search_archive_next_page, get_archive_details
- Planning: check_feasibility, get_feasibility_result, predict_satellite_passes
- Pricing: get_pricing_options
- Orders: create_archive_order, create_tasking_order, list_orders, get_order_status
- Monitoring: create_aoi_notification, list_notifications, get_notification_history,
             delete_notification, check_new_images
- Account: get_account_info

START CONVERSATIONS BY:
1. Asking the user what location or area they want to monitor
2. Asking what type of imagery they need (optical, SAR, multispectral, etc.)
3. Asking their budget or timeline

Be conversational, helpful, and proactive about the confirmation flow."""


# ──────────────────────────────────────────────────────────────────────────────
# STATE TRACKING FOR CONFIRMATION FLOW
# ──────────────────────────────────────────────────────────────────────────────


class ConfirmationState:
    """Track pending confirmation tokens and orders to enforce human-in-loop."""

    def __init__(self) -> None:
        self.pending_token: str | None = None
        self.pending_context: dict[str, Any] = {}

    def set_token(self, token: str, context: dict[str, Any]) -> None:
        """Store a confirmation token and its context."""
        self.pending_token = token
        self.pending_context = context

    def clear(self) -> None:
        """Clear the pending token after order placement."""
        self.pending_token = None
        self.pending_context = {}


# ──────────────────────────────────────────────────────────────────────────────
# AGENT INITIALIZATION
# ──────────────────────────────────────────────────────────────────────────────


async def create_agent(
    mcp_url: str,
    model: str,
) -> tuple[AgentExecutor, ConfirmationState]:
    """
    Create a LangChain agent with SkyFi tools connected via MCP.

    Args:
        mcp_url: URL of the MCP server (e.g., http://localhost:8000/mcp)
        model: Model identifier ("gpt-4o", "claude-3-5-sonnet", etc.)

    Returns:
        Tuple of (AgentExecutor, ConfirmationState)

    Raises:
        ValueError: If model is not supported or MCP connection fails.
    """
    # Connect to MCP server and load SkyFi tools
    logger.info(f"Connecting to MCP server at {mcp_url}")
    async with MultiServerMCPClient(
        {
            "skyfi": {
                "url": mcp_url,
                "transport": "streamable_http",
            }
        }
    ) as client:
        mcp_tools = client.get_tools()

    logger.info(f"Loaded {len(mcp_tools)} tools from SkyFi MCP server")

    # Initialize LLM based on model name
    if model.startswith("gpt"):
        if not ChatOpenAI:
            raise ValueError(
                "langchain-openai not installed. "
                "Install with: pip install langchain-openai"
            )
        llm = ChatOpenAI(model=model, temperature=0)
        logger.info(f"Using OpenAI model: {model}")
    elif model.startswith("claude"):
        if not ChatAnthropic:
            raise ValueError(
                "langchain-anthropic not installed. "
                "Install with: pip install langchain-anthropic"
            )
        llm = ChatAnthropic(model=model, temperature=0)
        logger.info(f"Using Anthropic model: {model}")
    else:
        raise ValueError(
            f"Unsupported model: {model}. Use 'gpt-4o' or 'claude-3-5-sonnet'."
        )

    # Create agent prompt
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    # Create agent
    agent = create_tool_calling_agent(llm, mcp_tools, prompt)

    # Create executor with memory
    executor = AgentExecutor(
        agent=agent,
        tools=mcp_tools,
        verbose=True,
        max_iterations=10,
        handle_parsing_errors=True,
    )

    confirmation_state = ConfirmationState()
    return executor, confirmation_state


# ──────────────────────────────────────────────────────────────────────────────
# INTERACTIVE CHAT LOOP
# ──────────────────────────────────────────────────────────────────────────────


async def run_chat_loop(
    executor: AgentExecutor,
    confirmation_state: ConfirmationState,
) -> None:
    """
    Run an interactive chat loop with the agent.

    Args:
        executor: The LangChain agent executor
        confirmation_state: Confirmation token tracking state
    """
    chat_history: list[BaseMessage] = []

    print("\n" + "=" * 80)
    print("SkyFi Geospatial Research Agent")
    print("=" * 80)
    print("\nWelcome! I'm your SkyFi research assistant.")
    print("I can help you find, analyze, and order satellite imagery.")
    print("\nCommands:")
    print("  - Type your question or request")
    print("  - Type 'clear' to reset conversation history")
    print("  - Type 'account' to check your budget")
    print("  - Type 'quit' to exit")
    print("\n" + "=" * 80 + "\n")

    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()

            if not user_input:
                continue

            # Handle special commands
            if user_input.lower() == "quit":
                print("Goodbye!")
                break

            if user_input.lower() == "clear":
                chat_history = []
                print("Conversation history cleared.\n")
                continue

            if user_input.lower() == "account":
                user_input = "Check my account budget and remaining funds."

            # Add user message to history
            chat_history.append(HumanMessage(content=user_input))

            # Run agent
            logger.info(f"Processing user input: {user_input[:100]}")
            response = await asyncio.to_thread(
                executor.invoke,
                {
                    "input": user_input,
                    "chat_history": chat_history,
                },
            )

            agent_response = response["output"]
            logger.info(f"Agent response: {agent_response[:100]}")

            # Extract any confirmation tokens from the response
            if "confirmation_token" in agent_response:
                try:
                    # Try to parse JSON blocks in the response
                    json_start = agent_response.find("{")
                    json_end = agent_response.rfind("}") + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = agent_response[json_start:json_end]
                        parsed = json.loads(json_str)
                        if "confirmation_token" in parsed:
                            token = parsed["confirmation_token"]
                            context = {
                                "type": parsed.get("type", "order"),
                                "timestamp": json.dumps(parsed, default=str),
                            }
                            confirmation_state.set_token(token, context)
                            logger.info(f"Captured confirmation token: {token[:20]}...")
                except json.JSONDecodeError:
                    pass

            # Display response
            print(f"\nAssistant: {agent_response}\n")

            # Add assistant response to history
            from langchain_core.messages import AIMessage
            chat_history.append(AIMessage(content=agent_response))

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            logger.error(f"Error processing user input: {e}", exc_info=True)
            print(f"\nError: {e}\n")


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────


async def main(args: argparse.Namespace) -> None:
    """
    Main entry point for the agent.

    Args:
        args: Parsed command-line arguments
    """
    try:
        # Create agent
        executor, confirmation_state = await create_agent(args.mcp_url, args.model)

        # Run chat loop
        await run_chat_loop(executor, confirmation_state)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="SkyFi Geospatial Research Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using OpenAI GPT-4o (default)
  python examples/demo_agent.py

  # Using Anthropic Claude
  python examples/demo_agent.py --model claude-3-5-sonnet

  # Using custom MCP server URL
  python examples/demo_agent.py --mcp-url http://localhost:9000/mcp

  # Full example with all options
  python examples/demo_agent.py \\
    --mcp-url http://localhost:8000/mcp \\
    --model claude-3-5-sonnet
        """,
    )

    parser.add_argument(
        "--mcp-url",
        type=str,
        default="http://localhost:8000/mcp",
        help="URL of the MCP server (default: http://localhost:8000/mcp)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o",
        choices=["gpt-4o", "gpt-4-turbo", "claude-3-5-sonnet", "claude-3-opus"],
        help="LLM model to use (default: gpt-4o)",
    )

    args = parser.parse_args()

    # Run async main
    asyncio.run(main(args))
