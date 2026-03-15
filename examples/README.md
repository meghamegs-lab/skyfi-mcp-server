# SkyFi MCP Server Examples

This directory contains examples demonstrating how to use the SkyFi MCP server with LangChain and LangGraph for geospatial research and satellite imagery analysis.

## Demo Agent

The primary example is `demo_agent.py`, a production-quality LangChain agent that demonstrates the full capabilities of the SkyFi platform.

### Features

- **Multi-step Workflows**: Geocoding → Search → Feasibility → Pricing → Ordering
- **Human-in-Loop Confirmation**: Enforces user confirmation before placing any orders
- **Multi-turn Conversations**: Maintains chat history for contextual research sessions
- **Multiple LLM Support**: Works with OpenAI (GPT-4o) and Anthropic (Claude) models
- **Comprehensive Tool Integration**: Access to all 30+ SkyFi MCP tools
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

### Available Tools

The agent has access to these tool categories:

**Geocoding**
- `geocode_location`: Convert place names to WKT coordinates
- `reverse_geocode_location`: Convert coordinates to place names
- `search_nearby_pois`: Find points of interest near a location

**Archive Search**
- `search_archive`: Search existing satellite imagery
- `search_archive_next_page`: Paginate through results
- `get_archive_details`: Get full metadata for an image

**Planning**
- `check_feasibility`: Verify if a new capture is possible
- `get_feasibility_result`: Poll for feasibility status
- `predict_satellite_passes`: Find upcoming satellite passes

**Pricing & Orders**
- `get_pricing_options`: Get pricing information
- `create_archive_order`: Order existing imagery (requires confirmation token)
- `create_tasking_order`: Request new satellite capture (requires confirmation token)
- `list_orders`: View your order history
- `get_order_status`: Check status of a specific order

**Monitoring**
- `create_aoi_notification`: Monitor areas for new imagery
- `list_notifications`: View your active monitors
- `get_notification_history`: Check notification triggers
- `delete_notification`: Remove a monitor
- `check_new_images`: Poll for new imagery alerts

**Account**
- `get_account_info`: Check budget and payment status

### Confirmation Flow

The agent enforces a human-in-loop confirmation pattern:

1. User requests imagery search/analysis
2. Agent calls `get_pricing_options()` or `check_feasibility()`
3. Agent receives a `confirmation_token` in the response
4. Agent presents pricing/feasibility to the user
5. User confirms they want to proceed
6. Agent calls `create_archive_order()` or `create_tasking_order()` with the token
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
