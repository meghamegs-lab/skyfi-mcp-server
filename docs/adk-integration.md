# Google ADK (Agent Development Kit) Integration Guide

This guide shows how to integrate the SkyFi MCP server with Google's Agent Development Kit (ADK) for building AI agents with satellite imagery capabilities.

## Prerequisites

Install required packages:

```bash
pip install google-cloud-aiplatform google-genai httpx
```

Set environment variables:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
export SKYFI_API_KEY="your-skyfi-api-key"
```

## Configuration

### Step 1: Create MCPToolset for SkyFi

The ADK uses `MCPToolset` to wrap remote MCP servers. Create a configuration file:

**skyfi_tools.py**

```python
"""SkyFi MCP tools configuration for Google ADK."""

from google.genai.adk import MCPToolset

# Create toolset pointing to SkyFi MCP server
skyfi_toolset = MCPToolset(
    name="skyfi",
    server_url="https://skyfi-mcp.fly.dev/mcp",
    auth_headers={
        "Authorization": f"Bearer {os.getenv('SKYFI_API_KEY')}"
    },
    description="Access satellite imagery from SkyFi platform",
)

# For local/self-hosted server:
# skyfi_toolset = MCPToolset(
#     name="skyfi_local",
#     server_url="http://localhost:8000/mcp",
#     auth_headers={
#         "Authorization": f"Bearer {os.getenv('SKYFI_API_KEY')}"
#     },
# )
```

### Step 2: Minimal Agent Example

**agent.py**

```python
#!/usr/bin/env python3
"""Minimal SkyFi agent using Google ADK."""

import os
import json
from google.genai.adk import Agent, MCPToolset

# Initialize SkyFi toolset
skyfi_toolset = MCPToolset(
    name="skyfi",
    server_url="https://skyfi-mcp.fly.dev/mcp",
    auth_headers={
        "Authorization": f"Bearer {os.getenv('SKYFI_API_KEY')}"
    }
)

# Create agent with SkyFi tools
agent = Agent(
    name="SkyFi Satellite Imagery Agent",
    model="gemini-2.0-flash",
    tools=[skyfi_toolset],
    system_prompt="""You are a helpful satellite imagery assistant powered by SkyFi.

You can:
- Search for satellite imagery by location and filters
- Check pricing and feasibility before placing orders
- Place orders (always get user confirmation first)
- Monitor areas for new imagery

Always follow this workflow:
1. Geocode the location if a place name is given
2. Search for available imagery
3. Present findings with pricing
4. Get explicit user approval before ordering
5. Use the confirmation_token when placing orders

Never place orders without user approval and a valid token."""
)


def search_imagery(location: str, date_range_days: int = 30):
    """Search for satellite imagery of a location."""

    query = f"""Find satellite imagery of {location} from the last {date_range_days} days.
    Please:
    1. Geocode the location
    2. Search for archived imagery
    3. Show me the top 5 results with pricing information"""

    response = agent.run(query)
    return response


def check_feasibility(location: str):
    """Check if ordering new imagery is feasible."""

    query = f"""Check the feasibility of ordering fresh satellite imagery for {location}.

    Please:
    1. Geocode the location
    2. Check feasibility for HIGH resolution imagery
    3. Get the pricing options
    4. Show me the estimated cost and feasibility score"""

    response = agent.run(query)
    return response


def setup_monitoring(location: str, webhook_url: str = None):
    """Set up area monitoring."""

    query = f"""Set up monitoring for {location} to alert me when new satellite imagery becomes available.

    {f'Webhook URL: {webhook_url}' if webhook_url else 'Store notifications locally.'}"""

    response = agent.run(query)
    return response


if __name__ == "__main__":
    # Example 1: Search for imagery
    print("=== Searching for satellite imagery ===\n")
    result = search_imagery("Port of Singapore", 30)
    print(json.dumps(result, indent=2))

    # Example 2: Check feasibility
    print("\n=== Checking feasibility ===\n")
    result = check_feasibility("Manhattan, New York")
    print(json.dumps(result, indent=2))

    # Example 3: Setup monitoring
    print("\n=== Setting up monitoring ===\n")
    result = setup_monitoring("Tokyo, Japan")
    print(json.dumps(result, indent=2))
```

### Step 3: Advanced Agent with State Management

For more sophisticated workflows, use ADK's state management:

```python
"""Advanced agent with state and multi-step workflows."""

import os
from typing import Optional
from google.genai.adk import Agent, MCPToolset, TaskState

skyfi_toolset = MCPToolset(
    name="skyfi",
    server_url="https://skyfi-mcp.fly.dev/mcp",
    auth_headers={"Authorization": f"Bearer {os.getenv('SKYFI_API_KEY')"}
)

class SkyFiWorkflow:
    """Multi-step workflow for satellite imagery."""

    def __init__(self):
        self.agent = Agent(
            name="SkyFi Workflow Agent",
            model="gemini-2.0-flash",
            tools=[skyfi_toolset],
        )
        self.state = TaskState()

    def search_and_price(self, location: str) -> dict:
        """Search imagery and get pricing."""

        # Step 1: Search
        self.state["location"] = location
        search_result = self.agent.run(
            f"Search for satellite imagery of {location}",
            state=self.state
        )
        self.state["search_results"] = search_result

        # Step 2: Get pricing
        pricing_result = self.agent.run(
            f"For the {location} imagery, get pricing using preview_order",
            state=self.state
        )
        self.state["pricing"] = pricing_result

        return {
            "location": location,
            "search_results": search_result,
            "pricing": pricing_result
        }

    def order_with_confirmation(
        self,
        location: str,
        archive_id: str,
        user_approved: bool = False
    ) -> dict:
        """Place order with confirmation token."""

        if not user_approved:
            return {
                "status": "pending_approval",
                "message": f"Please confirm to order imagery of {location}"
            }

        # Place order (agent will use confirmation_token from preview_order via confirm_order)
        result = self.agent.run(
            f"Place archive order for {archive_id} of {location} using confirm_order",
            state=self.state
        )

        return result

    def setup_continuous_monitoring(self, location: str) -> dict:
        """Set up continuous area monitoring."""

        result = self.agent.run(
            f"Use setup_area_monitoring with action=create for {location} to monitor new imagery",
            state=self.state
        )

        # Store in state for reference
        self.state["monitoring"] = result

        return result
```

## MCPToolset Configuration Reference

| Parameter | Description | Example |
|-----------|-------------|---------|
| `name` | Toolset identifier | `"skyfi"` |
| `server_url` | MCP server endpoint | `"https://skyfi-mcp.fly.dev/mcp"` |
| `auth_headers` | Auth headers dict | `{"Authorization": "Bearer key"}` |
| `description` | What the toolset does | `"Access satellite imagery"` |
| `timeout` | Request timeout in seconds | `60` |

## Tool Categories Available

Through the MCPToolset, you get access to:

- **Search**: `geocode_location`, `search_satellite_imagery`, `search_nearby_pois`
- **Pricing & Orders**: `preview_order`, `confirm_order`, `check_feasibility`
- **Orders**: `check_order_status`, `get_download_url`
- **Monitoring**: `setup_area_monitoring`, `check_new_images`
- **Account**: `get_account_info`, `get_pricing_overview`

## Example: Complete Order Workflow

```python
"""Complete workflow: search → approve → order."""

def complete_order_workflow():
    workflow = SkyFiWorkflow()

    # Step 1: Search and get pricing
    print("Searching for imagery...")
    search_data = workflow.search_and_price("Suez Canal")

    # Step 2: Present to user
    print(f"Found {len(search_data['search_results'])} images")
    print(f"Price: ${search_data['pricing']['cost']}")

    # Step 3: User approves
    user_input = input("Proceed with order? (yes/no): ")
    approved = user_input.lower() in ["yes", "y"]

    # Step 4: Place order
    if approved:
        result = workflow.order_with_confirmation(
            location="Suez Canal",
            archive_id=search_data['search_results'][0]['id'],
            user_approved=True
        )
        print(f"Order placed: {result['order_id']}")
        print(f"Status: {result['status']}")
    else:
        print("Order cancelled")
```

## Error Handling

```python
try:
    result = agent.run("Find imagery of Tokyo")
except Exception as e:
    if "401" in str(e):
        print("Check your SKYFI_API_KEY")
    elif "timeout" in str(e).lower():
        print("Request timed out")
    else:
        print(f"Error: {e}")
```

## Deployment

Deploy your ADK agent to Google Cloud:

```bash
gcloud functions deploy skyfi-agent \
    --runtime python311 \
    --trigger-http \
    --entry-point main \
    --set-env-vars SKYFI_API_KEY=your-key
```

## What's Next

- **LangChain Integration**: See [langchain-integration.md](langchain-integration.md) for LangChain agents
- **Vercel AI SDK**: See [ai-sdk-integration.md](ai-sdk-integration.md) for Node.js
- **Claude Integration**: See [anthropic-api-integration.md](anthropic-api-integration.md) for Anthropic API
- **OpenAI Integration**: See [openai-integration.md](openai-integration.md) for GPT models
