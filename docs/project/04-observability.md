# Observability Strategy — SkyFi MCP Server

## Current State

The server currently has **basic observability** through Python's `logging` module. Here's what exists and what's missing.

### What We Have

| Layer | Mechanism | Location |
|-------|-----------|----------|
| Application logs | `logging.getLogger("skyfi_mcp")` | `server.py`, `__main__.py` |
| Webhook event logging | `logger.info` on webhook receipt | `__main__.py` (ASGI wrapper) |
| Error formatting | `_format_error()` returns structured error strings | `server.py` |
| Health endpoint | `GET /health` returns service status | `__main__.py` |
| SQLite event store | Queryable webhook event history | `webhooks/store.py` |

### What's Missing

| Gap | Impact | Priority |
|-----|--------|----------|
| No structured logging (JSON) | Hard to parse in log aggregators | P1 |
| No request tracing / correlation IDs | Can't trace a request across tool calls | P1 |
| No metrics (latency, error rates, tool usage) | No insight into performance or usage patterns | P1 |
| No SkyFi API call instrumentation | Can't measure upstream API latency or errors | P1 |
| No token validation metrics | No visibility into rejected orders | P2 |
| No alerting | No notification on errors or anomalies | P2 |
| No distributed tracing | Can't trace across agent → MCP → SkyFi API | P3 |

---

## Recommended Observability Stack

### Tier 1: Structured Logging (Low effort, high impact)

Replace basic logging with structured JSON output. This makes logs parseable by any log aggregator (CloudWatch, Datadog, ELK, Fly.io logs).

```python
# Proposed: Add to __main__.py
import logging
import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "tool_name"):
            log_entry["tool_name"] = record.tool_name
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        return json.dumps(log_entry)
```

### Tier 2: Tool Call Instrumentation (Medium effort, high impact)

Wrap every MCP tool with timing and outcome tracking.

```python
# Proposed: Decorator for tool instrumentation
import time
import functools

def instrument_tool(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        tool_name = func.__name__
        start = time.monotonic()
        try:
            result = await func(*args, **kwargs)
            duration_ms = (time.monotonic() - start) * 1000
            logger.info(
                "Tool call completed",
                extra={
                    "tool_name": tool_name,
                    "duration_ms": round(duration_ms, 2),
                    "status": "success",
                },
            )
            return result
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            logger.error(
                "Tool call failed",
                extra={
                    "tool_name": tool_name,
                    "duration_ms": round(duration_ms, 2),
                    "status": "error",
                    "error_type": type(e).__name__,
                },
            )
            raise
    return wrapper
```

### Tier 3: SkyFi API Client Metrics (Medium effort, high impact)

Add httpx event hooks to track upstream API performance.

```python
# Proposed: Add to api/client.py
async def _log_request(request):
    logger.debug("SkyFi API request", extra={
        "method": request.method,
        "url": str(request.url),
    })

async def _log_response(response):
    request = response.request
    logger.info("SkyFi API response", extra={
        "method": request.method,
        "url": str(request.url),
        "status_code": response.status_code,
        "elapsed_ms": response.elapsed.total_seconds() * 1000 if response.elapsed else None,
    })

# In SkyFiClient.__init__:
self._client = httpx.AsyncClient(
    event_hooks={"request": [_log_request], "response": [_log_response]},
    ...
)
```

### Tier 4: Prometheus Metrics Endpoint (Higher effort, production-grade)

For production deployments, expose a `/metrics` endpoint with Prometheus-compatible metrics.

Key metrics to track:
- `skyfi_mcp_tool_calls_total` (counter, labels: tool_name, status)
- `skyfi_mcp_tool_duration_seconds` (histogram, labels: tool_name)
- `skyfi_mcp_api_requests_total` (counter, labels: method, endpoint, status_code)
- `skyfi_mcp_api_duration_seconds` (histogram, labels: endpoint)
- `skyfi_mcp_token_validations_total` (counter, labels: result — valid/expired/tampered/wrong_action)
- `skyfi_mcp_webhook_events_total` (counter)
- `skyfi_mcp_active_sessions` (gauge)

### Tier 5: Distributed Tracing (Future)

For tracing requests across agent → MCP server → SkyFi API:
- OpenTelemetry SDK with OTLP exporter
- Trace context propagation via headers
- Span per tool call, span per API request
- Integration with Jaeger, Zipkin, or cloud-native tracing (X-Ray, Cloud Trace)

---

## Health Check Enhancement

The current `/health` endpoint is basic. Enhance it for production:

```python
async def handle_health(scope, receive, send):
    # Check SQLite connectivity
    try:
        event_store.get_recent_events(hours=1, limit=1)
        db_status = "ok"
    except Exception:
        db_status = "error"

    # Check SkyFi API reachability (optional, cached)
    api_status = "unchecked"  # Don't hit API on every health check

    status_code = 200 if db_status == "ok" else 503
    await _json_response(scope, receive, send, {
        "status": "healthy" if status_code == 200 else "degraded",
        "service": "skyfi-mcp",
        "version": "0.1.0",
        "tools": 22,
        "checks": {
            "sqlite": db_status,
            "skyfi_api": api_status,
        },
    }, status=status_code)
```

---

## Deployment-Specific Observability

| Platform | Logging | Metrics | Tracing |
|----------|---------|---------|---------|
| **Local** | Console JSON logs | None needed | None needed |
| **Fly.io** | `fly logs` (stdout capture) | Fly Metrics (built-in) | None |
| **AWS ECS** | CloudWatch Logs | CloudWatch Metrics | X-Ray |
| **Docker** | Docker logging driver | Prometheus + Grafana | Jaeger |

---

## Implementation Priority

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| P0 | Structured JSON logging | 1 hour | High — enables all log analysis |
| P1 | Tool call instrumentation | 2 hours | High — visibility into tool usage |
| P1 | SkyFi API client metrics | 1 hour | High — upstream latency tracking |
| P2 | Enhanced health check | 30 min | Medium — production readiness |
| P2 | Token validation metrics | 30 min | Medium — security visibility |
| P3 | Prometheus /metrics endpoint | 4 hours | High — full production metrics |
| P3 | OpenTelemetry tracing | 8 hours | High — distributed tracing |
