"""CLI entry point for the SkyFi MCP server.

Usage:
    skyfi-mcp serve [--host HOST] [--port PORT]
    skyfi-mcp serve --transport stdio
    python -m skyfi_mcp serve
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

logger = logging.getLogger("skyfi_mcp")


def main():
    parser = argparse.ArgumentParser(
        prog="skyfi-mcp",
        description="SkyFi MCP Server — Satellite imagery via Model Context Protocol",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # serve command
    serve_parser = subparsers.add_parser("serve", help="Start the MCP server")
    serve_parser.add_argument(
        "--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)"
    )
    serve_parser.add_argument(
        "--port", type=int, default=8000, help="Port to bind to (default: 8000)"
    )
    serve_parser.add_argument(
        "--transport",
        choices=["streamable-http", "sse", "stdio"],
        default="streamable-http",
        help="MCP transport type (default: streamable-http)",
    )

    # config command
    config_parser = subparsers.add_parser("config", help="Show or set configuration")
    config_parser.add_argument("--init", action="store_true", help="Create initial config file")
    config_parser.add_argument("--show", action="store_true", help="Show current config")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "config":
        _handle_config(args)
    elif args.command == "serve":
        _handle_serve(args)


def _handle_config(args):
    """Handle config subcommand."""
    from pathlib import Path

    config_path = Path.home() / ".skyfi" / "config.json"

    if args.init:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        if config_path.exists():
            print(f"Config already exists at {config_path}")
        else:
            config_path.write_text(
                json.dumps(
                    {
                        "api_key": "YOUR_SKYFI_API_KEY_HERE",
                        "base_url": "https://app.skyfi.com/platform-api",
                    },
                    indent=2,
                )
            )
            print(f"Config created at {config_path}")
            print("Edit the file to add your SkyFi API key.")
    elif args.show:
        from skyfi_mcp.auth.config import load_local_config

        config = load_local_config()
        if config:
            masked_key = (
                config.api_key[:8] + "..." + config.api_key[-4:]
                if len(config.api_key) > 12
                else "***"
            )
            print(f"API Key: {masked_key}")
            print(f"Base URL: {config.base_url}")
        else:
            print("No configuration found.")
            print("Run 'skyfi-mcp config --init' or set SKYFI_API_KEY environment variable.")
    else:
        print("Use --init to create config or --show to display current config.")


def _create_combined_app(mcp_server):
    """Create an ASGI app with MCP + custom HTTP routes.

    Strategy: wrap FastMCP's own ASGI app (``http_app()``) with a thin ASGI
    dispatcher that intercepts ``/``, ``/health``, and ``/webhook`` before
    they reach the MCP handler.  Everything else (including ``/mcp``,
    lifespan events, and SSE streams) passes through untouched.

    This avoids mutating FastMCP internals or nesting Starlette apps, which
    both cause hard-to-debug lifespan and routing errors.
    """
    import json as _json

    from skyfi_mcp.webhooks.store import WebhookEventStore

    event_store = WebhookEventStore()

    # -- tiny helpers for raw ASGI responses --------------------------------

    async def _json_response(scope, receive, send, body: dict, status: int = 200):
        payload = _json.dumps(body).encode()
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(payload)).encode()],
            ],
        })
        await send({"type": "http.response.body", "body": payload})

    async def _read_body(receive) -> bytes:
        body = b""
        while True:
            msg = await receive()
            body += msg.get("body", b"")
            if not msg.get("more_body", False):
                break
        return body

    # -- custom route handlers ----------------------------------------------

    async def handle_landing(scope, receive, send):
        await _json_response(scope, receive, send, {
            "name": "SkyFi MCP Server",
            "version": "0.1.0",
            "description": "Satellite imagery via Model Context Protocol",
            "endpoints": {
                "mcp": "/mcp  (MCP protocol — use an MCP client, not a browser)",
                "health": "/health  (GET — health check)",
                "webhook": "/webhook  (POST — SkyFi notification webhook receiver)",
                "tool_proxy": "/tool/<name>  (POST — direct tool invocation for CF Worker proxy)",
            },
            "docs": "https://github.com/skyfi/skyfi-mcp-server",
            "note": (
                "This is an MCP server. Connect with Claude, ChatGPT, "
                "LangChain, or any MCP-compatible client."
            ),
        })

    async def handle_health(scope, receive, send):
        await _json_response(scope, receive, send, {
            "status": "healthy",
            "service": "skyfi-mcp",
            "version": "0.1.0",
            "tools": 12,
        })

    async def handle_webhook(scope, receive, send):
        raw = await _read_body(receive)
        try:
            payload = _json.loads(raw)
        except Exception:
            await _json_response(scope, receive, send, {"error": "Invalid JSON"}, 400)
            return
        notification_id = (
            payload.get("notification_id")
            or payload.get("notificationId")
            or "unknown"
        )
        event_id = event_store.store_event(notification_id, payload)
        logger.info("Webhook received: notification=%s, event=%s", notification_id, event_id)
        await _json_response(scope, receive, send, {"status": "received", "event_id": event_id})

    # -- /tool/<name> proxy endpoints for Cloudflare Worker ------------------

    # Import all tool functions from server.py so the Worker can proxy to them.
    # Each tool function accepts keyword arguments and returns a JSON string.
    from skyfi_mcp.server import (
        search_satellite_imagery,
        check_feasibility,
        get_pricing_overview,
        preview_order,
        confirm_order,
        check_order_status,
        get_download_url,
        setup_area_monitoring,
        check_new_images,
        geocode_location,
        search_nearby_pois,
        get_account_info,
    )

    _tool_registry = {
        "search_satellite_imagery": search_satellite_imagery,
        "check_feasibility": check_feasibility,
        "get_pricing_overview": get_pricing_overview,
        "preview_order": preview_order,
        "confirm_order": confirm_order,
        "check_order_status": check_order_status,
        "get_download_url": get_download_url,
        "setup_area_monitoring": setup_area_monitoring,
        "check_new_images": check_new_images,
        "geocode_location": geocode_location,
        "search_nearby_pois": search_nearby_pois,
        "get_account_info": get_account_info,
    }

    async def handle_tool_proxy(scope, receive, send, tool_name: str):
        """Handle POST /tool/<name> — invoke an MCP tool function directly.

        The Cloudflare Worker proxies each tool call here as:
            POST /tool/<tool_name>  { ...args, api_key?: "..." }
        """
        if tool_name not in _tool_registry:
            await _json_response(scope, receive, send, {
                "error": f"Unknown tool: {tool_name}",
                "available_tools": list(_tool_registry.keys()),
            }, 404)
            return

        raw = await _read_body(receive)
        try:
            args = _json.loads(raw) if raw else {}
        except Exception:
            await _json_response(scope, receive, send, {"error": "Invalid JSON body"}, 400)
            return

        tool_fn = _tool_registry[tool_name]
        try:
            result = await tool_fn(**args)
        except TypeError as e:
            # Argument mismatch — return helpful error
            await _json_response(scope, receive, send, {
                "error": f"Invalid arguments for {tool_name}: {e}",
            }, 400)
            return
        except Exception as e:
            logger.exception("Tool %s raised unexpected error", tool_name)
            await _json_response(scope, receive, send, {
                "error": f"Tool execution error: {e}",
            }, 500)
            return

        # Tool functions return JSON strings — send as raw text/json
        payload = result.encode() if isinstance(result, str) else _json.dumps(result).encode()
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(payload)).encode()],
            ],
        })
        await send({"type": "http.response.body", "body": payload})

    # -- the actual ASGI app ------------------------------------------------

    mcp_app = mcp_server.http_app()

    async def app(scope, receive, send):
        # Pass lifespan and non-HTTP scopes straight to MCP
        if scope["type"] != "http":
            await mcp_app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")

        if path == "/" and method == "GET":
            await handle_landing(scope, receive, send)
        elif path == "/health" and method == "GET":
            await handle_health(scope, receive, send)
        elif path == "/webhook" and method == "POST":
            await handle_webhook(scope, receive, send)
        elif path.startswith("/tool/") and method == "POST":
            tool_name = path[len("/tool/"):]
            await handle_tool_proxy(scope, receive, send, tool_name)
        else:
            # Everything else → FastMCP (handles /mcp, SSE, etc.)
            await mcp_app(scope, receive, send)

    return app


def _handle_serve(args):
    """Handle serve subcommand."""
    from skyfi_mcp.server import mcp

    print("Starting SkyFi MCP Server")
    print(f"  Transport: {args.transport}")

    if args.transport == "stdio":
        print("  Mode: stdio (local MCP client)")
        mcp.run(transport="stdio")
    else:
        import uvicorn

        print(f"  Host: {args.host}:{args.port}")
        print()
        print(f"  MCP endpoint:     http://{args.host}:{args.port}/mcp")
        print(f"  Health check:     http://{args.host}:{args.port}/health")
        print(f"  Webhook receiver: http://{args.host}:{args.port}/webhook")
        print(f"  Landing page:     http://{args.host}:{args.port}/")
        print()

        app = _create_combined_app(mcp)
        uvicorn.run(app, host=args.host, port=args.port, ws="wsproto")


if __name__ == "__main__":
    main()
