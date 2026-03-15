# SkyFi MCP Server Examples

This directory contains examples demonstrating how to use the SkyFi MCP server for geospatial research and satellite imagery analysis.

## Simple Agent (`simple_agent.py`)

A minimal ~140-line agent with no framework dependencies (just `httpx`). Demonstrates the core search → preview → confirm workflow by calling the `/tool/<name>` HTTP proxy endpoints directly.

```bash
export SKYFI_API_KEY="sk-..."
python examples/simple_agent.py "Golden Gate Bridge"
python examples/simple_agent.py --mcp-url http://localhost:8000/mcp "Port of Singapore"
```

## Demo Agent (`demo_agent.py`)

The full-featured example — a production-quality LangChain agent that demonstrates all capabilities of the SkyFi platform.

### Features

- **Multi-step Workflows**: Geocoding → Search → Feasibility → Pricing → Ordering
- **Human-in-Loop Confirmation**: Enforces user confirmation before placing any orders
- **Multi-turn Conversations**: Maintains chat history for contextual research sessions
- **Multiple LLM Support**: Works with OpenAI (GPT-4o) and Anthropic (Claude) models
- **Comprehensive Tool Integration**: Access to all 12 SkyFi MCP tools
- **Error Handling**: Graceful error recovery and informative messages
- **Production-Quality Code**: Type hints, logging, full documentation

### Quick Start

#### Prerequisites

1. **Python 3.11+** with pip
2. **Running SkyFi MCP server** (on `http://localhost:8000/mcp` by default)
3. **LLM API key** for OpenAI or Anthropic:
   ```bash
   export OPENAI_API_KEY="sk-..."  # for GPT-4o
   # OR
   export ANTHROPIC_API_KEY="sk-ant-..."  # for Claude
   ```

#### Installation

Install the demo dependencies:

```bash
pip install -e ".[demo]"
```

This installs:
- `langchain>=0.3.0` - LangChain framework for agent orchestration
- `langgraph>=0.2.0` - State management for multi-turn workflows
- `langchain-openai>=0.2.0` - OpenAI integration
- `langchain-anthropic>=0.3.0` - Anthropic Claude integration
- `langchain-mcp-adapters>=0.1.0` - MCP tool integration

#### Running the Agent

```bash
# Using default GPT-4o model
python examples/demo_agent.py

# Using Claude
python examples/demo_agent.py --model claude-3-5-sonnet

# With custom MCP server URL
python examples/demo_agent.py --mcp-url http://localhost:9000/mcp
```

### Typical Workflow

1. **Start the Agent**: The agent greets you and asks about your needs
2. **Describe Your Area**: Tell the agent what location you want to study
3. **Specify Requirements**: Describe the type of imagery, resolution, and timeline
4. **Review Results**: The agent searches and presents options with pricing
5. **Confirm Order**: Review pricing/feasibility, then confirm to place the order
6. **Track Status**: Monitor your order status and download when ready

### Architecture

The agent uses LangChain with MCP adapters to connect to the SkyFi server:

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

async with MultiServerMCPClient({"skyfi": {"url": mcp_url, "transport": "streamable_http"}}) as client:
    tools = client.get_tools()
```

All SkyFi MCP tools are automatically wrapped and made available to the agent.

### Available Tools (12)

The agent has access to these tool categories:

**Search & Geospatial**
- `search_satellite_imagery`: Search catalog with auto-geocoding, filters, and pagination
- `geocode_location`: Convert place names to WKT coordinates
- `search_nearby_pois`: Find points of interest near a location

**Pricing & Feasibility**
- `get_pricing_overview`: General pricing across all products/resolutions
- `check_feasibility`: Verify if a new capture is possible (auto-polls for results)
- `preview_order`: Get exact pricing + feasibility check, returns confirmation_token

**Ordering (Human-in-the-Loop)**
- `confirm_order`: Place archive or tasking order (requires confirmation_token)
- `check_order_status`: View specific order or list order history
- `get_download_url`: Get download URL for completed imagery

**Monitoring**
- `setup_area_monitoring`: Create, list, view history, or delete AOI monitors
- `check_new_images`: Poll for new imagery alerts from webhooks

**Account**
- `get_account_info`: Check budget and payment status

### Confirmation Flow

The agent enforces a human-in-loop confirmation pattern:

1. User requests imagery search/analysis
2. Agent calls `search_satellite_imagery()` to find images (auto-geocodes place names)
3. Agent calls `preview_order()` to get exact pricing + confirmation_token
4. Agent presents pricing to the user
5. User confirms they want to proceed
6. Agent calls `confirm_order()` with the confirmation_token
7. Order is placed and user receives confirmation

**Without the confirmation token, orders will be rejected.**

### Model Support

The agent works with:

**OpenAI**
- `gpt-4o` (default)
- `gpt-4-turbo`

**Anthropic**
- `claude-3-5-sonnet`
- `claude-3-opus`

Switch models with the `--model` flag.

### Command Reference

While in the chat loop:

```
Type your question/request   - Send a query to the agent
'clear'                       - Reset conversation history
'account'                     - Check your SkyFi budget
'quit'                        - Exit the agent
```

### Troubleshooting

**"Connection refused" error**
- Ensure the SkyFi MCP server is running on the specified URL
- Check the `--mcp-url` parameter

**"API key not found" error**
- Set your LLM API key:
  - `export OPENAI_API_KEY="..."`
  - `export ANTHROPIC_API_KEY="..."`

**"Module not found" errors**
- Reinstall demo dependencies: `pip install -e ".[demo]"`

**Agent seems slow**
- The agent may be polling for feasibility results or order status
- This is expected behavior; wait for the process to complete

### Code Structure

`demo_agent.py` contains:

- **Imports**: LangChain, MCP adapters, argument parsing
- **System Prompt**: Instructions for the agent on SkyFi capabilities
- **ConfirmationState**: Tracks confirmation tokens for order validation
- **create_agent()**: Initializes the agent with MCP tools
- **run_chat_loop()**: Interactive conversation interface
- **main()**: CLI entry point with argument parsing

### Production Deployment

To deploy this agent in production:

1. Wrap it in a web framework (FastAPI, Flask, etc.)
2. Add authentication for your users
3. Implement persistent conversation storage (database)
4. Add monitoring and logging
5. Consider rate limiting and usage quotas
6. Use environment variables for API keys

### Contributing

This example is open-source. Contributions welcome:

- Add new tool categories
- Improve the system prompt
- Add more usage examples
- Optimize performance
- Enhance error handling

### License

MIT License - See LICENSE file in root directory
