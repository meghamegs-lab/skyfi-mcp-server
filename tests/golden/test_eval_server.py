"""Golden Evals E-080 to E-086: Server Infrastructure.

These evals verify the ASGI app composition, custom HTTP routes,
health check, and CLI config commands.
"""

from __future__ import annotations

import json
import pytest


# ── E-080: Landing Page ──────────────────────────────────────────────────────

class TestE080LandingPage:
    """E-080: GET / returns JSON with name, version, endpoints."""

    @pytest.fixture
    def app(self):
        from skyfi_mcp.__main__ import _create_combined_app
        from skyfi_mcp.server import mcp
        return _create_combined_app(mcp)

    @pytest.mark.asyncio
    async def test_landing_returns_200(self, app):
        response = await _simulate_request(app, "GET", "/")
        assert response["status"] == 200

    @pytest.mark.asyncio
    async def test_landing_has_required_fields(self, app):
        response = await _simulate_request(app, "GET", "/")
        body = json.loads(response["body"])
        assert "name" in body
        assert "version" in body
        assert "endpoints" in body
        assert body["name"] == "SkyFi MCP Server"

    @pytest.mark.asyncio
    async def test_landing_lists_endpoints(self, app):
        response = await _simulate_request(app, "GET", "/")
        body = json.loads(response["body"])
        endpoints = body["endpoints"]
        assert "mcp" in endpoints
        assert "health" in endpoints
        assert "webhook" in endpoints


# ── E-081: Health Check ──────────────────────────────────────────────────────

class TestE081HealthCheck:
    """E-081: GET /health returns healthy status."""

    @pytest.fixture
    def app(self):
        from skyfi_mcp.__main__ import _create_combined_app
        from skyfi_mcp.server import mcp
        return _create_combined_app(mcp)

    @pytest.mark.asyncio
    async def test_health_returns_200(self, app):
        response = await _simulate_request(app, "GET", "/health")
        assert response["status"] == 200

    @pytest.mark.asyncio
    async def test_health_has_status_field(self, app):
        response = await _simulate_request(app, "GET", "/health")
        body = json.loads(response["body"])
        assert body["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_has_service_name(self, app):
        response = await _simulate_request(app, "GET", "/health")
        body = json.loads(response["body"])
        assert body["service"] == "skyfi-mcp"

    @pytest.mark.asyncio
    async def test_health_reports_tool_count(self, app):
        response = await _simulate_request(app, "GET", "/health")
        body = json.loads(response["body"])
        assert "tools" in body
        assert isinstance(body["tools"], int)
        assert body["tools"] >= 12


# ── E-082: Webhook Endpoint ──────────────────────────────────────────────────

class TestE082WebhookEndpoint:
    """E-082: POST /webhook stores events and returns correct response."""

    @pytest.fixture
    def app(self):
        from skyfi_mcp.__main__ import _create_combined_app
        from skyfi_mcp.server import mcp
        return _create_combined_app(mcp)

    @pytest.mark.asyncio
    async def test_webhook_valid_payload(self, app):
        payload = json.dumps({
            "notification_id": "notif-test-123",
            "archive_id": "arch-456",
        }).encode()
        response = await _simulate_request(app, "POST", "/webhook", body=payload)
        assert response["status"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "received"
        assert "event_id" in body

    @pytest.mark.asyncio
    async def test_webhook_camel_case_notification_id(self, app):
        payload = json.dumps({
            "notificationId": "notif-camel",
            "data": "test",
        }).encode()
        response = await _simulate_request(app, "POST", "/webhook", body=payload)
        assert response["status"] == 200

    @pytest.mark.asyncio
    async def test_webhook_missing_notification_id(self, app):
        payload = json.dumps({"data": "no-notif-id"}).encode()
        response = await _simulate_request(app, "POST", "/webhook", body=payload)
        assert response["status"] == 200  # still accepted, uses "unknown"

    @pytest.mark.asyncio
    async def test_webhook_invalid_json(self, app):
        response = await _simulate_request(app, "POST", "/webhook", body=b"not json")
        assert response["status"] == 400
        body = json.loads(response["body"])
        assert "error" in body


# ── E-084: Invalid Webhook Payloads ──────────────────────────────────────────

class TestE084InvalidWebhook:
    """E-084: POST /webhook with bad data returns 400."""

    @pytest.fixture
    def app(self):
        from skyfi_mcp.__main__ import _create_combined_app
        from skyfi_mcp.server import mcp
        return _create_combined_app(mcp)

    @pytest.mark.asyncio
    async def test_empty_body(self, app):
        response = await _simulate_request(app, "POST", "/webhook", body=b"")
        assert response["status"] == 400

    @pytest.mark.asyncio
    async def test_malformed_json(self, app):
        response = await _simulate_request(app, "POST", "/webhook", body=b"{bad json")
        assert response["status"] == 400

    @pytest.mark.asyncio
    async def test_binary_garbage(self, app):
        response = await _simulate_request(app, "POST", "/webhook", body=b"\x00\x01\xff")
        assert response["status"] == 400


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _simulate_request(
    app,
    method: str,
    path: str,
    body: bytes = b"",
) -> dict:
    """Simulate a raw ASGI HTTP request and capture the response."""
    response_started = False
    status_code = None
    response_body = b""
    headers = []

    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": b"",
        "headers": [
            [b"content-type", b"application/json"],
            [b"content-length", str(len(body)).encode()],
        ],
        "root_path": "",
        "scheme": "http",
        "server": ("localhost", 8000),
    }

    body_sent = False

    async def receive():
        nonlocal body_sent
        if not body_sent:
            body_sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        nonlocal response_started, status_code, response_body, headers
        if message["type"] == "http.response.start":
            response_started = True
            status_code = message["status"]
            headers = message.get("headers", [])
        elif message["type"] == "http.response.body":
            response_body += message.get("body", b"")

    await app(scope, receive, send)

    return {
        "status": status_code,
        "body": response_body,
        "headers": headers,
    }
