# Pre-Search Design Document — SkyFi MCP Server

## 1. Problem Statement

As AI systems become increasingly autonomous, they encompass a larger share of purchasing decisions. This trend, already visible in software development (Supabase, Vercel, Fly.io) and research (Firecrawl, Exa, Tavily), will spread to other verticals as agents are deployed. SkyFi needs a bridge between conversational AI and satellite imagery ordering — a remote MCP server that exposes the full SkyFi Platform API to any AI agent.

## 2. Business Context: Why MCP Matters for SkyFi

### The Agentic Purchasing Shift

AI agents are becoming the primary interface for discovery and procurement across industries. In software development, companies like Vercel and Supabase have already seen significant revenue driven by AI-recommended tooling. Research platforms like Firecrawl, Exa, and Tavily were built agent-first and have captured the AI-native research market. The satellite imagery industry is next.

### SkyFi's Strategic Position

SkyFi aggregates 14+ satellite providers (Planet, Umbra, Satellogic, etc.) into a single API — effectively becoming the "Stripe of satellite imagery." This aggregation model is ideally suited for MCP integration because:

- **Single API, many providers** — An AI agent gets access to the entire satellite constellation ecosystem through one MCP server, rather than needing separate integrations per provider.
- **Conversational ordering** — Satellite imagery ordering is inherently complex (resolution, cloud cover, off-nadir angle, product type, feasibility windows). Natural language makes it accessible to non-GIS users.
- **Human-in-the-loop alignment** — Satellite imagery orders are high-value transactions ($100s–$10,000s). The MCP confirmation token pattern aligns perfectly with responsible AI purchasing.

### Revenue Opportunity

By being the first satellite imagery platform with a polished MCP integration, SkyFi positions itself as the default satellite data provider for every AI agent. As autonomous agents grow from research assistants to procurement agents, being the tool they reach for translates directly to order volume.

### Open-Source as Distribution

Open-sourcing the MCP server serves as a distribution channel: developers building geospatial AI agents will discover SkyFi through the MCP ecosystem. The 7 framework integration guides (LangChain, OpenAI, Claude, ADK, AI SDK, Anthropic, Gemini) maximize discoverability across the fragmented AI agent ecosystem.

## 3. Competitor & Landscape Analysis

### Satellite Imagery API Competitors

| Provider | Has MCP? | API Approach | Notes |
|----------|----------|-------------|-------|
| **SkyFi** (this project) | Yes (first) | Aggregator — 14+ providers via single API | First mover in MCP for satellite imagery |
| **Planet** | No | Direct API, per-provider | Largest constellation, no agent integration |
| **Maxar** | No | Direct API, enterprise-focused | High resolution, no self-serve agent support |
| **UP42** | No | Marketplace/API | Similar aggregation model, no MCP |
| **SatVu** | No | Direct API, thermal | Niche (thermal), no agent integration |
| **Umbra** | No | Direct API, SAR-only | SAR-specific, no MCP |

**Key insight:** No satellite imagery provider currently has an MCP integration. SkyFi will be first-to-market.

### MCP Ecosystem Competitors (Adjacent Verticals)

| MCP Server | Domain | Relevance |
|------------|--------|-----------|
| **Firecrawl MCP** | Web scraping/research | Similar "agent-native API" pattern |
| **Stripe MCP** | Payments | Reference for financial transaction safety |
| **GitHub MCP** | Code hosting | Reference for authenticated multi-user MCP |
| **Brave Search MCP** | Web search | Reference for search + pagination patterns |

**Patterns borrowed:**
- From Stripe MCP: confirmation tokens for financial safety
- From GitHub MCP: dual auth (local config + cloud headers)
- From Brave Search MCP: paginated search with cursor-based navigation

### Differentiation

SkyFi's MCP server differentiates through:
1. **Human-in-the-loop safety** — HMAC tokens prevent unauthorized purchases (most MCP servers don't handle financial transactions)
2. **OSM integration** — Built-in geocoding so agents can work with place names, not WKT polygons
3. **Webhook-to-poll bridge** — Converts SkyFi's push notifications into a poll-based pattern compatible with current MCP limitations
4. **Comprehensive framework support** — 7 integration guides vs. most MCP servers that document 1-2 frameworks

## 4. Scope & Constraints

**Delivery timeline:** 16 hours (original ask), actual target <24 hours including documentation.

**Language:** Python (SkyFi preference).

**Target users:** AI agent developers integrating satellite imagery into their workflows.

**Non-functional requirements:**
- Production-ready for open-source release
- Support for 7+ AI frameworks
- Human-in-the-loop safety for all financial transactions
- Both local and cloud deployment modes

## 5. Requirements Analysis

### 3.1 Core Infrastructure (R1, R13, R14)

**What:** A remote MCP server built on SkyFi's public API, hostable locally, using stateless HTTP + SSE.

**Design questions explored:**
- **Which MCP library?** Evaluated the official `mcp` SDK vs Prefect's `fastmcp`. Chose Prefect fastmcp for better Streamable HTTP support.
- **Which transport?** Streamable HTTP (modern, replaces deprecated HTTP+SSE) + stdio for local clients.
- **Deployment targets?** Local (uvicorn), Docker, Fly.io, AWS ECS Fargate.
- **ASGI composition?** FastMCP returns a `StarletteWithLifespan` object — can't modify routes. Solved with raw ASGI wrapper.

**Alternatives considered:**
- TypeScript on Cloudflare Workers — rejected (SkyFi prefers Python, Cloudflare not mandatory)
- Official `mcp` SDK — rejected (transport issues with Streamable HTTP)
- Starlette `Mount()` — rejected (breaks lifespan propagation with `StarletteWithLifespan`)

### 3.2 API Client & Data Models (R1)

**What:** Typed client for all 19 SkyFi API endpoints with Pydantic models from the OpenAPI spec.

**Design questions explored:**
- **Sync vs async?** Async (httpx) — MCP tools are async, avoids blocking.
- **Code generation vs hand-written?** Hand-written from OpenAPI spec. Generated 57 Pydantic models with camelCase aliases.
- **Error handling?** Custom `SkyFiAPIError` with status code and detail. Every tool wraps errors gracefully.

**Key API quirks discovered:**
- `GET /orders` takes a JSON request body (unusual but per spec)
- `POST /feasibility` is async — returns task_id, requires polling
- Download endpoints return redirects (301/302) to signed URLs

### 3.3 Authentication (R12, R15, R16)

**What:** Dual auth supporting local development and cloud multi-user deployment.

**Design questions explored:**
- **Config file format?** JSON at `~/.skyfi/config.json` — simple, no dependencies.
- **Resolution order?** Env var → config file → error (env var wins for CI/CD).
- **Cloud auth header?** Both `Authorization: Bearer` and `X-Skyfi-Api-Key` for flexibility.
- **Per-tool override?** Every tool accepts optional `api_key` parameter.

### 3.4 Search & Discovery (R6)

**What:** Iterative archive search with pagination and comprehensive filtering.

**Design questions explored:**
- **Pagination model?** Cursor-based (SkyFi provides `next_page` tokens).
- **Filter exposure?** All 11 API filters exposed as optional tool parameters.
- **Result format?** Flattened JSON with key fields (not raw API response) for better agent comprehension.

### 3.5 Human-in-the-Loop Safety (R3, R4)

**What:** Prevent AI agents from placing orders without human confirmation.

**Design questions explored:**
- **Quote/cart API?** SkyFi doesn't have one. Need custom safety mechanism.
- **Server-side state?** No — stateless HMAC tokens for horizontal scalability.
- **Token scope?** Action-bound (e.g., "order"), context-hashed, time-limited (5 min TTL).
- **What if agent ignores instructions?** Token required at the API level — can't bypass server-side validation.

**Alternatives considered:**
- Session-based approval (requires server state, breaks horizontal scaling)
- Client-side confirmation only (agent could skip it — not safe)
- Separate approval endpoint (adds complexity, still needs tokens)

### 3.6 Feasibility & Pricing (R5, R8, R9)

**What:** Let agents explore what's possible before committing to orders.

**Design questions explored:**
- **Async feasibility handling?** Auto-poll (3s intervals, 30s timeout) with fallback to manual polling.
- **Pass prediction?** Expose `predict_satellite_passes` for forward-looking feasibility.
- **Pricing scope?** Global pricing matrix + AOI-specific pricing.

### 3.7 Order Management (R2, R7)

**What:** Full order lifecycle — create, list, status, download, redeliver.

**Design questions explored:**
- **Order types?** Both ARCHIVE (existing imagery) and TASKING (new capture).
- **Download handling?** Follow redirects to signed URLs, return the URL to the agent.
- **Redelivery?** Support S3, GCS, Azure as delivery targets.

### 3.8 AOI Monitoring & Webhooks (R10, R11)

**What:** Set up persistent monitoring and get notified when new imagery is available.

**Design questions explored:**
- **Webhook storage?** SQLite — zero external dependencies, works everywhere.
- **Event consumption model?** Poll-based with read/unread tracking (ChatGPT Pulse-style).
- **Event TTL?** 30 days auto-cleanup.
- **Why not real-time push?** MCP protocol doesn't support server-initiated notifications. Poll is the standard pattern.

### 3.9 OSM Integration (R17)

**What:** Convert natural language locations to WKT polygons for SkyFi API calls.

**Design questions explored:**
- **Which geocoder?** Nominatim — free, no API key needed, returns actual boundary geometry.
- **WKT generation?** Use Shapely for geometry manipulation (boundary → WKT, bbox → WKT, point buffer → WKT).
- **POI search?** Overpass API for finding specific feature types (airports, ports, military bases).

### 3.10 Documentation (R18)

**What:** Integration guides for 7 AI frameworks.

**Design questions explored:**
- **Full examples vs config guides?** 3 full working examples (LangChain, Claude Web, OpenAI) + 4 config guides (ADK, AI SDK, Anthropic API, Gemini).
- **Why this split?** LangChain/OpenAI/Claude Web are highest adoption. Others need less hand-holding.

### 3.11 Demo Agent (R19)

**What:** A polished research agent demonstrating the full MCP capability.

**Design questions explored:**
- **Framework?** LangChain + LangGraph — most popular, good MCP adapter support.
- **Research flow?** Geocode → search → feasibility → pricing → comparative brief.
- **LLM support?** Both OpenAI and Anthropic models.

## 6. Technology Stack Decision Matrix

| Component | Chosen | Alternatives Considered | Rationale |
|-----------|--------|------------------------|-----------|
| Language | Python 3.11+ | TypeScript | SkyFi preference, team familiarity |
| MCP Library | fastmcp (Prefect) | official mcp SDK | Better Streamable HTTP support |
| HTTP Client | httpx | aiohttp, requests | Async-native, clean API, timeout handling |
| Data Models | Pydantic v2 | dataclasses, attrs | Validation, serialization, alias support |
| Geocoding | Nominatim + Shapely | Google Maps, Mapbox | Free, no API key, boundary geometry |
| POI Search | Overpass API | Google Places | Free, comprehensive OSM data |
| Webhook Store | SQLite | Redis, PostgreSQL | Zero dependencies, file-based, portable |
| Token Signing | HMAC-SHA256 | JWT, server-side sessions | Stateless, simple, no dependencies |
| Build System | hatchling | setuptools, flit | Modern, minimal config |
| Deployment | Fly.io + Docker | Cloudflare Workers, AWS Lambda | Supports streaming, persistent volumes |
| Demo Agent | LangChain + LangGraph | CrewAI, AutoGen | Most popular, best MCP support |

## 7. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| FastMCP API changes | Medium | High | Pin version, ASGI wrapper isolates us |
| SkyFi API changes | Low | High | Pydantic models validate at runtime |
| Agent bypasses confirmation | Low | Critical | Server-side token validation (can't bypass) |
| SQLite concurrency under load | Medium | Medium | Single-writer is fine for webhook volume |
| OSM Nominatim rate limits | Medium | Low | User-Agent header, caching, fallback buffer |
| Token secret exposure | Low | High | Configurable via env var, default for dev only |
