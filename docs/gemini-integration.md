# Google Gemini Integration Guide

This guide shows how to integrate the SkyFi MCP server with Google Gemini's function calling API for satellite imagery operations.

## Prerequisites

Install required packages:

```bash
pip install google-genai python-dotenv
```

Set environment variables:

```bash
export GOOGLE_API_KEY="your-google-api-key"
export SKYFI_API_KEY="your-skyfi-api-key"
```

## Configuration

### Step 1: Set Up Gemini API

1. Go to [Google AI Studio](https://aistudio.google.com)
2. Create a new API key
3. Add to environment: `export GOOGLE_API_KEY="..."`

### Step 2: Create Tool Definitions

**lib/skyfi_tools.py**

```python
"""SkyFi tool definitions for Google Gemini function calling."""

from typing import Any

# Tool schemas matching SkyFi MCP server capabilities
SKYFI_TOOLS = [
    {
        "name": "geocode_location",
        "description": "Convert a place name to WKT coordinates for satellite searches",
        "parameters": {
            "type": "object",
            "properties": {
                "location_name": {
                    "type": "string",
                    "description": "Human-readable place name (e.g., 'Suez Canal', 'LAX Airport')"
                },
                "buffer_km": {
                    "type": "number",
                    "description": "Buffer in km around the location (default 1.0)",
                    "default": 1.0
                }
            },
            "required": ["location_name"]
        }
    },
    {
        "name": "search_archive",
        "description": "Search the SkyFi satellite image catalog",
        "parameters": {
            "type": "object",
            "properties": {
                "aoi": {
                    "type": "string",
                    "description": "Area of interest in WKT format"
                },
                "from_date": {
                    "type": "string",
                    "description": "Start date filter (ISO format, e.g., 2024-01-01T00:00:00+00:00)"
                },
                "to_date": {
                    "type": "string",
                    "description": "End date filter (ISO format)"
                },
                "max_cloud_coverage_percent": {
                    "type": "number",
                    "description": "Maximum cloud cover (0-100)"
                },
                "resolutions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by resolution: LOW, MEDIUM, HIGH, VERY_HIGH, ULTRA_HIGH"
                },
                "product_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by product: DAY, NIGHT, VIDEO, SAR, etc."
                },
                "page_size": {
                    "type": "integer",
                    "description": "Number of results per page (default 20, max 100)",
                    "default": 20
                }
            },
            "required": ["aoi"]
        }
    },
    {
        "name": "get_pricing_options",
        "description": "Get pricing options and confirmation token for orders",
        "parameters": {
            "type": "object",
            "properties": {
                "aoi": {
                    "type": "string",
                    "description": "Optional WKT area of interest for area-specific pricing"
                }
            }
        }
    },
    {
        "name": "check_feasibility",
        "description": "Check if a new satellite image capture is feasible",
        "parameters": {
            "type": "object",
            "properties": {
                "aoi": {
                    "type": "string",
                    "description": "Area of interest in WKT format"
                },
                "product_type": {
                    "type": "string",
                    "description": "Product type (DAY, NIGHT, SAR, etc.)"
                },
                "resolution": {
                    "type": "string",
                    "description": "Resolution level"
                },
                "start_date": {
                    "type": "string",
                    "description": "Start of capture window (ISO format)"
                },
                "end_date": {
                    "type": "string",
                    "description": "End of capture window (ISO format)"
                },
                "max_cloud_coverage_percent": {
                    "type": "number",
                    "description": "Maximum acceptable cloud cover"
                }
            },
            "required": ["aoi", "product_type", "resolution", "start_date", "end_date"]
        }
    },
    {
        "name": "create_archive_order",
        "description": "Place an order for existing archived satellite imagery",
        "parameters": {
            "type": "object",
            "properties": {
                "aoi": {
                    "type": "string",
                    "description": "Area of interest in WKT format"
                },
                "archive_id": {
                    "type": "string",
                    "description": "The archive image UUID to order"
                },
                "confirmation_token": {
                    "type": "string",
                    "description": "Token from get_pricing_options (REQUIRED)"
                },
                "label": {
                    "type": "string",
                    "description": "Label for this order",
                    "default": "Gemini Order"
                }
            },
            "required": ["aoi", "archive_id", "confirmation_token"]
        }
    },
    {
        "name": "list_orders",
        "description": "List your previous SkyFi orders",
        "parameters": {
            "type": "object",
            "properties": {
                "page_size": {
                    "type": "integer",
                    "description": "Orders per page (default 25)",
                    "default": 25
                }
            }
        }
    },
    {
        "name": "get_account_info",
        "description": "Get your SkyFi account information and budget",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
]
```

## Minimal Agent Implementation

**skyfi_gemini_agent.py**

```python
#!/usr/bin/env python3
"""Minimal SkyFi agent using Google Gemini."""

import json
import os
import httpx
from typing import Any
import google.genai as genai

# Initialize Gemini
API_KEY = os.getenv("GOOGLE_API_KEY")
SKYFI_API_KEY = os.getenv("SKYFI_API_KEY")
SKYFI_URL = "https://skyfi-mcp.fly.dev/mcp"

client = genai.Client(api_key=API_KEY)

# Import tool definitions
from lib.skyfi_tools import SKYFI_TOOLS


class SkyFiGeminiAgent:
    """SkyFi agent powered by Google Gemini."""

    def __init__(self):
        self.http_client = httpx.AsyncClient()
        self.conversation_history = []

    async def call_mcp_tool(self, tool_name: str, args: dict) -> str:
        """Call a tool on the remote MCP server."""

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": tool_name,
            "params": args
        }

        try:
            response = await self.http_client.post(
                SKYFI_URL,
                json=payload,
                headers={"Authorization": f"Bearer {SKYFI_API_KEY}"}
            )
            result = response.json()

            if "result" in result:
                return json.dumps(result["result"], indent=2)
            elif "error" in result:
                return f"Error: {result['error']['message']}"
            else:
                return str(result)

        except Exception as e:
            return f"Failed to call tool: {e}"

    async def process_message(self, user_message: str) -> str:
        """Process a user message with Gemini and SkyFi tools."""

        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "parts": [{"text": user_message}]
        })

        # Create a chat session with tools
        chat = client.chats.create(
            model="gemini-2.0-flash",
            config=genai.types.GenerateContentConfig(
                tools=[
                    genai.types.Tool(
                        function_declarations=[
                            genai.types.FunctionDeclaration(
                                name=tool["name"],
                                description=tool["description"],
                                parameters=tool["parameters"]
                            )
                            for tool in SKYFI_TOOLS
                        ]
                    )
                ]
            ),
            history=self.conversation_history
        )

        # Send message
        response = chat.send_message(user_message)

        # Handle function calls
        while response.candidates[0].content.parts[-1].function_call:
            function_call = response.candidates[0].content.parts[-1].function_call

            # Execute the tool
            tool_result = await self.call_mcp_tool(
                function_call.name,
                dict(function_call.args)
            )

            # Send result back to Gemini
            response = chat.send_message(
                genai.types.Content(
                    parts=[
                        genai.types.Part.from_function_response(
                            name=function_call.name,
                            response={"result": tool_result}
                        )
                    ]
                )
            )

        # Extract final response
        final_response = ""
        for part in response.candidates[0].content.parts:
            if hasattr(part, "text"):
                final_response += part.text

        # Add to history
        self.conversation_history.append({
            "role": "model",
            "parts": [{"text": final_response}]
        })

        return final_response


async def main():
    """Interactive agent loop."""

    agent = SkyFiGeminiAgent()

    print("SkyFi Satellite Imagery Assistant (Google Gemini)")
    print("=" * 50)
    print("Ask me about satellite imagery!\n")

    while True:
        user_input = input("You: ").strip()

        if user_input.lower() in ["exit", "quit"]:
            break

        response = await agent.process_message(user_input)
        print(f"Assistant: {response}\n")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Configuration Snippet: Tool Definitions

For quick reference, here's the minimal configuration needed:

```python
import google.genai as genai

# Configure Gemini with SkyFi tools
client = genai.Client(api_key="YOUR_GOOGLE_API_KEY")

# Define SkyFi tools
tools = [
    genai.types.Tool(
        function_declarations=[
            genai.types.FunctionDeclaration(
                name="search_archive",
                description="Search the SkyFi satellite image catalog",
                parameters={
                    "type": "object",
                    "properties": {
                        "aoi": {
                            "type": "string",
                            "description": "Area of interest in WKT format"
                        },
                        "max_cloud_coverage_percent": {
                            "type": "number",
                            "description": "Maximum cloud cover (0-100)"
                        }
                    },
                    "required": ["aoi"]
                }
            ),
            # ... add more tools
        ]
    )
]

# Create chat with tools
chat = client.chats.create(
    model="gemini-2.0-flash",
    config=genai.types.GenerateContentConfig(tools=tools)
)
```

## Function Call Handling

```python
async def handle_tool_calls(response: Any, agent: SkyFiGeminiAgent) -> str:
    """Process function calls from Gemini."""

    while response.candidates[0].content.parts[-1].function_call:
        fn_call = response.candidates[0].content.parts[-1].function_call

        # Call the SkyFi MCP tool
        result = await agent.call_mcp_tool(
            fn_call.name,
            dict(fn_call.args)
        )

        # Send result back
        response = agent.chat.send_message(
            genai.types.Content(
                parts=[
                    genai.types.Part.from_function_response(
                        name=fn_call.name,
                        response={"result": result}
                    )
                ]
            )
        )

    return extract_text_response(response)
```

## Error Handling

```python
try:
    response = await agent.process_message("Find imagery of Tokyo")
except Exception as e:
    if "401" in str(e):
        print("Check your GOOGLE_API_KEY and SKYFI_API_KEY")
    elif "timeout" in str(e).lower():
        print("Request timed out")
    else:
        print(f"Error: {e}")
```

## Tool Reference

| Tool | Purpose | Returns |
|------|---------|---------|
| `geocode_location` | Convert place name to WKT | WKT polygon + coordinates |
| `search_archive` | Find satellite imagery | List of available images |
| `get_pricing_options` | Get pricing matrix | Prices + confirmation_token |
| `check_feasibility` | Check tasking order feasibility | Feasibility score + token |
| `create_archive_order` | Order existing imagery | Order ID + cost |
| `list_orders` | View order history | Order list with status |
| `get_account_info` | Get account details | Budget + usage info |

## What's Next

- **LangChain Integration**: See [langchain-integration.md](langchain-integration.md) for Python agents
- **Claude Integration**: See [anthropic-api-integration.md](anthropic-api-integration.md) for Anthropic API
- **Vercel AI SDK**: See [ai-sdk-integration.md](ai-sdk-integration.md) for Node.js
- **OpenAI Integration**: See [openai-integration.md](openai-integration.md) for OpenAI API
- **Google ADK**: See [adk-integration.md](adk-integration.md) for Google's Agent Development Kit
