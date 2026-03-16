# SkyFi MCP Server

> **Satellite imagery at the speed of conversation.** A Model Context Protocol (MCP) server that lets AI agents search, analyze, order, and monitor satellite imagery through [SkyFi's platform](https://skyfi.com).

[![CI/CD](https://github.com/skyfi/skyfi-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/skyfi/skyfi-mcp-server/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## What is this?

SkyFi MCP Server bridges the gap between conversational AI and satellite imagery. It exposes SkyFi's full API as 12 MCP tools that any AI agent can use — Claude, GPT-4, Gemini, LangChain, and more.

An agent can go from *"Show me recent imagery of the Suez Canal"* to presenting search results, checking feasibility, getting pricing, and placing an order — all through natural conversation with human confirmation at every financial step.

## Architecture

The server uses a **hybrid two-tier architecture**:

```
┌─────────────────────────────────────────────────────┐
│              AI Agent / MCP Client                    │
│  (Claude, GPT-4, Gemini, LangChain, ADK, AI SDK)    │
└──────────────┬───────────────────────────────────────┘
               │  MCP Protocol (Streamable HTTP / SSE)
               ▼
┌─────────────────────────────────────────────────────┐
│        Cloudflare Worker  (TypeScript)               │
│    MCP proxy + OAuth 2.1 + Zod schemas              │
│    Durable Objects for session management            │
└──────────────┬───────────────────────────────────────┘
               │  POST /tool/<name>
               ▼
┌─────────────────────────────────────────────────────┐
│         Python Backend  (Fly.io)                     │
│    FastMCP + 12 tools + SkyFi API client            │
│    Geocoding, HMAC tokens, webhook store            │
└──────────────┬───────────────────────────────────────┘
               │  HTTPS
               ▼
        ┌──────────────┐
        │ SkyFi API    │
        │ app.skyfi.com│
        └──────────────┘
```

The **Cloudflare Worker** handles MCP protocol, OAuth 2.1 for Claude Web, and Zod schema validation. The **Python backend** contains all business logic and runs on Fly.io.

For local development, the Python backend runs standalone as a full MCP server — no Worker needed.

## Quick Start

```bash
# Clone and install
git clone https://github.com/skyfi/skyfi-mcp-server.git
cd skyfi-mcp-server
pip install -e .

# Configure your SkyFi API key
export SKYFI_API_KEY="your-api-key-here"

# Start the server
skyfi-mcp serve
```

The server starts at `http://localhost:8000`. See [SETUP.md](SETUP.md) for detailed instructions.

## Tools (12)

| Category | Tool | What it does |
|----------|------|-------------|
| **Search** | `search_satellite_imagery` | Search catalog with auto-geocoding, filters, pagination |
| **Pricing** | `get_pricing_overview` | General pricing across all products and resolutions |
| **Feasibility** | `check_feasibility` | Assess if new capture is feasible (auto-polls) |
| **Order Flow** | `preview_order` | Exact pricing + feasibility + confirmation token |
| **Order Flow** | `confirm_order` | Place archive or tasking order (requires token) |
| **Order Mgmt** | `check_order_status` | View specific order or list order history |
| **Order Mgmt** | `get_download_url` | Download URL for completed imagery |
| **Monitoring** | `setup_area_monitoring` | Create, list, view, or delete AOI monitors |
| **Monitoring** | `check_new_images` | Poll for new imagery events from webhooks |
| **Geospatial** | `geocode_location` | Place name to WKT polygon (via OpenStreetMap) |
| **Geospatial** | `search_nearby_pois` | Find airports, ports, bases near a location |
| **Account** | `get_account_info` | Budget usage and payment status |

All tools have MCP annotations (`readOnlyHint`, `destructiveHint`, etc.). Only `confirm_order` is marked destructive.

## Human-in-the-Loop Safety

Orders are protected by HMAC-signed confirmation tokens:

```
1. Agent calls preview_order      → gets pricing + confirmation_token
2. Agent presents price to user   → user says "go ahead"
3. Agent calls confirm_order      → token validated, order placed
```

Archive tokens expire in 5 minutes. Tasking tokens expire in 24 hours (to allow time for feasibility review). Without a valid token, order tools reject the request — agents cannot bypass this.

## Server Endpoints

### Python Backend (local / Fly.io)

| Path | Method | Description |
|------|--------|-------------|
| `/` | GET | Landing page (server info JSON) |
| `/health` | GET | Health check |
| `/webhook` | POST | SkyFi notification receiver |
| `/tool/<name>` | POST | Direct tool invocation (Worker proxy target) |
| `/mcp` | POST/GET | MCP protocol (Streamable HTTP + SSE) |

### Cloudflare Worker (production)

| Path | Method | Description |
|------|--------|-------------|
| `/mcp` | POST/GET | MCP protocol (Streamable HTTP) |
| `/sse` | GET | MCP protocol (legacy SSE) |
| `/authorize` | GET | OAuth 2.1 authorization (Claude Web) |
| `/health` | GET | Health check |

The `/mcp` endpoint is for MCP clients only. Browsers get a `406 Not Acceptable` — this is expected.

## Integration Guides

| Platform | Guide |
|----------|-------|
| LangChain / LangGraph | [docs/langchain-integration.md](docs/langchain-integration.md) |
| Claude Web | [docs/claude-web-integration.md](docs/claude-web-integration.md) |
| OpenAI | [docs/openai-integration.md](docs/openai-integration.md) |
| Google ADK | [docs/adk-integration.md](docs/adk-integration.md) |
| Vercel AI SDK | [docs/ai-sdk-integration.md](docs/ai-sdk-integration.md) |
| Anthropic API | [docs/anthropic-api-integration.md](docs/anthropic-api-integration.md) |
| Google Gemini | [docs/gemini-integration.md](docs/gemini-integration.md) |

## Demo Agents

```bash
# Simple agent (no framework, httpx only)
python examples/simple_agent.py "Golden Gate Bridge"

# Full LangChain research agent
pip install -e ".[demo]"
python examples/demo_agent.py
```

## Documentation

| Document | Description |
|----------|-------------|
| **[SETUP.md](SETUP.md)** | Local development setup, dependencies, configuration, testing |
| **[DEPLOY.md](DEPLOY.md)** | Production deployment to Fly.io + Cloudflare, CI/CD, secrets |
| [CLAUDE.md](CLAUDE.md) | AI assistant context file for this codebase |
| [examples/README.md](examples/README.md) | Demo agent documentation |

## Project Structure

```
skyfi-mcp-server/
├── worker/                    # Cloudflare Worker (TypeScript)
│   ├── src/index.ts           # McpAgent + OAuth 2.1 + Zod schemas
│   ├── package.json           # agents, zod, workers-oauth-provider
│   ├── wrangler.toml          # Durable Objects, KV, env config
│   └── tsconfig.json
├── src/skyfi_mcp/             # Python backend (all business logic)
│   ├── __main__.py            # CLI + ASGI app + /tool/<name> proxy
│   ├── server.py              # FastMCP server with 12 tools
│   ├── api/
│   │   ├── client.py          # Async SkyFi API client (httpx)
│   │   └── models.py          # 57 Pydantic v2 models
│   ├── auth/
│   │   ├── config.py          # Dual auth (local + cloud)
│   │   └── tokens.py          # HMAC confirmation tokens
│   ├── osm/
│   │   └── geocoder.py        # Nominatim + Overpass integration
│   └── webhooks/
│       └── store.py           # SQLite webhook event store
├── tests/                     # pytest + golden evals (212 tests)
├── examples/                  # Demo agents (LangChain + simple)
├── docs/                      # Integration guides (7 platforms)
├── Dockerfile                 # Python backend container
├── fly.toml                   # Fly.io config
├── pyproject.toml             # Package config
└── .github/workflows/ci.yml   # CI/CD (lint + test + deploy)
```

## License

[MIT](LICENSE)
