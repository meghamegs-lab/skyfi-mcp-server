# CLAUDE.md — SkyFi MCP Server

This file gives Claude (or any AI assistant) the context needed to work on this codebase effectively.

## What this project is

A remote MCP (Model Context Protocol) server that wraps SkyFi's satellite imagery Platform API, enabling AI agents to conversationally search, order, and monitor satellite imagery with human-in-the-loop safety for purchases.

**Hybrid architecture:** TypeScript Cloudflare Worker (thin MCP proxy + OAuth) → Python backend (all business logic). The Worker handles MCP protocol, Zod schema validation, OAuth 2.1 for Claude Web, and session management via Durable Objects. The Python backend (FastMCP + uvicorn) runs on Fly.io and exposes `/tool/<name>` HTTP endpoints that the Worker proxies to.

Python backend uses Prefect's **FastMCP** library (`fastmcp>=2.0.0` from PyPI — NOT the official `mcp` SDK's built-in FastMCP). Transport: Streamable HTTP + legacy SSE + progress streaming.

## Project structure

```
skyfi-mcp-server/
├── worker/                    # Cloudflare Worker (TypeScript) — MCP front door
│   ├── src/index.ts           # McpAgent + 12 Zod-validated tools + OAuth 2.1
│   ├── package.json           # agents, zod, @cloudflare/workers-oauth-provider
│   ├── wrangler.toml          # Durable Objects, KV bindings, env config
│   └── tsconfig.json          # TypeScript config
├── src/skyfi_mcp/             # Python backend — all business logic
│   ├── __main__.py            # CLI entry point + ASGI app + /tool/<name> proxy endpoints
│   ├── server.py              # FastMCP server with 12 outcome-oriented MCP tools
│   ├── api/
│   │   ├── client.py          # Async httpx wrapper for all 19 SkyFi API endpoints
│   │   └── models.py          # 57 Pydantic v2 models from OpenAPI spec (616 lines)
│   ├── auth/
│   │   ├── config.py          # Dual auth: local config file + cloud header extraction
│   │   └── tokens.py          # HMAC-signed confirmation tokens for order safety
│   ├── osm/
│   │   └── geocoder.py        # Nominatim geocoding + Overpass POI search
│   └── webhooks/
│       └── store.py           # SQLite event store for webhook notifications
├── tests/                     # pytest + pytest-asyncio
│   ├── test_models.py         # Pydantic model validation
│   ├── test_tokens.py         # HMAC token create/validate
│   ├── test_server_helpers.py # Tool helpers, registration, annotations
│   └── test_webhooks.py       # SQLite event store
├── examples/
│   ├── demo_agent.py          # LangChain/LangGraph research agent (372 lines)
│   └── simple_agent.py        # Framework-free demo (~140 lines, httpx only)
├── docs/                      # Integration guides for 7 frameworks
│   ├── langchain-integration.md
│   ├── claude-web-integration.md
│   ├── openai-integration.md
│   ├── adk-integration.md
│   ├── ai-sdk-integration.md
│   ├── anthropic-api-integration.md
│   └── gemini-integration.md
├── Dockerfile                 # Python 3.12-slim, runs skyfi-mcp serve
├── fly.toml                   # Fly.io deployment config (Python backend)
├── pyproject.toml             # hatchling build, CLI entry point, deps
└── .github/
    ├── workflows/ci.yml       # ruff lint + pytest
    ├── ISSUE_TEMPLATE/
    └── pull_request_template.md
```

## Key architectural decisions

### Hybrid architecture: TypeScript Worker + Python backend

The server uses a two-tier architecture:

1. **Cloudflare Worker** (`worker/src/index.ts`): Thin MCP proxy using `McpAgent` from the Cloudflare Agents SDK (`agents` npm package). Handles MCP protocol (Streamable HTTP + legacy SSE), Zod schema validation for all 12 tools, OAuth 2.1 for Claude Web via `@cloudflare/workers-oauth-provider`, session management via Durable Objects, and Bearer token extraction for programmatic clients.

2. **Python backend** (`src/skyfi_mcp/`): All business logic. FastMCP server with 12 tools, SkyFi API client, geocoding, HMAC tokens, webhook store. Exposes `/tool/<name>` HTTP endpoints that the Worker proxies to.

The Worker calls `POST ${PYTHON_BACKEND_URL}/tool/${toolName}` for each tool invocation. The Python backend also runs standalone as a full MCP server (via `skyfi-mcp serve`) for local development.

### FastMCP (Prefect), not the official `mcp` SDK

We use `from fastmcp import FastMCP` (the Prefect/jlowin package on PyPI: `fastmcp>=2.0.0`), **not** `from mcp.server.fastmcp import FastMCP`. The official SDK's built-in FastMCP had transport issues. The Prefect version provides better Streamable HTTP support.

### ASGI app composition — raw ASGI wrapper, not Starlette Mount

`__main__.py` contains a `_create_combined_app()` function that wraps FastMCP's Starlette app with a thin ASGI dispatcher. This intercepts `/`, `/health`, `/webhook`, and `/tool/<name>` before they reach the MCP handler. Everything else (including `/mcp`, lifespan events, SSE streams) passes through to FastMCP untouched.

**Why not Starlette Mount?** FastMCP's `http_app()` returns a `StarletteWithLifespan` object whose `routes` property has no setter. Nesting it inside another Starlette app via `Mount()` breaks lifespan propagation and session management. The raw ASGI wrapper avoids both problems.

**Why not `@mcp.custom_route`?** The `custom_route` decorator is broken in fastmcp >= 2.4 (see jlowin/fastmcp#556). All custom HTTP routes are handled in `__main__.py` instead.

### Human-in-the-loop ordering via HMAC confirmation tokens

SkyFi has no quote/cart API. We implement order safety with a two-step pattern:

1. `preview_order` → returns an HMAC-signed `confirmation_token`
2. `confirm_order` → requires that token, validates signature + expiry

Token TTLs differ by order type:
- **Archive orders:** 5-minute TTL (pricing is static, quick decision)
- **Tasking orders:** 24-hour TTL (feasibility analysis takes time, users need longer to decide)

Tokens are stateless (HMAC-signed with `{action, context_hash, timestamp}`), so any server instance can validate them. The MCP server instructions tell the AI to always present pricing to the user and get explicit confirmation before calling order tools.

### Dual authentication

- **Local mode:** reads API key from `SKYFI_API_KEY` env var → `~/.skyfi/config.json` file → error
- **Cloud mode (Worker):** OAuth 2.1 for Claude Web (user provides API key via web form, gets OAuth token), or `Authorization: Bearer <key>` / `X-Skyfi-Api-Key` header for programmatic clients
- Every tool accepts an optional `api_key` parameter for cloud/multi-user deployments

### Async feasibility with auto-polling and progress streaming

The SkyFi feasibility endpoint is async — POST returns a `task_id`, and you poll GET for the result. The `check_feasibility` and `preview_order` (tasking) tools auto-poll every 3 seconds for up to 30 seconds with MCP progress notifications via `ctx.report_progress()`, then fall back to returning the `feasibility_id` for manual polling.

### Webhook notifications via SQLite event store

SkyFi sends webhook POSTs to `/webhook` when AOI monitors detect new imagery. Events are stored in a SQLite database (`webhook_events.db`). The `check_new_images` MCP tool reads unread events from this store (poll-based, ChatGPT Pulse-style). Events auto-expire after 30 days.

### OpenStreetMap integration

Three OSM tools let AI agents convert natural language locations to WKT:
- `geocode_location` — Nominatim forward geocode → WKT polygon (uses actual boundary geometry when available, falls back to bounding box or buffer)
- `reverse_geocode_location` — coordinates → place name
- `search_nearby_pois` — Overpass API for finding airports, ports, military bases, etc.

## The 12 MCP tools

Refactored from 21 granular REST-mirror tools to 12 outcome-oriented tools:

| Category | Tool | Description |
|---|---|---|
| Search | `search_satellite_imagery` | Search catalog with auto-geocoding, filters, and pagination |
| Pricing | `get_pricing_overview` | General pricing across all products/resolutions |
| Feasibility | `check_feasibility` | Async feasibility check with auto-polling (read-only) |
| Order Flow | `preview_order` | Exact pricing + feasibility + confirmation_token |
| Order Flow | `confirm_order` | Place archive or tasking order (requires confirmation_token) |
| Order Mgmt | `check_order_status` | View specific order or list order history |
| Order Mgmt | `get_download_url` | Get download URL for image/payload/COG |
| Monitor | `setup_area_monitoring` | Create, list, view history, or delete AOI monitors (action param) |
| Monitor | `check_new_images` | Poll local webhook store for new imagery |
| OSM | `geocode_location` | Place name → WKT polygon |
| OSM | `search_nearby_pois` | Overpass POI search |
| Account | `get_account_info` | Budget, payment status, profile |

All tools have MCP annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`).
Only `confirm_order` is marked destructive. Search tools accept plain location names and auto-geocode via OSM.

## SkyFi Platform API

Base URL: `https://app.skyfi.com/platform-api`
Auth header: `X-Skyfi-Api-Key: <key>`
OpenAPI spec: `https://app.skyfi.com/platform-api/openapi.json`

19 endpoints wrapped in `api/client.py`. All request/response models in `api/models.py` use Pydantic v2 with `populate_by_name = True` and camelCase `alias` for API compatibility (the API uses camelCase, Python code uses snake_case).

Key enums: `ApiProvider` (14 satellite providers), `ProductType` (8 types including DAY, SAR, HYPERSPECTRAL), `DeliveryStatus` (14 statuses), `ResolutionLevel` (5 levels).

## Development commands

```bash
# ── Python backend ──
pip install -e ".[dev]"                    # Install in development mode
skyfi-mcp serve                           # Streamable HTTP on :8000
skyfi-mcp serve --port 3000               # Custom port
skyfi-mcp serve --transport stdio          # For local MCP clients

# Configure API key
skyfi-mcp config --init                    # Create ~/.skyfi/config.json template
skyfi-mcp config --show                    # Show current config
export SKYFI_API_KEY="sk-..."              # Or use env var

# Run tests
pytest
ruff check src/ tests/

# Docker (Python backend only)
docker build -t skyfi-mcp .
docker run -p 8000:8000 -e SKYFI_API_KEY="sk-..." skyfi-mcp

# Fly.io deployment (Python backend)
fly deploy
fly secrets set SKYFI_API_KEY="sk-..."

# ── Cloudflare Worker ──
cd worker
npm install
npx wrangler dev                          # Local dev
npx wrangler deploy                       # Deploy to Cloudflare
npx wrangler secret put SKYFI_OAUTH_CLIENT_ID
npx wrangler secret put SKYFI_OAUTH_CLIENT_SECRET
npx wrangler secret put COOKIE_ENCRYPTION_KEY
```

## Server endpoints

### Python backend (Fly.io / local)

| Path | Method | Description |
|---|---|---|
| `/` | GET | Landing page JSON |
| `/health` | GET | Health check |
| `/webhook` | POST | SkyFi notification webhook receiver |
| `/tool/<name>` | POST | Direct tool invocation (Worker proxy target) |
| `/mcp` | POST/GET | MCP protocol (Streamable HTTP + SSE) |

### Cloudflare Worker

| Path | Method | Description |
|---|---|---|
| `/` | GET | Landing page JSON |
| `/health` | GET | Health check |
| `/mcp` | POST/GET | MCP protocol (Streamable HTTP) |
| `/sse` | GET | MCP protocol (legacy SSE) |
| `/authorize` | GET | OAuth 2.1 authorization (Claude Web) |

The `/mcp` endpoint is for MCP clients only. Browsers hitting it get a `406 Not Acceptable` error — this is expected behavior (they need to accept `text/event-stream`).

## Known issues and workarounds

1. **`@mcp.custom_route` broken in fastmcp >= 2.4** — All custom HTTP routes are implemented as raw ASGI handlers in `__main__.py` instead. See jlowin/fastmcp#556.

2. **`StarletteWithLifespan` has read-only `routes`** — Cannot inject routes into `http_app()` return value. Solved with ASGI wrapper pattern.

3. **SkyFi's `GET /orders` takes a JSON body** — Unusual but per their spec. The client sends both `params=` and `json=` on the GET request.

4. **Feasibility is async** — POST returns immediately with a task ID. Must poll GET. Auto-poll handles this for most cases.

## Pydantic model conventions

All models in `api/models.py`:
- Use `model_config = ConfigDict(populate_by_name=True)` to allow both snake_case and camelCase
- Fields have `alias="camelCase"` for API serialization
- Serialize with `model_dump(by_alias=True, exclude_none=True)` when sending to API
- Validate with `Model.model_validate(data)` when receiving from API

## Testing approach

Tests use `pytest-asyncio` with `asyncio_mode = "auto"`. The `conftest.py` provides fixtures for mock configs and clients. Tests cover:
- Pydantic model validation (all 57 models)
- HMAC token creation, validation, expiry, and tampering
- SQLite webhook store CRUD, TTL cleanup, and filtering

API client tests would use `respx` for HTTP mocking (listed in dev dependencies).

## Environment variables

### Python backend

| Variable | Required | Description |
|---|---|---|
| `SKYFI_API_KEY` | Yes (or config file) | SkyFi Platform API key |
| `SKYFI_BASE_URL` | No | Override API base URL (default: `https://app.skyfi.com/platform-api`) |
| `SKYFI_TOKEN_SECRET` | No | HMAC secret for confirmation tokens (default: built-in) |
| `SKYFI_MCP_DATA_DIR` | No | Directory for SQLite DB (default: `.`) |

### Cloudflare Worker (wrangler secrets)

| Variable | Required | Description |
|---|---|---|
| `PYTHON_BACKEND_URL` | Yes | Python backend URL (e.g., `https://skyfi-mcp-server.fly.dev`) |
| `SKYFI_OAUTH_CLIENT_ID` | For OAuth | OAuth client ID for Claude Web |
| `SKYFI_OAUTH_CLIENT_SECRET` | For OAuth | OAuth client secret |
| `COOKIE_ENCRYPTION_KEY` | For OAuth | Session cookie encryption key |

## Deployment options

- **Production (recommended):** Cloudflare Worker → Fly.io Python backend
  - Worker: `cd worker && npx wrangler deploy`
  - Backend: `fly deploy && fly secrets set SKYFI_API_KEY="sk-..."`
- **Local development:** `skyfi-mcp serve` (Python backend only, full MCP server)
- **Docker:** `Dockerfile` included for the Python backend, maps port 8000
- **Standalone Python:** For local MCP clients, `skyfi-mcp serve --transport stdio`
