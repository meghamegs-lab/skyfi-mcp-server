# OpenAI Integration Guide

This guide demonstrates how to use the SkyFi MCP server with OpenAI's GPT models via the OpenAI API. OpenAI supports remote MCP tools, allowing you to invoke satellite imagery functions from your Python code.

## Prerequisites

Install required packages:

```bash
pip install openai httpx python-dotenv
```

Set environment variables:

```bash
export OPENAI_API_KEY="sk-..."
export SKYFI_API_KEY="your-skyfi-api-key"
```

## How It Works

OpenAI's API accepts `mcp_tools` parameter that references remote MCP servers. When you call the API with tool_choice, OpenAI will:

1. Connect to the MCP server URL
2. Discover available tools
3. Use them within the conversation
4. Pass back tool results for processing

## Full Working Example

```python
#!/usr/bin/env python3
"""
OpenAI integration with SkyFi MCP server using tool_choice.

This example uses GPT-4 to search for satellite imagery and provide analysis.
"""

import json
import os
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# SkyFi MCP server configuration
SKYFI_MCP_URL = "https://skyfi-mcp.fly.dev/mcp"
SKYFI_API_KEY = os.getenv("SKYFI_API_KEY")

def call_gpt_with_skyfi_tools(user_message: str) -> dict:
    """
    Call GPT-4 with SkyFi MCP tools available.

    Args:
        user_message: The user's query

    Returns:
        Full API response including tool results
    """

    # Create message with MCP tools
    response = client.beta.messages.create(
        model="gpt-4",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": user_message
            }
        ],
        # Enable MCP tools from remote server
        betas=["mcp-1"],
        tools=[
            {
                "type": "mcp",
                "name": "skyfi",
                "url": SKYFI_MCP_URL,
                "headers": {
                    "Authorization": f"Bearer {SKYFI_API_KEY}"
                }
            }
        ],
        tool_choice="auto",  # Let Claude decide when to use tools
    )

    return response


def interactive_satellite_search():
    """
    Interactive loop for satellite imagery search with OpenAI.
    """

    print("SkyFi Satellite Imagery Assistant (powered by OpenAI)")
    print("=" * 50)
    print("Ask me anything about satellite imagery!\n")

    conversation_history = []

    while True:
        user_input = input("You: ").strip()

        if user_input.lower() in ["exit", "quit", "bye"]:
            print("Goodbye!")
            break

        if not user_input:
            continue

        # Add to conversation history
        conversation_history.append({
            "role": "user",
            "content": user_input
        })

        print("\nAssistant: Thinking...\n")

        # Call OpenAI with MCP tools
        response = call_gpt_with_skyfi_tools(user_input)

        # Process the response
        if response.stop_reason == "tool_use":
            # Handle tool calls
            for block in response.content:
                if hasattr(block, "text"):
                    print(f"Response: {block.text}\n")
                elif hasattr(block, "type") and block.type == "tool_use":
                    print(f"Using tool: {block.name}")
                    print(f"Input: {json.dumps(block.input, indent=2)}\n")
        else:
            # Standard response
            for block in response.content:
                if hasattr(block, "text"):
                    print(f"Response: {block.text}\n")

        # Store assistant response
        conversation_history.append({
            "role": "assistant",
            "content": response.content
        })


# Example 1: Simple synchronous call
def example_search_imagery():
    """Search for satellite imagery of a specific location."""

    response = call_gpt_with_skyfi_tools(
        "Find satellite imagery of the Suez Canal captured in the last 30 days with less than 10% cloud coverage"
    )

    print("=== Imagery Search Result ===\n")
    for block in response.content:
        if hasattr(block, "text"):
            print(block.text)
        elif hasattr(block, "type") and block.type == "tool_use":
            print(f"\nTool Used: {block.name}")
            print(f"Parameters: {json.dumps(block.input, indent=2)}")


# Example 2: Check pricing before ordering
def example_pricing_check():
    """Get pricing estimate for satellite imagery."""

    response = call_gpt_with_skyfi_tools(
        "What would it cost to get a new satellite capture of Manhattan with HIGH resolution?"
    )

    print("=== Pricing Information ===\n")
    for block in response.content:
        if hasattr(block, "text"):
            print(block.text)


# Example 3: Using streaming for real-time responses
def example_streaming_response():
    """Use streaming for real-time response output."""

    print("=== Streaming Response ===\n")

    with client.beta.messages.stream(
        model="gpt-4",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": "Find imagery of Tokyo and explain what it shows"
            }
        ],
        betas=["mcp-1"],
        tools=[
            {
                "type": "mcp",
                "name": "skyfi",
                "url": SKYFI_MCP_URL,
                "headers": {
                    "Authorization": f"Bearer {SKYFI_API_KEY}"
                }
            }
        ],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)

    print("\n")


# Example 4: Multi-step workflow with tool results
def example_order_workflow():
    """Complete workflow: search → check feasibility → order."""

    messages = [
        {
            "role": "user",
            "content": """
            I need satellite imagery of the Port of Rotterdam.
            1. First, check if fresh imagery is feasible for next week
            2. Get the pricing
            3. If under $500, proceed with the order
            4. Otherwise, just show me the existing archive imagery
            """
        }
    ]

    print("=== Order Workflow ===\n")

    # First call to initiate search
    response = client.beta.messages.create(
        model="gpt-4",
        max_tokens=2048,
        messages=messages,
        betas=["mcp-1"],
        tools=[
            {
                "type": "mcp",
                "name": "skyfi",
                "url": SKYFI_MCP_URL,
                "headers": {
                    "Authorization": f"Bearer {SKYFI_API_KEY}"
                }
            }
        ],
        tool_choice="auto",
    )

    # Print initial response
    for block in response.content:
        if hasattr(block, "text"):
            print(f"Initial Response:\n{block.text}\n")
        elif hasattr(block, "type") and block.type == "tool_use":
            print(f"Tool Used: {block.name}")
            print(f"Input: {json.dumps(block.input, indent=2)}\n")

    # Continue conversation if tools were used
    if response.stop_reason == "tool_use":
        # Add tool results back to conversation
        # (In production, you would process actual tool results here)
        messages.append({"role": "assistant", "content": response.content})

        # Follow-up request
        follow_up = client.beta.messages.create(
            model="gpt-4",
            max_tokens=2048,
            messages=messages + [
                {
                    "role": "user",
                    "content": "Great, please proceed with getting the actual pricing and feasibility scores."
                }
            ],
            betas=["mcp-1"],
            tools=[
                {
                    "type": "mcp",
                    "name": "skyfi",
                    "url": SKYFI_MCP_URL,
                    "headers": {
                        "Authorization": f"Bearer {SKYFI_API_KEY}"
                    }
                }
            ],
        )

        for block in follow_up.content:
            if hasattr(block, "text"):
                print(f"Follow-up Response:\n{block.text}\n")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "search":
            example_search_imagery()
        elif sys.argv[1] == "pricing":
            example_pricing_check()
        elif sys.argv[1] == "stream":
            example_streaming_response()
        elif sys.argv[1] == "order":
            example_order_workflow()
        else:
            print("Unknown example. Use: search, pricing, stream, or order")
    else:
        # Run interactive mode
        interactive_satellite_search()
```

## API Configuration Details

### Streamable HTTP Transport

The SkyFi MCP server uses Streamable HTTP (POST requests with JSON-RPC):

```python
# OpenAI automatically handles the transport:
tools=[
    {
        "type": "mcp",
        "name": "skyfi",
        "url": "https://skyfi-mcp.fly.dev/mcp",
        "headers": {
            "Authorization": f"Bearer {SKYFI_API_KEY}"
        }
    }
]
```

### Self-Hosted Server

If you're running your own SkyFi MCP server:

```python
tools=[
    {
        "type": "mcp",
        "name": "skyfi",
        "url": "https://your-skyfi-server.example.com/mcp",
        "headers": {
            "Authorization": f"Bearer {os.getenv('SKYFI_API_KEY')}"
        }
    }
]
```

## Tool Usage Examples

### Get Pricing with Confirmation Token

```python
# The MCP tools automatically include tools like:
# - get_pricing_options: Returns confirmation_token for orders
# - check_feasibility: Returns token for tasking orders
# - create_archive_order: Requires valid token
# - create_tasking_order: Requires valid token

response = client.beta.messages.create(
    model="gpt-4",
    messages=[
        {
            "role": "user",
            "content": "Get the price for satellite imagery of LAX Airport"
        }
    ],
    tools=[{
        "type": "mcp",
        "name": "skyfi",
        "url": SKYFI_MCP_URL,
        "headers": {"Authorization": f"Bearer {SKYFI_API_KEY}"}
    }]
)
# GPT-4 will call get_pricing_options and return pricing_token
```

### Search with Filters

```python
response = client.beta.messages.create(
    model="gpt-4",
    messages=[
        {
            "role": "user",
            "content": """
            Find satellite imagery with these filters:
            - Location: Manhattan, New York
            - Cloud cover: < 5%
            - Resolution: VERY_HIGH or ULTRA_HIGH
            - Date range: Last 7 days
            """
        }
    ],
    tools=[{
        "type": "mcp",
        "name": "skyfi",
        "url": SKYFI_MCP_URL,
        "headers": {"Authorization": f"Bearer {SKYFI_API_KEY}"}
    }]
)
```

## Error Handling

```python
try:
    response = call_gpt_with_skyfi_tools("Your query here")
except Exception as e:
    if "401" in str(e):
        print("Authentication failed. Check your SKYFI_API_KEY.")
    elif "timeout" in str(e).lower():
        print("Request timed out. Try a simpler query.")
    else:
        print(f"Error: {e}")
```

## What's Next

- **Streaming**: Use `client.beta.messages.stream()` for real-time output
- **Async Calls**: Use `AsyncOpenAI` for non-blocking requests
- **LangChain**: See [langchain-integration.md](langchain-integration.md) for agent workflows
- **Claude Integration**: See [anthropic-api-integration.md](anthropic-api-integration.md) for Anthropic API
- **Vercel AI SDK**: See [ai-sdk-integration.md](ai-sdk-integration.md) for Node.js
