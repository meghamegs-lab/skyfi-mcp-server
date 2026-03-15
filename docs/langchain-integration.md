# LangChain Integration Guide

This guide shows how to integrate the SkyFi MCP server with LangChain using the `langchain-mcp-adapters` package to access satellite imagery tools from Python agents.

## Prerequisites

Install required packages:

```bash
pip install langchain-mcp-adapters langchain-core langchain-openai langchain-anthropic httpx
```

## Quick Start

### 1. Set Up Your API Keys

**For cloud mode** (remote SkyFi MCP server):
```bash
export SKYFI_API_KEY="your-skyfi-api-key-here"
export OPENAI_API_KEY="your-openai-api-key-here"  # or ANTHROPIC_API_KEY
```

**For local mode** (stdio transport):
```bash
# Create ~/.skyfi/config.json with:
{
  "api_key": "your-skyfi-api-key"
}

# Install skyfi-mcp locally:
pip install skyfi-mcp
```

### 2. Full Working Example

```python
#!/usr/bin/env python3
"""
LangChain integration with SkyFi MCP server.

This example uses the Anthropic API with SkyFi tools to:
1. Geocode a location name to coordinates
2. Search for satellite imagery in that area
3. Get pricing before placing orders
"""

import json
import os
from langchain_mcp_adapters import StdioMCPToolProvider, HttpMCPToolProvider
from langchain_anthropic import ChatAnthropic
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate

# Configure the SkyFi MCP server connection
# For REMOTE (Streamable HTTP) mode:
skyfi_provider = HttpMCPToolProvider(
    url="https://skyfi-mcp.fly.dev/mcp",  # or your custom instance
    headers={
        "Authorization": f"Bearer {os.getenv('SKYFI_API_KEY')}"
    }
)

# For LOCAL (stdio) mode, uncomment instead:
# skyfi_provider = StdioMCPToolProvider(
#     command="skyfi-mcp",
#     args=["serve", "--transport", "stdio"],
# )

# Load all SkyFi tools
tools = skyfi_provider.get_tools()

# Initialize an LLM (Anthropic Claude)
llm = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    temperature=0.7,
    api_key=os.getenv("ANTHROPIC_API_KEY")
)

# Create the agent
agent_prompt = PromptTemplate.from_template("""You are a helpful satellite imagery assistant powered by SkyFi.

You can:
- Geocode locations and search for satellite imagery
- Check pricing and feasibility of orders
- Place orders after user confirmation
- Monitor areas of interest for new imagery

When a user asks about satellite imagery:
1. Use geocode_location to convert place names to coordinates
2. Use search_satellite_imagery to find available imagery
3. Use preview_order to get costs and get a confirmation_token
4. Present findings to the user and get approval before ordering
5. Use confirm_order with the confirmation_token to place the order

IMPORTANT: Never place orders without explicit user approval and a valid confirmation_token.

Available tools: {tools}

Question: {input}
{agent_scratchpad}""")

agent = create_react_agent(llm, tools, agent_prompt)
agent_executor = AgentExecutor.from_agent_and_tools(
    agent=agent,
    tools=tools,
    verbose=True,
    max_iterations=10,
)

# Example usage
if __name__ == "__main__":
    # Example 1: Search for imagery
    result = agent_executor.invoke({
        "input": "Find satellite imagery of the Suez Canal from the last 30 days with cloud coverage less than 10%"
    })
    print(json.dumps(result, indent=2))

    # Example 2: Check pricing before ordering
    result = agent_executor.invoke({
        "input": "What would it cost to get new satellite imagery of LAX Airport?"
    })
    print(json.dumps(result, indent=2))

    # Example 3: Monitor an area
    result = agent_executor.invoke({
        "input": "Set up monitoring for the Port of Rotterdam to alert me when new imagery is available"
    })
    print(json.dumps(result, indent=2))
```

### 3. Using with LangGraph (Multi-Step Workflows)

For more complex workflows with state management:

```python
from langgraph.graph import StateGraph
from langgraph.prebuilt import create_react_agent
from typing import Any, Dict, List

# Build a state-based workflow
workflow = StateGraph(state_schema=Dict[str, Any])

# Add nodes for different stages
workflow.add_node("geocode", lambda state: {
    **state,
    "aoi": run_tool(tools, "geocode_location", state["location"])
})

workflow.add_node("search", lambda state: {
    **state,
    "results": run_tool(tools, "search_satellite_imagery", state["aoi"])
})

workflow.add_node("pricing", lambda state: {
    **state,
    "pricing": run_tool(tools, "preview_order", state["aoi"])
})

workflow.add_edge("geocode", "search")
workflow.add_edge("search", "pricing")

graph = workflow.compile()

# Run the workflow
output = graph.invoke({"location": "Manhattan, New York"})
print(json.dumps(output, indent=2))
```

## Key Concepts

### Authentication

- **Cloud Mode**: Pass API key via `Authorization: Bearer` header
- **Local Mode**: Use `~/.skyfi/config.json` with `skyfi_api_key` field
- Tools automatically use whichever is configured

### Tool Categories

**Search & Discovery**
- `geocode_location` - Convert place names to WKT coordinates
- `search_satellite_imagery` - Find archived satellite imagery with auto-geocoding support
- `search_nearby_pois` - Find points of interest

**Pricing & Ordering**
- `preview_order` - Get pricing options and confirmation token
- `confirm_order` - Place orders (archive or tasking) with confirmation_token
- `check_feasibility` - Check if tasking order is feasible (auto-polls)

**Orders & Downloads**
- `check_order_status` - View order history or track specific order progress
- `get_download_url` - Get download links for imagery

**Monitoring**
- `setup_area_monitoring` - Create/list/history/delete area monitoring
- `check_new_images` - Check for new imagery from monitors

**Geolocation**
- `search_nearby_pois` - Find points of interest

**Account**
- `get_account_info` - Check budget and usage

**Pricing Overview**
- `get_pricing_overview` - Get general pricing questions answered

### Confirmation Tokens

Orders require a `confirmation_token` from `preview_order`. The flow is:
1. `search_satellite_imagery` → find images (auto-geocodes if needed)
2. `preview_order` → get exact pricing + confirmation_token
3. Present price to user and get approval
4. `confirm_order` → place order (archive or tasking) with confirmation_token

Always present pricing/feasibility results to the user and get explicit approval before using the token.

## Error Handling

```python
try:
    result = agent_executor.invoke({
        "input": "Your query here"
    })
except Exception as e:
    print(f"Error: {e}")
    # Handle authentication errors
    if "401" in str(e) or "Unauthorized" in str(e):
        print("Check your SKYFI_API_KEY")
    # Handle tool errors
    elif "aoi" in str(e):
        print("Make sure to geocode the location first")
```

## What's Next

- **Streaming Results**: Use `agent_executor.stream()` for real-time output
- **Custom Tools**: Extend with your own post-processing logic
- **Database Storage**: Store orders and notifications in a database
- **Claude Web Integration**: See [claude-web-integration.md](claude-web-integration.md) for browser-based access
- **OpenAI Integration**: See [openai-integration.md](openai-integration.md) for OpenAI API usage
