# Phase & Requirements Implementation Map

## Phase Overview

| Phase | Name | Requirements Covered | Status |
|-------|------|---------------------|--------|
| 1 | Core Server Infrastructure | R1, R13, R14 | Complete |
| 2 | SkyFi API Client & Data Models | R1 | Complete |
| 3 | Authentication & Security | R12, R15, R16 | Complete |
| 4 | Search, Pricing & Feasibility Tools | R2, R3, R5, R6, R8, R9 | Complete |
| 5 | Ordering with Human-in-the-Loop | R2, R3, R4, R7 | Complete |
| 6 | AOI Monitoring & Webhooks | R10, R11 | Complete |
| 7 | OSM Integration | R17 | Complete |
| 8 | Documentation, Demo Agent & Open-Source Readiness | R18, R19 | Complete |

---

## All 19 Requirements — Detailed Implementation Map

### R1: Fully deployed remote MCP server built on SkyFi's public API

**Phase:** 1 (infrastructure) + 2 (API client)

**Implementation:**
- `src/skyfi_mcp/server.py` — FastMCP server instance with `from fastmcp import FastMCP` (Prefect's PyPI package, not the official `mcp` SDK)
- `src/skyfi_mcp/__main__.py` — CLI entry point (`skyfi-mcp serve`) with ASGI wrapper for custom routes + MCP protocol at `/mcp`
- `src/skyfi_mcp/api/client.py` — Async httpx client wrapping all 19 SkyFi Platform API endpoints
- `src/skyfi_mcp/api/models.py` — 57 Pydantic v2 models generated from the actual OpenAPI spec at `app.skyfi.com/platform-api/openapi.json`
- `Dockerfile` + `fly.toml` — Container deployment to Fly.io

**How to test:**
- `skyfi-mcp serve` starts the server
- `curl http://localhost:8000/` returns landing page JSON
- `curl http://localhost:8000/health` returns health check
- MCP clients connect to `http://localhost:8000/mcp`
- `pytest tests/test_models.py` validates all 57 Pydantic models

---

### R2: Allows a user to conversationally place a SkyFi image order

**Phase:** 4 (search) + 5 (ordering)

**Implementation:**
- `search_archive` tool — search catalog with filters (date, cloud cover, resolution, provider, product type)
- `get_archive_details` tool — full metadata for a specific image
- `get_pricing_options` tool — returns pricing matrix + `confirmation_token`
- `create_archive_order` tool — places archive order (requires valid token)
- `create_tasking_order` tool — places new capture order (requires valid token)
- Server `instructions` field tells the AI agent to always present pricing and get confirmation first

**How to test:**
- End-to-end: connect MCP client → geocode location → search archive → get pricing → confirm → create order
- Unit: `pytest tests/test_tokens.py` validates token create/validate cycle
- Integration: mock SkyFi API with `respx` and verify full order flow

---

### R3: Must confirm with user the price

**Phase:** 4 + 5

**Implementation:**
- `get_pricing_options` tool returns pricing matrix for all product types and resolutions
- Every pricing response includes a `confirmation_token` and `instructions` field that explicitly tells the agent: "Present these pricing options to the user"
- `create_archive_order` and `create_tasking_order` both validate the token before proceeding

**How to test:**
- Verify `get_pricing_options` response includes `confirmation_token` and `instructions` fields
- Verify order tools reject calls without a valid token (returns error with re-instruction)
- `pytest tests/test_tokens.py::test_validate_token_success`

---

### R4: Require human confirmation before placing order

**Phase:** 5

**Implementation:**
- `src/skyfi_mcp/auth/tokens.py` — `ConfirmationTokenManager` creates HMAC-signed tokens with 5-minute TTL
- Token flow: pricing/feasibility → token issued → agent presents to user → user confirms → agent passes token to order tool → server validates signature + expiry + action type
- Tokens are stateless (HMAC-signed with `{action, context_hash, timestamp}`), so any server instance can validate

**How to test:**
- `pytest tests/test_tokens.py` — 7 test cases covering: creation, validation, expiry, tampering, wrong action, format corruption
- Manual: call `create_archive_order` without a token → get rejection message
- Manual: call with expired token (wait >5 min) → get expiry error

---

### R5: Must check feasibility and report to user before placing order

**Phase:** 4

**Implementation:**
- `check_feasibility` tool — POST to SkyFi `/feasibility` endpoint, auto-polls every 3 seconds for up to 30 seconds
- `get_feasibility_result` tool — manual polling fallback via task_id
- `predict_satellite_passes` tool — find upcoming satellite passes for an AOI
- Feasibility response includes weather score, provider score, overall feasibility score, and a `confirmation_token`
- Response includes `instructions` field telling the agent to present results to user

**How to test:**
- Integration: mock feasibility endpoint → verify auto-poll behavior (3s intervals, 30s timeout)
- Verify fallback: if auto-poll doesn't complete, returns `feasibility_id` for manual polling
- Verify response includes `confirmation_token` for subsequent order placement

---

### R6: Allows user to explore available data through iterative search

**Phase:** 4

**Implementation:**
- `search_archive` tool — accepts 11 filter parameters (AOI, date range, cloud cover, off-nadir angle, resolution, product type, provider, open data, overlap ratio, page size)
- `search_archive_next_page` tool — cursor-based pagination using `next_page` token from previous response
- `get_archive_details` tool — deep-dive into a specific image's full metadata
- Response includes `total_results`, `page_size`, and `next_page` cursor for iterative refinement

**How to test:**
- Integration: mock paginated search responses → verify cursor propagation
- Verify all 11 filter parameters are correctly serialized to the API request
- Verify `search_archive_next_page` correctly passes the cursor

---

### R7: Allows user to explore previous orders and fetch ordered images

**Phase:** 5

**Implementation:**
- `list_orders` tool — paginated order history with filtering by type (ARCHIVE/TASKING), sorting by date/cost/status
- `get_order_status` tool — detailed status with full event timeline for a specific order
- `get_download_url` tool — get download URL for image, payload, or COG deliverable
- `schedule_redelivery` tool — redeliver to S3/GCS/Azure

**How to test:**
- Integration: mock `GET /orders` (note: this endpoint uses GET with a JSON body per SkyFi's spec)
- Verify pagination parameters (page_number, page_size, sort_columns, sort_directions)
- Verify `get_download_url` handles redirect responses (301/302/307/308) and returns the location header

---

### R8: Allows user to explore feasibility of a task

**Phase:** 4

**Implementation:**
- `check_feasibility` tool — full feasibility check with product type, resolution, date window, cloud cover, priority, and provider constraints
- `get_feasibility_result` tool — manual polling for long-running checks
- `predict_satellite_passes` tool — shows upcoming satellite passes with timing, pricing, and capabilities
- Auto-poll mechanism: 3-second intervals, 30-second timeout, graceful fallback

**How to test:**
- Verify `FeasibilityRequest` model serializes all parameters correctly
- Integration: mock async POST → poll GET pattern
- Verify auto-poll terminates on COMPLETE/ERROR status or timeout

---

### R9: Allows user to explore different pricing options

**Phase:** 4

**Implementation:**
- `get_pricing_options` tool — calls `POST /pricing` with optional AOI for area-specific pricing
- Returns full pricing matrix across all product types and resolution levels
- Response includes `confirmation_token` and `token_valid_for_seconds`

**How to test:**
- Integration: mock pricing endpoint with and without AOI
- Verify token is generated and included in response
- Verify `token_valid_for_seconds` matches the configured TTL (300s default)

---

### R10: Allows user to set up AOI monitoring and notifications

**Phase:** 6

**Implementation:**
- `create_aoi_notification` tool — creates webhook-based AOI monitor with GSD and product type filters
- `list_notifications` tool — paginated list of active monitors
- `get_notification_history` tool — trigger history for a specific monitor
- `delete_notification` tool — remove a monitor

**How to test:**
- Integration: mock all 4 notification CRUD endpoints
- Verify `NotificationRequest` model serializes AOI, webhook URL, and filters correctly
- Verify pagination on `list_notifications`

---

### R11: Webhook integration for agent to inform user of new images (ChatGPT Pulse-style)

**Phase:** 6

**Implementation:**
- `src/skyfi_mcp/webhooks/store.py` — SQLite event store (`webhook_events.db`) with TTL-based cleanup (30 days)
- `/webhook` endpoint in `__main__.py` — receives POST from SkyFi, stores in SQLite
- `check_new_images` tool — poll-based retrieval of unread events, with read/unread tracking and notification_id filtering
- Events can be filtered by notification_id and time range

**How to test:**
- `pytest tests/test_webhooks.py` — 10 test cases covering: store event, get unread, mark read, recent events, TTL cleanup, notification filtering
- Integration: POST to `/webhook` with sample payload → verify stored → call `check_new_images` → verify returned and marked read

---

### R12: Authentication and payments support within the MCP

**Phase:** 3

**Implementation:**
- `src/skyfi_mcp/auth/config.py` — `AuthConfig` dataclass generates `X-Skyfi-Api-Key` headers
- `load_local_config()` — env var → config file fallback chain
- `extract_cloud_auth(headers)` — extracts from `Authorization: Bearer` or `X-Skyfi-Api-Key` headers
- Every tool's `_get_client()` helper creates an authenticated `SkyFiClient`
- Payment is handled by SkyFi's API (charges on order creation) — the MCP server passes through the authenticated session

**How to test:**
- Unit: verify `load_local_config()` reads from env var and config file
- Unit: verify `extract_cloud_auth()` extracts from both header formats
- Verify `_get_client()` raises `ValueError` when no credentials found

---

### R13: Ability to host the server locally

**Phase:** 1

**Implementation:**
- `skyfi-mcp serve` — starts uvicorn on `0.0.0.0:8000` by default
- `skyfi-mcp serve --transport stdio` — for local MCP clients (Claude Desktop, Claude Code)
- `pip install -e .` — install from source for local development
- `Dockerfile` — containerized local deployment

**How to test:**
- `skyfi-mcp serve` → verify `http://localhost:8000/health` responds
- `skyfi-mcp serve --transport stdio` → verify stdin/stdout MCP handshake
- `docker build -t skyfi-mcp . && docker run -p 8000:8000 skyfi-mcp` → verify health endpoint

---

### R14: Stateless HTTP + SSE transport

**Phase:** 1

**Implementation:**
- FastMCP's built-in Streamable HTTP transport at `/mcp` endpoint
- `mcp.http_app()` returns a Starlette ASGI app with SSE support
- Raw ASGI wrapper in `__main__.py` intercepts custom routes, passes all MCP traffic through
- Lifespan events (session management, cleanup) propagated from FastMCP untouched

**How to test:**
- Verify `POST /mcp` with MCP protocol headers returns valid JSON-RPC responses
- Verify `GET /mcp` with `Accept: text/event-stream` establishes SSE connection
- Verify browser GET to `/mcp` without SSE accept header returns `406 Not Acceptable` (expected)

---

### R15: Local use with credentials in stored JSON config

**Phase:** 3

**Implementation:**
- `skyfi-mcp config --init` creates `~/.skyfi/config.json` template
- `skyfi-mcp config --show` displays current config with masked API key
- `load_local_config()` reads from `~/.skyfi/config.json` with support for both `api_key` and `apiKey` field names
- Env var `SKYFI_API_KEY` takes priority over config file

**How to test:**
- `skyfi-mcp config --init` → verify file created at `~/.skyfi/config.json`
- `skyfi-mcp config --show` → verify masked key display
- Set `SKYFI_API_KEY` env var → verify it takes priority over config file

---

### R16: Cloud deployment with credentials sent in headers for multi-user access

**Phase:** 3

**Implementation:**
- `extract_cloud_auth(headers)` in `auth/config.py` — supports both `Authorization: Bearer <key>` and `X-Skyfi-Api-Key: <key>`
- Every MCP tool accepts an optional `api_key` parameter — when provided, overrides local config
- Fly.io deployment via `fly.toml` with `fly secrets set SKYFI_API_KEY`
- Dockerfile exposes port 8000 for any container orchestrator

**How to test:**
- Deploy to Fly.io → send request with `X-Skyfi-Api-Key` header → verify tool execution
- Verify multi-user: two different API keys in concurrent requests → verify isolation
- `fly deploy && curl https://your-app.fly.dev/health`

---

### R17: OpenStreetMaps integration

**Phase:** 7

**Implementation:**
- `src/skyfi_mcp/osm/geocoder.py` — 3 functions using Nominatim + Overpass APIs
- `geocode_location` tool — place name → WKT polygon (uses actual OSM boundary geometry when available, falls back to bounding box, then point buffer)
- `reverse_geocode_location` tool — coordinates → place name with address details
- `search_nearby_pois` tool — Overpass API query for finding airports, ports, military bases, etc. within a radius
- All responses are formatted for direct use as SkyFi AOI parameters

**How to test:**
- Integration: mock Nominatim API → verify WKT polygon generation from boundary, bounding box, and point buffer cases
- Integration: mock Overpass API → verify POI search with different feature types
- End-to-end: `geocode_location("Suez Canal")` → verify WKT output → feed to `search_archive`

---

### R18: Comprehensive documentation for ADK, LangChain, AI SDK, Claude Web, OpenAI, Anthropic, Gemini

**Phase:** 8

**Implementation:**
- `docs/langchain-integration.md` — full working example with LangChain MCP adapter
- `docs/claude-web-integration.md` — full working example with Claude Web remote MCP
- `docs/openai-integration.md` — full working example with OpenAI MCP tools
- `docs/adk-integration.md` — config guide for Google Agent Development Kit
- `docs/ai-sdk-integration.md` — config guide for Vercel AI SDK (TypeScript)
- `docs/anthropic-api-integration.md` — config guide for Anthropic API + Claude Code
- `docs/gemini-integration.md` — config guide for Google Gemini function calling + MCP

**How to test:**
- Review each guide for accuracy of import paths, API calls, and configuration
- Verify code examples compile/parse without syntax errors
- Cross-reference MCP endpoint URLs and authentication patterns with actual server behavior

---

### R19: Demo agent for geospatial deep research, polished and ready to open-source

**Phase:** 8

**Implementation:**
- `examples/demo_agent.py` — 372-line LangChain/LangGraph research agent
- Multi-step research flow: geocode → search archive → check feasibility → compare pricing → generate brief
- Supports both OpenAI and Anthropic LLMs as the reasoning engine
- `examples/config/` — example configuration files
- `examples/README.md` — setup instructions and example prompts
- Open-source readiness: `LICENSE` (MIT), `CONTRIBUTING.md`, issue templates, PR template, CI workflow

**How to test:**
- `pip install -e ".[demo]" && python examples/demo_agent.py` with valid API keys
- Verify the agent can complete a full research loop (geocode → search → feasibility → brief)
- `ruff check examples/` for code quality
- Verify all open-source files are present: LICENSE, CONTRIBUTING.md, .github/*, README.md
