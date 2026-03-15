# Anthropic API & Claude Code Integration Guide

This guide shows how to integrate the SkyFi MCP server with the Anthropic API (Claude) and Claude Code desktop client.

## Overview

Both Claude.com (web), Claude Code (desktop), and the Anthropic API support MCP server integration. This enables satellite imagery tools directly in your Claude conversations.

## Prerequisites

### For Claude API Integration:

```bash
pip install anthropic httpx python-dotenv
```

### For Claude Code/Desktop:

- Download [Claude Code](https://claude.com/claude-code) or use Claude Desktop
- No additional packages needed

Set environment variables:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export SKYFI_API_KEY="your-skyfi-api-key"
```

## Method 1: Claude API (Python)

### Full Working Example

```python
#!/usr/bin/env python3
"""
Anthropic API integration with SkyFi MCP server.

This example uses Claude 3.5 Sonnet with satellite imagery tools.
"""

import json
import os
from anthropic import Anthropic

# Initialize Anthropic client
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# SkyFi MCP server configuration
SKYFI_MCP_CONFIG = {
    "type": "mcp",
    "name": "skyfi",
    "url": "https://skyfi-mcp.fly.dev/mcp",
    "headers": {
        "Authorization": f"Bearer {os.getenv('SKYFI_API_KEY')}"
    }
}

def chat_with_skyfi_tools(user_message: str, conversation_history: list = None) -> str:
    """
    Chat with Claude using SkyFi MCP tools.

    Args:
        user_message: The user's query
        conversation_history: Previous messages for multi-turn conversation

    Returns:
        Claude's response as a string
    """

    if conversation_history is None:
        conversation_history = []

    # Add user message to history
    conversation_history.append({
        "role": "user",
        "content": user_message
    })

    # Call Claude with MCP tools
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2048,
        system="""You are a helpful satellite imagery assistant powered by SkyFi.

You can:
- Search for satellite imagery by location and filters
- Check pricing and feasibility of orders
- Place orders (always get user confirmation first)
- Monitor areas for new imagery

IMPORTANT WORKFLOW:
1. When searching: Use geocode_location first, then search_archive
2. Before ordering: Always use get_pricing_options or check_feasibility
3. Present pricing to the user and get explicit approval
4. Only create orders after user confirmation with a valid confirmation_token
5. For monitoring: Use create_aoi_notification and check_new_images periodically

Be conversational and helpful. Always explain what data you're getting.""",
        messages=conversation_history,
        tools=[SKYFI_MCP_CONFIG]
    )

    # Extract and return response text
    assistant_message = ""
    for block in response.content:
        if hasattr(block, "text"):
            assistant_message += block.text

    # Add assistant response to history
    conversation_history.append({
        "role": "assistant",
        "content": assistant_message
    })

    return assistant_message, conversation_history


def interactive_session():
    """Run an interactive chat session with SkyFi tools."""

    print("SkyFi Satellite Imagery Assistant (Anthropic API)")
    print("=" * 50)
    print("Ask me anything about satellite imagery!")
    print("Type 'exit' to quit\n")

    conversation_history = []

    while True:
        user_input = input("You: ").strip()

        if user_input.lower() in ["exit", "quit", "bye"]:
            print("Goodbye!")
            break

        if not user_input:
            continue

        try:
            response, conversation_history = chat_with_skyfi_tools(
                user_input,
                conversation_history
            )
            print(f"\nAssistant: {response}\n")
        except Exception as e:
            print(f"Error: {e}\n")


# Example 1: Search for imagery
def example_search():
    """Search for satellite imagery."""

    print("=== Searching for Satellite Imagery ===\n")

    response, _ = chat_with_skyfi_tools(
        "Find satellite imagery of the Suez Canal from the last 30 days with less than 10% cloud coverage. Show me the top results with pricing."
    )

    print(f"Response:\n{response}\n")


# Example 2: Check pricing and feasibility
def example_pricing():
    """Check pricing for new satellite capture."""

    print("=== Checking Pricing & Feasibility ===\n")

    response, _ = chat_with_skyfi_tools(
        "Check if it's feasible to get a fresh HIGH resolution satellite image of Manhattan. What would it cost?"
    )

    print(f"Response:\n{response}\n")


# Example 3: Multi-turn conversation
def example_multi_turn():
    """Multi-turn conversation workflow."""

    print("=== Multi-Turn Conversation ===\n")

    history = []

    # Turn 1: Search
    print("Turn 1: Searching...")
    response, history = chat_with_skyfi_tools(
        "Find satellite imagery of the Port of Rotterdam",
        history
    )
    print(f"Assistant: {response}\n")

    # Turn 2: Get more details
    print("Turn 2: Asking for details...")
    response, history = chat_with_skyfi_tools(
        "What's the pricing for the best quality image?",
        history
    )
    print(f"Assistant: {response}\n")

    # Turn 3: Check feasibility
    print("Turn 3: Checking feasibility...")
    response, history = chat_with_skyfi_tools(
        "Can you check if we can order fresh imagery instead? What would that cost?",
        history
    )
    print(f"Assistant: {response}\n")


# Example 4: Complete order workflow
def example_order_workflow():
    """Complete workflow: search → price → order."""

    print("=== Complete Order Workflow ===\n")

    history = []

    # Step 1: Search
    response, history = chat_with_skyfi_tools(
        "I need satellite imagery of Tokyo. First, find what's available.",
        history
    )
    print(f"Search Results:\n{response}\n")

    # Step 2: Get pricing
    response, history = chat_with_skyfi_tools(
        "Now get the pricing options for the best image you found.",
        history
    )
    print(f"Pricing:\n{response}\n")

    # Step 3: Simulate user approval
    response, history = chat_with_skyfi_tools(
        "The pricing looks good. The user approves the order. Proceed with the archive order using the confirmation_token.",
        history
    )
    print(f"Order Result:\n{response}\n")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "search":
            example_search()
        elif sys.argv[1] == "pricing":
            example_pricing()
        elif sys.argv[1] == "multi":
            example_multi_turn()
        elif sys.argv[1] == "order":
            example_order_workflow()
        else:
            print("Unknown example. Use: search, pricing, multi, or order")
    else:
        # Run interactive mode
        interactive_session()
```

### Basic Synchronous Usage

```python
from anthropic import Anthropic

client = Anthropic()

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": "Find satellite imagery of Paris"
        }
    ],
    tools=[
        {
            "type": "mcp",
            "name": "skyfi",
            "url": "https://skyfi-mcp.fly.dev/mcp",
            "headers": {
                "Authorization": f"Bearer {os.getenv('SKYFI_API_KEY')}"
            }
        }
    ]
)

# Extract text from response
for block in response.content:
    if hasattr(block, "text"):
        print(block.text)
```

## Method 2: Claude Code / Claude Desktop

### Configuration File

Claude uses `claude_desktop_config.json` to configure MCP servers.

**Location:**
- **Mac**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

**Configuration:**

```json
{
  "mcpServers": {
    "skyfi": {
      "type": "http",
      "url": "https://skyfi-mcp.fly.dev/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_SKYFI_API_KEY"
      }
    }
  }
}
```

**For Local/Self-Hosted Server:**

```json
{
  "mcpServers": {
    "skyfi": {
      "type": "http",
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_SKYFI_API_KEY"
      }
    }
  }
}
```

### Using in Claude Code

Once configured, you can use SkyFi tools directly in Claude Code:

1. Open a conversation in Claude Code
2. Reference satellite imagery operations naturally:

```
Find satellite imagery of the Golden Gate Bridge
```

Claude will automatically:
1. Geocode "Golden Gate Bridge"
2. Search available imagery
3. Show results with pricing

## Method 3: Claude.com Web

See [claude-web-integration.md](claude-web-integration.md) for detailed setup instructions for Claude.com.

## API Configuration Details

### Streamable HTTP Transport

SkyFi uses HTTP POST with JSON-RPC:

```python
# The MCP configuration automatically handles this
SKYFI_MCP_CONFIG = {
    "type": "mcp",
    "name": "skyfi",
    "url": "https://skyfi-mcp.fly.dev/mcp",  # Streamable HTTP endpoint
    "headers": {
        "Authorization": f"Bearer {os.getenv('SKYFI_API_KEY')}"
    }
}
```

### Authentication Header

The Bearer token is passed in the Authorization header:

```
POST https://skyfi-mcp.fly.dev/mcp
Authorization: Bearer sk_your_api_key_here
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  ...
}
```

## Error Handling

```python
from anthropic import Anthropic, APIError

client = Anthropic()

try:
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        messages=[{"role": "user", "content": "Find imagery of Tokyo"}],
        tools=[SKYFI_MCP_CONFIG]
    )
except APIError as e:
    if e.status_code == 401:
        print("Authentication failed. Check your SKYFI_API_KEY.")
    elif e.status_code == 429:
        print("Rate limited. Please wait before trying again.")
    else:
        print(f"API Error: {e}")
```

## Tool Categories Reference

All SkyFi tools are automatically available:

| Category | Tools |
|----------|-------|
| **Search** | `geocode_location`, `search_archive`, `get_archive_details` |
| **Pricing** | `get_pricing_options`, `check_feasibility`, `predict_satellite_passes` |
| **Orders** | `create_archive_order`, `create_tasking_order`, `list_orders` |
| **Monitoring** | `create_aoi_notification`, `list_notifications`, `check_new_images` |
| **Geolocation** | `reverse_geocode_location`, `search_nearby_pois` |
| **Account** | `get_account_info` |

## What's Next

- **Claude Web**: See [claude-web-integration.md](claude-web-integration.md) for web browser setup
- **LangChain**: See [langchain-integration.md](langchain-integration.md) for Python agents
- **Vercel AI SDK**: See [ai-sdk-integration.md](ai-sdk-integration.md) for Node.js applications
- **OpenAI**: See [openai-integration.md](openai-integration.md) for GPT models
- **Google ADK**: See [adk-integration.md](adk-integration.md) for Google Agent Development Kit
