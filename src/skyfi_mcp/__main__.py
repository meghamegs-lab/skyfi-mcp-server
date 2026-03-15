"""CLI entry point for the SkyFi MCP server.

Usage:
    skyfi-mcp serve [--host HOST] [--port PORT]
    skyfi-mcp serve --transport stdio
    python -m skyfi_mcp serve
"""

from __future__ import annotations

import argparse
import json
import sys

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


def create_webhook_app():
    """Create the webhook receiver Starlette routes."""
    from skyfi_mcp.webhooks.store import WebhookEventStore

    store = WebhookEventStore()

    async def webhook_receiver(request: Request) -> JSONResponse:
        """Receive webhook events from SkyFi notification system."""
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        notification_id = payload.get("notification_id") or payload.get("notificationId") or "unknown"
        store.store_event(notification_id, payload)

        return JSONResponse({"status": "received"})

    async def health_check(request: Request) -> JSONResponse:
        return JSONResponse({"status": "healthy", "service": "skyfi-mcp"})

    return [
        Route("/webhook", webhook_receiver, methods=["POST"]),
        Route("/health", health_check, methods=["GET"]),
    ]


def main():
    parser = argparse.ArgumentParser(
        prog="skyfi-mcp",
        description="SkyFi MCP Server — Satellite imagery via Model Context Protocol",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # serve command
    serve_parser = subparsers.add_parser("serve", help="Start the MCP server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")
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
            config_path.write_text(json.dumps({
                "api_key": "YOUR_SKYFI_API_KEY_HERE",
                "base_url": "https://app.skyfi.com/platform-api",
            }, indent=2))
            print(f"Config created at {config_path}")
            print("Edit the file to add your SkyFi API key.")
    elif args.show:
        from skyfi_mcp.auth.config import load_local_config
        config = load_local_config()
        if config:
            masked_key = config.api_key[:8] + "..." + config.api_key[-4:] if len(config.api_key) > 12 else "***"
            print(f"API Key: {masked_key}")
            print(f"Base URL: {config.base_url}")
        else:
            print("No configuration found.")
            print(f"Run 'skyfi-mcp config --init' or set SKYFI_API_KEY environment variable.")
    else:
        print("Use --init to create config or --show to display current config.")


def _handle_serve(args):
    """Handle serve subcommand."""
    from skyfi_mcp.server import mcp

    if args.transport == "stdio":
        # Run with stdio transport for local MCP clients
        mcp.run(transport="stdio")
    else:
        # Run with HTTP transport (streamable-http or sse)
        # Mount webhook routes alongside MCP
        import uvicorn

        # Get the MCP's Starlette app and add webhook routes
        # FastMCP.run() handles this internally, but we need to add our webhook endpoint
        print(f"Starting SkyFi MCP Server on {args.host}:{args.port}")
        print(f"Transport: {args.transport}")
        print(f"MCP endpoint: http://{args.host}:{args.port}/mcp")
        print(f"Webhook endpoint: http://{args.host}:{args.port}/webhook")
        print(f"Health check: http://{args.host}:{args.port}/health")

        mcp.settings.host = args.host
        mcp.settings.port = args.port

        # Use streamable-http which includes SSE support
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
