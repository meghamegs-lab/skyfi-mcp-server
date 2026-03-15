# SkyFi MCP Server

> **Satellite imagery at the speed of conversation.** A Model Context Protocol (MCP) server that lets AI agents search, analyze, order, and monitor satellite imagery through [SkyFi's platform](https://skyfi.com).

[![CI](https://github.com/skyfi/skyfi-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/skyfi/skyfi-mcp-server/actions)
[![PyPI](https://img.shields.io/pypi/v/skyfi-mcp)](https://pypi.org/project/skyfi-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## What is this?

As AI agents take on more autonomous decision-making, they need programmatic access to real-world data. SkyFi MCP Server bridges the gap between conversational AI and satellite imagery by exposing SkyFi's full API as MCP tools that any AI agent can use.

An agent can go from *"Show me recent imagery of the Suez Canal"* to presenting search results, checking feasibility, getting pricing, and placing an order — all through natural conversation with human confirmation at every financial step.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    AI Agent / Client                     │
│  (Claude, GPT-4, Gemini, LangChain, ADK, AI SDK, etc.) │
└──────────────┬──────────────────────────────────────────┘
               │  MCP Protocol (Streamable HTTP / SSE / stdio)
               ▼
┌─────────────────────────────────────────────────────────┐
│                   SkyFi MCP Server                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │ Search   │ │ Pricing  │ │ Orders   │ │ Monitoring│  │
│  │ & OSM    │ │ & Feas.  │ │ (w/token)│ │ & Webhooks│  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬─────┘  │
│       └─────────────┼───────────┼──────────────┘        │
│                     ▼           ▼                        │
│              ┌─────────────────────────┐                 │
│              │    SkyFi API Client     │                 │
│              │  (httpx + Pydantic v2)  │                 │
│              └────────────┬────────────┘                 │
└───────────────────────────┼─────────────────────────────┘
                            ▼
                 ┌─────────────────────┐
                 │  SkyFi Platform API  │
                 │  app.skyfi.com       │
                 └─────────────────────┘
```

## Quick Start

### Install

```bash
pip install skyfi-mcp
```

Or from source:

```bash
git clone https://github.com/skyfi/skyfi-mcp-server.git
cd skyfi-mcp-server
pip install -e .
```

### Configure

```bash
# Option 1: Environment variable
export SKYFI_API_KEY="your-api-key-here"

# Option 2: Config file
skyfi-mcp config --init
# Then edit ~/.skyfi/config.json with your API key
```

Get your API key from [SkyFi](https://app.skyfi.com) (requires Pro account).

### Run

```bash
# HTTP server (for remote clients like Claude Web, OpenAI, etc.)
skyfi-mcp serve

# Local stdio (for Claude Desktop, Claude Code, etc.)
skyfi-mcp serve --transport stdio
```

The server starts at `http://localhost:8000/mcp`.

## Tools Reference

### Search & Discovery
| Tool | Description |
|------|-------------|
| `search_archive` | Search satellite image catalog with filters (date, resolution, cloud cover, provider) |
| `search_archive_next_page` | Paginate through search results |
| `get_archive_details` | Full metadata for a specific archive image |
| `geocode_location` | Convert place names to WKT coordinates (via OpenStreetMap) |
| `reverse_geocode_location` | Convert coordinates to place names |
| `search_nearby_pois` | Find airports, ports, buildings near a location |

### Pricing & Feasibility
| Tool | Description |
|------|-------------|
| `get_pricing_options` | Get pricing across all products/resolutions. **Returns confirmation_token.** |
| `check_feasibility` | Assess if new capture is feasible for an area. **Returns confirmation_token.** |
| `get_feasibility_result` | Poll for async feasibility results |
| `predict_satellite_passes` | Upcoming satellite passes for a location |

### Ordering (Human-in-the-Loop)
| Tool | Description |
|------|-------------|
| `create_archive_order` | Order existing imagery. **Requires confirmation_token.** |
| `create_tasking_order` | Order new satellite capture. **Requires confirmation_token.** |
| `list_orders` | View order history with pagination |
| `get_order_status` | Detailed order status with event timeline |
| `get_download_url` | Download URL for completed imagery |
| `schedule_redelivery` | Re-deliver order to different storage |

### Monitoring & Notifications
| Tool | Description |
|------|-------------|
| `create_aoi_notification` | Set up AOI monitoring with webhook |
| `list_notifications` | List active monitors |
| `get_notification_history` | View notification trigger history |
| `delete_notification` | Remove a monitor |
| `check_new_images` | Poll for new imagery events (Pulse-style) |

### Account
| Tool | Description |
|------|-------------|
| `get_account_info` | Budget usage, payment status |

## Human-in-the-Loop Safety

Orders are protected by a confirmation token system:

```
1. Agent calls get_pricing_options → receives confirmation_token
2. Agent presents price to user → user says "go ahead"
3. Agent calls create_archive_order with confirmation_token → order placed
```

- Tokens are HMAC-signed and expire after 5 minutes
- Order tools **reject** requests without a valid token
- Tokens are stateless (no server-side storage needed)

## Deployment

### Cloud (Fly.io)

```bash
fly launch
fly secrets set SKYFI_API_KEY="your-key"
fly deploy
```

Your MCP server is now at `https://your-app.fly.dev/mcp`.

### Docker

```bash
docker build -t skyfi-mcp .
docker run -p 8000:8000 -e SKYFI_API_KEY="your-key" skyfi-mcp
```

### Cloud Auth (Multi-user)

For cloud deployment, clients pass their own SkyFi API key in headers:

```
Authorization: Bearer <skyfi-api-key>
```

or:

```
X-Skyfi-Api-Key: <skyfi-api-key>
```

## Integration Guides

| Platform | Guide | Type |
|----------|-------|------|
| LangChain / LangGraph | [Full Example](docs/langchain-integration.md) | Python |
| Claude Web | [Full Example](docs/claude-web-integration.md) | Config |
| OpenAI | [Full Example](docs/openai-integration.md) | Python |
| Google ADK | [Config Guide](docs/adk-integration.md) | Python |
| Vercel AI SDK | [Config Guide](docs/ai-sdk-integration.md) | TypeScript |
| Anthropic API / Claude Code | [Config Guide](docs/anthropic-api-integration.md) | JSON + Python |
| Google Gemini | [Config Guide](docs/gemini-integration.md) | Python |

## Demo Agent

A full research agent that demonstrates all capabilities:

```bash
pip install -e ".[demo]"
python examples/demo_agent.py
```

Try: *"What satellite imagery is available for the new Istanbul airport?"*

The agent will geocode the location, search the archive, check feasibility for new captures, compare pricing, and present a research brief.

## Development

```bash
git clone https://github.com/skyfi/skyfi-mcp-server.git
cd skyfi-mcp-server
pip install -e ".[dev]"

# Run tests
pytest -v

# Lint
ruff check src/ tests/
ruff format src/ tests/
```

## Project Structure

```
skyfi-mcp-server/
├── src/skyfi_mcp/
│   ├── __init__.py          # Package metadata
│   ├── __main__.py          # CLI entry point
│   ├── server.py            # FastMCP server with all 21 tools
│   ├── api/
│   │   ├── client.py        # Async SkyFi API client (httpx)
│   │   └── models.py        # Pydantic v2 models (57 schemas)
│   ├── auth/
│   │   ├── config.py        # Dual auth (local config + cloud headers)
│   │   └── tokens.py        # HMAC confirmation tokens
│   ├── osm/
│   │   └── geocoder.py      # Nominatim geocoding + Overpass POI search
│   └── webhooks/
│       └── store.py         # SQLite webhook event store
├── examples/
│   ├── demo_agent.py        # LangChain research agent
│   └── config/              # Example configuration files
├── docs/                    # Integration guides (7 platforms)
├── tests/                   # pytest test suite
├── Dockerfile               # Container deployment
├── fly.toml                 # Fly.io configuration
└── pyproject.toml           # Package configuration
```

## License

[MIT](LICENSE) — Copyright 2025 SkyFi Inc.
