#!/usr/bin/env python3
"""Simple SkyFi MCP Agent — ~100 lines, no frameworks.

A minimal agent that connects to the SkyFi MCP server and demonstrates
the search → preview → confirm workflow using only the `httpx` library.

Usage:
    export SKYFI_API_KEY="sk-..."
    python examples/simple_agent.py
    python examples/simple_agent.py --mcp-url http://localhost:8000/mcp

This is the bare-minimum integration. For a full-featured agent with
LangChain, multi-turn conversations, and model support, see demo_agent.py.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx


def call_tool(client: httpx.Client, mcp_url: str, tool_name: str, args: dict) -> dict:
    """Call an MCP tool via the /tool/<name> HTTP proxy endpoint.

    This bypasses the MCP protocol and calls tools directly via the REST
    proxy that the Python backend exposes at /tool/<name>.
    """
    # Derive the base URL from the MCP URL (e.g., http://localhost:8000/mcp → http://localhost:8000)
    base_url = mcp_url.rsplit("/mcp", 1)[0]
    url = f"{base_url}/tool/{tool_name}"

    # Inject API key if set
    api_key = os.environ.get("SKYFI_API_KEY")
    if api_key:
        args["api_key"] = api_key

    resp = client.post(url, json=args, timeout=60)
    resp.raise_for_status()
    return resp.json()


def search_imagery(client: httpx.Client, mcp_url: str, location: str, **kwargs) -> dict:
    """Search for satellite imagery at a location."""
    args = {"location": location, "page_size": 5, **kwargs}
    return call_tool(client, mcp_url, "search_satellite_imagery", args)


def preview_order(client: httpx.Client, mcp_url: str, archive_id: str, location: str) -> dict:
    """Preview an archive order to get pricing and a confirmation token."""
    return call_tool(client, mcp_url, "preview_order", {
        "order_type": "ARCHIVE",
        "location": location,
        "archive_id": archive_id,
    })


def confirm_order(client: httpx.Client, mcp_url: str, token: str, archive_id: str, location: str) -> dict:
    """Confirm an order (charges the account)."""
    return call_tool(client, mcp_url, "confirm_order", {
        "confirmation_token": token,
        "order_type": "ARCHIVE",
        "location": location,
        "archive_id": archive_id,
    })


def main():
    parser = argparse.ArgumentParser(description="Simple SkyFi MCP Agent")
    parser.add_argument("--mcp-url", default="http://localhost:8000/mcp", help="MCP server URL")
    parser.add_argument("location", nargs="?", default="Golden Gate Bridge", help="Location to search")
    args = parser.parse_args()

    if not os.environ.get("SKYFI_API_KEY"):
        print("Warning: SKYFI_API_KEY not set. Set it for authenticated access.")

    with httpx.Client() as client:
        # Step 1: Search for imagery
        print(f"\n🔍 Searching for imagery at: {args.location}")
        results = search_imagery(client, args.mcp_url, args.location)

        if "error" in results:
            print(f"Error: {results['error']}")
            sys.exit(1)

        archives = results.get("archives", [])
        print(f"   Found {results.get('total_results', 0)} images ({len(archives)} shown)")

        if not archives:
            print("   No imagery found. Try a different location or date range.")
            sys.exit(0)

        # Show top results
        for i, img in enumerate(archives[:3], 1):
            print(f"\n   [{i}] {img.get('provider', '?')} — {img.get('capture_date', '?')}")
            print(f"       Resolution: {img.get('resolution', '?')}  Cloud: {img.get('cloud_coverage', '?')}%")
            print(f"       Archive ID: {img.get('archive_id', img.get('id', '?'))}")

        # Step 2: Preview order for first result
        first = archives[0]
        archive_id = first.get("archive_id", first.get("id"))
        if not archive_id:
            print("\nNo archive_id in results. Exiting.")
            sys.exit(0)

        print(f"\n💰 Previewing order for archive {archive_id}...")
        preview = preview_order(client, args.mcp_url, archive_id, args.location)

        if "error" in preview:
            print(f"Error: {preview['error']}")
            sys.exit(1)

        token = preview.get("confirmation_token")
        print(f"   Price: ${preview.get('price_full_scene_usd', '?')} USD")
        print(f"   Token valid for: {preview.get('token_valid_for_seconds', '?')}s")

        # Step 3: Ask user for confirmation (human-in-the-loop)
        print(f"\n⚠️  Placing this order will charge your account.")
        answer = input("   Confirm order? [y/N]: ").strip().lower()

        if answer == "y" and token:
            print("\n📡 Placing order...")
            order = confirm_order(client, args.mcp_url, token, archive_id, args.location)
            if "error" in order:
                print(f"Error: {order['error']}")
            else:
                print(f"   Order placed! ID: {order.get('order_id')}")
                print(f"   Cost: ${order.get('order_cost_usd', '?')} USD")
                print(f"   Status: {order.get('delivery_status')}")
        else:
            print("   Order cancelled.")

        print("\nDone.")


if __name__ == "__main__":
    main()
