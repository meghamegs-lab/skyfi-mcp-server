# Golden Evals — SkyFi MCP Server

Golden evals are deterministic, repeatable test scenarios that validate correctness of every MCP tool and system behavior. They serve as both regression tests and acceptance criteria.

## Eval Categories

### Category 1: Tool Availability & Schema Validation

| Eval ID | Description | Expected Result | Priority |
|---------|-------------|-----------------|----------|
| E-001 | MCP `tools/list` returns exactly 22 tools | Tool count = 22, all names match spec | P0 |
| E-002 | Every tool has a description and input schema | No empty descriptions, all params typed | P0 |
| E-003 | Order tools document `confirmation_token` as required | Parameter exists in schema, marked required | P0 |

### Category 2: Search & Discovery

| Eval ID | Scenario | Input | Expected Output | Priority |
|---------|----------|-------|-----------------|----------|
| E-010 | Basic archive search | AOI=WKT polygon, from_date=2024-01-01 | JSON with `archives` array, `total_results`, `next_page` | P0 |
| E-011 | Paginated search | next_page cursor from E-010 | New page of results with updated cursor | P0 |
| E-012 | Search with all filters | cloud<10%, resolution=VERY_HIGH, provider=PLANET | Filtered results matching all criteria | P1 |
| E-013 | Archive detail retrieval | Valid archive_id | Full metadata including footprint, pricing, thumbnails | P0 |
| E-014 | Search with invalid AOI | aoi="not a polygon" | Graceful error message (not a crash) | P1 |
| E-015 | Empty search results | AOI in middle of ocean, narrow date range | `archives: [], total_results: 0` | P1 |

### Category 3: Geocoding & OSM

| Eval ID | Scenario | Input | Expected Output | Priority |
|---------|----------|-------|-----------------|----------|
| E-020 | Geocode known location | "Suez Canal" | WKT POLYGON, lat/lon near 30.45/32.35, display_name | P0 |
| E-021 | Geocode with boundary | "Manhattan" | WKT POLYGON from actual boundary (not just bbox) | P1 |
| E-022 | Geocode unknown place | "xyznonexistent123" | `{"error": "No results found..."}` | P1 |
| E-023 | Reverse geocode | lat=48.8584, lon=2.2945 | display_name contains "Paris" or "Eiffel" | P0 |
| E-024 | POI search airports | lat=40.64, lon=-73.78, type=aeroway | Results include JFK-related features | P1 |
| E-025 | Geocode → Search chain | geocode("LAX") → search_archive(wkt) | Search returns results for LAX area | P0 |

### Category 4: Pricing & Feasibility

| Eval ID | Scenario | Input | Expected Output | Priority |
|---------|----------|-------|-----------------|----------|
| E-030 | Get global pricing | No AOI | Pricing matrix + `confirmation_token` + `token_valid_for_seconds: 300` | P0 |
| E-031 | Get area pricing | AOI = Manhattan polygon | Area-specific pricing + token | P1 |
| E-032 | Check feasibility | AOI + DAY + 30 days window | Score/status + `confirmation_token` | P0 |
| E-033 | Feasibility auto-poll | Slow feasibility response | Polls ≤10 times, returns result or fallback ID | P0 |
| E-034 | Feasibility timeout | Response never completes | Returns `status: pending` + `feasibility_id` after 30s | P1 |
| E-035 | Predict passes | AOI + 7 day window | List of passes with provider, timing, pricing | P1 |

### Category 5: Human-in-the-Loop Token System

| Eval ID | Scenario | Input | Expected Output | Priority |
|---------|----------|-------|-----------------|----------|
| E-040 | Token roundtrip | Create token → validate immediately | `(True, "Valid")` | P0 |
| E-041 | Expired token | Create token → wait >300s → validate | `(False, "Token expired...")` | P0 |
| E-042 | Tampered token | Modify token payload | `(False, "Invalid token signature")` | P0 |
| E-043 | Wrong action | Create token for "order" → validate for "delete" | `(False, "Token is for 'order'...")` | P0 |
| E-044 | Invalid format | Random string as token | `(False, "Invalid token format")` | P1 |
| E-045 | Order without token | Call create_archive_order with no token | Rejection with instructions to get pricing first | P0 |
| E-046 | Order with valid token | Full flow: pricing → token → order | Order placed successfully | P0 |

### Category 6: Ordering

| Eval ID | Scenario | Input | Expected Output | Priority |
|---------|----------|-------|-----------------|----------|
| E-050 | Archive order success | Valid AOI + archive_id + token | `status: order_placed`, order_id, cost_usd | P0 |
| E-051 | Tasking order success | Valid AOI + window + product_type + token | `status: order_placed`, order_id | P0 |
| E-052 | List orders | Default params | Paginated order list with status, cost, dates | P0 |
| E-053 | Order status detail | Valid order_id | Full event timeline + download URLs | P0 |
| E-054 | Download URL | Completed order_id + type=image | Redirect URL to imagery file | P1 |
| E-055 | Redelivery schedule | order_id + S3 config | Redelivery scheduled confirmation | P2 |

### Category 7: AOI Monitoring & Webhooks

| Eval ID | Scenario | Input | Expected Output | Priority |
|---------|----------|-------|-----------------|----------|
| E-060 | Create notification | AOI + webhook URL | notification_id, status: active | P0 |
| E-061 | List notifications | Default | Paginated list of active monitors | P0 |
| E-062 | Notification history | Valid notification_id | Trigger history with timestamps | P1 |
| E-063 | Delete notification | Valid notification_id | Deletion confirmed | P1 |
| E-064 | Webhook receive | POST /webhook with payload | 200 + event stored in SQLite | P0 |
| E-065 | Check new images | After webhook received | Returns unread events, marks as read | P0 |
| E-066 | Check images filtered | notification_id filter | Only events for that notification | P1 |
| E-067 | Re-check after read | Call check_new_images again | 0 events (already marked read) | P0 |
| E-068 | TTL cleanup | Event older than 30 days | Cleaned up on next store_event call | P2 |

### Category 8: Authentication

| Eval ID | Scenario | Input | Expected Output | Priority |
|---------|----------|-------|-----------------|----------|
| E-070 | Local auth from env | SKYFI_API_KEY=sk-test | AuthConfig with api_key=sk-test | P0 |
| E-071 | Local auth from file | ~/.skyfi/config.json with api_key | AuthConfig populated | P0 |
| E-072 | Env overrides file | Both set with different values | Env var value used | P0 |
| E-073 | Cloud auth Bearer | Authorization: Bearer sk-test | AuthConfig with api_key=sk-test | P0 |
| E-074 | Cloud auth header | X-Skyfi-Api-Key: sk-test | AuthConfig with api_key=sk-test | P0 |
| E-075 | No auth available | No env, no file, no header | ValueError raised | P0 |
| E-076 | Tool-level api_key | api_key parameter on any tool | Overrides local config | P1 |

### Category 9: Server Infrastructure

| Eval ID | Scenario | Input | Expected Output | Priority |
|---------|----------|-------|-----------------|----------|
| E-080 | Landing page | GET / | JSON with name, version, endpoints | P0 |
| E-081 | Health check | GET /health | `{"status": "healthy", "tools": 21}` | P0 |
| E-082 | MCP endpoint | POST /mcp with JSON-RPC | Valid MCP response | P0 |
| E-083 | Browser to /mcp | GET /mcp without SSE accept | 406 Not Acceptable (expected) | P1 |
| E-084 | Invalid webhook | POST /webhook with bad JSON | 400 + error message | P1 |
| E-085 | CLI config init | skyfi-mcp config --init | Config file created at ~/.skyfi/ | P1 |
| E-086 | CLI config show | skyfi-mcp config --show | Masked API key displayed | P1 |

### Category 10: End-to-End Agent Workflows

| Eval ID | Scenario | Steps | Expected Outcome | Priority |
|---------|----------|-------|------------------|----------|
| E-090 | Full archive order flow | geocode → search → details → pricing → confirm → order | Order placed with correct archive_id and cost | P0 |
| E-091 | Full tasking order flow | geocode → feasibility → pricing → confirm → order | Tasking order with correct parameters | P0 |
| E-092 | Monitoring setup flow | geocode → create notification → webhook fires → check_new_images | Events retrieved and marked read | P0 |
| E-093 | Research agent flow | Place name → geocode → search → feasibility → pass prediction → brief | Complete research output | P1 |
| E-094 | Multi-page search | search → next_page → next_page → select | Correct pagination across 3+ pages | P1 |
| E-095 | Order rejection flow | Try order without pricing step | Token rejection + helpful instructions | P0 |

---

## Running Evals

### Unit Evals (existing)
```bash
pytest tests/ -v  # 51 tests covering models, tokens, webhooks
```

### Integration Evals (with mocked API)
```bash
pytest tests/ -v -m integration  # requires respx mocking
```

### End-to-End Evals (with live API)
```bash
SKYFI_API_KEY=sk-test pytest tests/e2e/ -v  # requires valid API key
```

### MCP Protocol Evals
```bash
# Use the MCP inspector or any MCP client
npx @modelcontextprotocol/inspector http://localhost:8000/mcp
```
