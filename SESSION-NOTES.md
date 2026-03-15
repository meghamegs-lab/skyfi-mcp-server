# SkyFi MCP Server — Session Notes

## Date: March 15, 2026

## What Was Built

A remote MCP server wrapping SkyFi's 19 satellite imagery API endpoints as 22 MCP tools. Python + Prefect FastMCP + Streamable HTTP transport.

## Current State: Server Works Locally

- `skyfi-mcp serve` runs on localhost:8000 ✓
- `/health`, `/`, `/webhook` custom routes working ✓
- `/mcp` serves MCP protocol via FastMCP ✓
- All 22 tools registered ✓
- 176 test cases across 11 test files (syntax-validated, not all run due to sandbox network limits)

## Requirements Audit (all 19)

### Fully Implemented AND Verified:
- R1 (deployed MCP server), R4 (HMAC tokens), R11 (webhook store), R12 (dual auth), R13 (local hosting), R14 (HTTP+SSE), R15 (local config), R17 (OSM geocoding)

### Implemented but NEVER Tested Against Live SkyFi API:
- R2 (conversational ordering), R3 (price confirmation), R5 (feasibility), R6 (iterative search), R7 (past orders), R8 (explore feasibility), R9 (pricing options), R10 (AOI monitoring), R16 (cloud multi-user)
- **Critical gap: Zero tests call SkyFiClient against any backend (real or mocked with respx)**
- The GCS→GS enum fix was an example of spec-vs-reality gaps that likely exist elsewhere

### Implemented but Unvalidated:
- R18 (7 framework docs) — files exist, code examples not verified against current SDKs
- R19 (demo agent + open-source) — demo_agent.py exists (372 lines) but never executed

## Key Files Created/Modified This Session

### Code fixes:
- `src/skyfi_mcp/__main__.py` — Raw ASGI wrapper pattern (3rd iteration, final working version)
- `tests/test_models.py` line 224 — Fixed "GCS" → "GS" delivery driver enum

### Documentation (in docs/project/):
1. `01-phase-requirements-map.md` — All 19 requirements mapped to 8 phases
2. `02-architecture.mermaid` — Full Mermaid architecture diagram
3. `03-golden-evals.md` — 95 eval scenarios across 10 categories
4. `04-observability.md` — Observability strategy with 5 tiers
5. `05-presearch-design-document.md` — Design doc with competitor analysis
6. `06-time-estimation-tradeoffs.md` — 24h estimate vs <1h actual, 7 tradeoffs
7. `SkyFi-MCP-Server-Documentation.docx` — Word doc with all 6 deliverables

### Golden eval test files (in tests/golden/):
- `test_eval_tokens.py` — 21 tests (E-040 to E-046)
- `test_eval_webhooks.py` — 17 tests (E-060 to E-068)
- `test_eval_auth.py` — 23 tests (E-070 to E-076)
- `test_eval_server.py` — 14 tests (E-080 to E-084)
- `test_eval_models.py` — 23 tests (E-001 to E-015)
- `test_eval_osm.py` — 14 tests (E-020 to E-025, uses respx mocking)
- `test_eval_e2e.py` — 13 tests (E-090 to E-095)

### Other:
- `CLAUDE.md` — Project context for AI assistants
- `README.md` — Complete rewrite with architecture, tools, deployment
- `SkyFi-MCP-Demo-Script.docx` — 5-minute demo script (11 pages)

## What to Do Next

1. **Connect Claude Desktop** to the running server:
   Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:
   ```json
   {
     "mcpServers": {
       "skyfi": {
         "type": "http",
         "url": "http://localhost:8000/mcp",
         "headers": {
           "Authorization": "Bearer YOUR_SKYFI_API_KEY"
         }
       }
     }
   }
   ```
   Restart Claude Desktop, then test: "Find satellite imagery of the Suez Canal"

2. **Run tests locally** (need network for pip install):
   ```bash
   pip install -e ".[dev]"
   pytest tests/ -v
   ```

3. **Add SkyFi API integration tests** — the biggest gap. Use respx to mock all 19 endpoints.

4. **Run demo_agent.py** with live API keys to validate LangChain integration.

## Architecture Quick Reference

- **FastMCP (Prefect)** not official mcp SDK — `from fastmcp import FastMCP`
- **ASGI wrapper** in __main__.py intercepts /, /health, /webhook; passes /mcp to FastMCP
- **HMAC tokens** — stateless, 5-min TTL, required for order tools
- **Dual auth** — env var → config file (local) OR Bearer/X-Skyfi-Api-Key headers (cloud)
- **Async feasibility** — auto-polls every 3s for 30s, fallback to manual poll
- **SQLite webhook store** — 30-day TTL, read/unread tracking, notification_id filtering

## Known Issues

1. `@mcp.custom_route` broken in fastmcp >= 2.4 (jlowin/fastmcp#556)
2. `StarletteWithLifespan` has read-only routes (solved with raw ASGI wrapper)
3. SkyFi `GET /orders` takes a JSON body (unusual, per their spec)
4. Default HMAC secret is hardcoded — set SKYFI_TOKEN_SECRET in production
