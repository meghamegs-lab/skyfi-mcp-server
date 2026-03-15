# CLAUDE.md — SkyFi MCP Server

This file gives Claude (or any AI assistant) the context needed to work on this codebase effectively.

## What this project is

A remote MCP (Model Context Protocol) server that wraps SkyFi's satellite imagery Platform API, enabling AI agents to conversationally search, order, and monitor satellite imagery with human-in-the-loop safety for purchases.

Built in Python using Prefect's **FastMCP** library (`fastmcp>=2.0.0` from PyPI — NOT the official `mcp` SDK's built-in FastMCP). Transport is Streamable HTTP + SSE. The server runs as a single ASGI app served by uvicorn.

## Project structure

```
skyfi-mcp-server/
├── src/skyfi_mcp/
│   ├── __main__.py          # CLI entry point + ASGI app composition
│   ├── server.py             # FastMCP server with 21 MCP tools
│   ├── api/
│   │   ├── client.py         # Async httpx wrapper for all 19 SkyFi API endpoints
│   │   └── models.py         # 57 Pydantic v2 models from OpenAPI spec (616 lines)
│   ├── auth/
│   │   ├── config.py         # Dual auth: local config file + cloud header extraction
│   │   └── tokens.py         # HMAC-signed confirmation tokens for order safety
│   ├── osm/
│   │   └── geocoder.py       # Nominatim geocoding + Overpass POI search
│   └── webhooks/
│       └── store.py          # SQLite event store for webhook notifications
├── tests/                     # pytest + pytest-asyncio
│   ├── test_models.py         # Pydantic model validation
│   ├── test_tokens.py         # HMAC token create/validate
│   └── test_webhooks.py       # SQLite event store
├── examples/
│   └── demo_agent.py         # LangChain/LangGraph research agent (372 lines)
├── docs/                      # Integration guides for 7 frameworks
│   ├── langchain-integration.md
│   ├── claude-web-integration.md
│   ├── openai-integration.md
│   ├── adk-integration.md
│   ├── ai-sdk-integration.md
│   ├── anthropic-api-integration.md
│   └── gemini-integration.md
├── Dockerfile                 # Python 3.12-slim, runs skyfi-mcp serve
├── fly.toml                   # Fly.io deployment config
├── pyproject.toml             # hatchling build, CLI entry point, deps
└── .github/
    ├── workflows/ci.yml       # ruff lint + pytest
    ├── ISSUE_TEMPLATE/
    └── pull_request_template.md
```

## Key architectural decisions

### FastMCP (Prefect), not the official `mcp` SDK

We use `from fastmcp import FastMCP` (the Prefect/jlowin package on PyPI: `fastmcp>=2.0.0`), **not** `from mcp.server.fastmcp import FastMCP`. The official SDK's built-in FastMCP had transport issues. The Prefect version provides better Streamable HTTP support.

### ASGI app composition — raw ASGI wrapper, not Starlette Mount

`__main__.py` contains a `_create_combined_app()` function that wraps FastMCP's Starlette app with a thin ASGI dispatcher. This intercepts `/`, `/health`, and `/webhook` before they reach the MCP handler. Everything else (including `/mcp`, lifespan events, SSE streams) passes through to FastMCP untouched.

**Why not Starlette Mount?** FastMCP's `http_app()` returns a `StarletteWithLifespan` object whose `routes` property has no setter. Nesting it inside another Starlette app via `Mount()` breaks lifespan propagation and session management. The raw ASGI wrapper avoids both problems.

**Why not `@mcp.custom_route`?** The `custom_route` decorator is broken in fastmcp >= 2.4 (see jlowin/fastmcp#556). All custom HTTP routes are handled in `__main__.py` instead.

### Human-in-the-loop ordering via HMAC confirmation tokens

SkyFi has no quote/cart API. We implement order safety with a two-step pattern:

1. `get_pricing_options` or `check_feasibility` → returns an HMAC-signed `confirmation_token` (5-minute TTL)
2. `create_archive_order` or `create_tasking_order` → requires that token, validates signature + expiry

Tokens are stateless (HMAC-signed with `{action, context_hash, timestamp}`), so any server instance can validate them. The MCP server instructions tell the AI to always present pricing to the user and get explicit confirmation before calling order tools.

### Dual authentication

- **Local mode:** reads API key from `SKYFI_API_KEY` env var → `~/.skyfi/config.json` file → error
- **Cloud mode:** extracts from `Authorization: Bearer <key>` or `X-Skyfi-Api-Key` header
- Every tool accepts an optional `api_key` parameter for cloud/multi-user deployments

### Async feasibility with auto-polling

The SkyFi feasibility endpoint is async — POST returns a `task_id`, and you poll GET for the result. The `check_feasibility` tool auto-polls every 3 seconds for up to 30 seconds, then falls back to returning the `feasibility_id` for manual polling via `get_feasibility_result`.

### Webhook notifications via SQLite event store

SkyFi sends webhook POSTs to `/webhook` when AOI monitors detect new imagery. Events are stored in a SQLite database (`webhook_events.db`). The `check_new_images` MCP tool reads unread events from this store (poll-based, ChatGPT Pulse-style). Events auto-expire after 30 days.

### OpenStreetMap integration

Three OSM tools let AI agents convert natural language locations to WKT:
- `geocode_location` — Nominatim forward geocode → WKT polygon (uses actual boundary geometry when available, falls back to bounding box or buffer)
- `reverse_geocode_location` — coordinates → place name
- `search_nearby_pois` — Overpass API for finding airports, ports, military bases, etc.

## The 21 MCP tools

| Category | Tool | Description |
|---|---|---|
| Search | `search_archive` | Search satellite image catalog with filters |
| Search | `search_archive_next_page` | Paginate through search results |
| Search | `get_archive_details` | Full metadata for a specific image |
| Pricing | `get_pricing_options` | Get pricing matrix + confirmation token |
| Feasibility | `check_feasibility` | Async feasibility check with auto-poll |
| Feasibility | `get_feasibility_result` | Manual poll for feasibility result |
| Feasibility | `predict_satellite_passes` | Find upcoming satellite passes for an AOI |
| Order | `create_archive_order` | Order existing archive image (requires token) |
| Order | `create_tasking_order` | Order new satellite capture (requires token) |
| Order | `list_orders` | List past orders with pagination |
| Order | `get_order_status` | Detailed order status + event timeline |
| Order | `get_download_url` | Get download URL for image/payload/COG |
| Order | `schedule_redelivery` | Redeliver to S3/GCS/Azure |
| Monitor | `create_aoi_notification` | Set up AOI monitoring webhook |
| Monitor | `list_notifications` | List active monitors |
| Monitor | `get_notification_history` | Trigger history for a monitor |
| Monitor | `delete_notification` | Remove a monitor |
| Monitor | `check_new_images` | Poll local webhook store for new imagery |
| OSM | `geocode_location` | Place name → WKT polygon |
| OSM | `reverse_geocode_location` | Coordinates → place name |
| OSM | `search_nearby_pois` | Overpass POI search |
| Account | `get_account_info` | Budget, payment status, profile |

## SkyFi Platform API

Base URL: `https://app.skyfi.com/platform-api`
Auth header: `X-Skyfi-Api-Key: <key>`
OpenAPI spec: `https://app.skyfi.com/platform-api/openapi.json`

19 endpoints wrapped in `api/client.py`. All request/response models in `api/models.py` use Pydantic v2 with `populate_by_name = True` and camelCase `alias` for API compatibility (the API uses camelCase, Python code uses snake_case).

Key enums: `ApiProvider` (14 satellite providers), `ProductType` (8 types including DAY, SAR, HYPERSPECTRAL), `DeliveryStatus` (14 statuses), `ResolutionLevel` (5 levels).

## Development commands

```bash
# Install in development mode
pip install -e ".[dev]"

# Run the server locally
skyfi-mcp serve                           # Streamable HTTP on :8000
skyfi-mcp serve --port 3000               # Custom port
skyfi-mcp serve --transport stdio          # For local MCP clients

# Configure API key
skyfi-mcp config --init                    # Create ~/.skyfi/config.json template
skyfi-mcp config --show                    # Show current config
export SKYFI_API_KEY="sk-..."              # Or use env var

# Run tests
pytest

# Lint
ruff check src/ tests/

# Docker
docker build -t skyfi-mcp .
docker run -p 8000:8000 -e SKYFI_API_KEY="sk-..." skyfi-mcp

# Fly.io deployment
fly deploy
fly secrets set SKYFI_API_KEY="sk-..."
```

## Server endpoints when running

| Path | Method | Description |
|---|---|---|
| `/` | GET | Landing page JSON (for browsers) |
| `/health` | GET | Health check |
| `/webhook` | POST | SkyFi notification webhook receiver |
| `/mcp` | POST/GET | MCP protocol (Streamable HTTP + SSE) |

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

| Variable | Required | Description |
|---|---|---|
| `SKYFI_API_KEY` | Yes (or config file) | SkyFi Platform API key |
| `SKYFI_BASE_URL` | No | Override API base URL (default: `https://app.skyfi.com/platform-api`) |
| `SKYFI_TOKEN_SECRET` | No | HMAC secret for confirmation tokens (default: built-in) |
| `SKYFI_MCP_DATA_DIR` | No | Directory for SQLite DB (default: `.`) |

## Deployment options

- **Local:** `skyfi-mcp serve` or `python -m skyfi_mcp serve`
- **Docker:** `Dockerfile` included, maps port 8000
- **Fly.io:** `fly.toml` configured with persistent volume for SQLite at `/data`
- **AWS ECS Fargate:** Recommended for AWS (supports streaming, no cold starts)
- **Prefect Horizon:** Free hosting option for FastMCP servers
