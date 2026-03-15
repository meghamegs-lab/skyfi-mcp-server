# SkyFi MCP Server Integration Documentation

This directory contains comprehensive integration guides for the SkyFi MCP server across multiple AI platforms and frameworks.

## Quick Links

| Integration | Use Case | Language | Docs |
|---|---|---|---|
| **LangChain** | Python agents, ReAct loops | Python | [langchain-integration.md](langchain-integration.md) |
| **Claude Web** | Browser-based access | Web | [claude-web-integration.md](claude-web-integration.md) |
| **Claude API** | Anthropic API, Claude Code desktop | Python | [anthropic-api-integration.md](anthropic-api-integration.md) |
| **OpenAI** | GPT-4, function calling | Python | [openai-integration.md](openai-integration.md) |
| **Vercel AI SDK** | Next.js, streaming, useChat hook | TypeScript/Node.js | [ai-sdk-integration.md](ai-sdk-integration.md) |
| **Google ADK** | Google Agent Development Kit | Python | [adk-integration.md](adk-integration.md) |
| **Google Gemini** | Gemini API, function calling | Python | [gemini-integration.md](gemini-integration.md) |

## Server Information

**Remote Endpoints:**
- Production: `https://skyfi-mcp.fly.dev/mcp`
- Self-hosted: `https://your-domain.com/mcp`

**Local Development:**
- Stdio: `skyfi-mcp serve --transport stdio`
- HTTP: `http://localhost:8000/mcp`

**Authentication:**
- Pass API key via `Authorization: Bearer <key>` header
- Or configure in `~/.skyfi/config.json` for local mode

**Transport Support:**
- Streamable HTTP (POST JSON-RPC)
- Server-Sent Events (SSE)
- Stdio (local only)

## Available Tools

All integrations provide access to the same SkyFi tools:

### Search & Discovery
- `geocode_location` - Convert place names to WKT coordinates
- `search_archive` - Find archived satellite imagery
- `search_archive_next_page` - Paginate search results
- `get_archive_details` - Get full image metadata

### Pricing & Feasibility
- `get_pricing_options` - Get cost estimates (returns confirmation_token)
- `check_feasibility` - Verify tasking order feasibility
- `predict_satellite_passes` - Find upcoming satellite passes

### Orders
- `create_archive_order` - Order existing archived imagery
- `create_tasking_order` - Request new satellite capture
- `list_orders` - View order history
- `get_order_status` - Track order progress
- `get_download_url` - Get download links
- `schedule_redelivery` - Deliver to cloud storage

### Monitoring
- `create_aoi_notification` - Set up area monitoring
- `list_notifications` - View active monitors
- `get_notification_history` - See notification events
- `check_new_images` - Check for new imagery
- `delete_notification` - Remove monitor

### Geolocation
- `reverse_geocode_location` - Convert coordinates to place names
- `search_nearby_pois` - Find points of interest

### Account
- `get_account_info` - Check budget and usage

## Getting Started

### Step 1: Get Your API Key

1. Visit [SkyFi Dashboard](https://app.skyfi.com)
2. Go to **Settings** → **API Keys**
3. Copy your API key (format: `sk_...`)

### Step 2: Choose Your Integration

**For Web/Browser:**
- Use [Claude Web](claude-web-integration.md)

**For Python Development:**
- Agents: [LangChain](langchain-integration.md)
- API: [Anthropic API](anthropic-api-integration.md) or [OpenAI](openai-integration.md)
- Google: [ADK](adk-integration.md) or [Gemini](gemini-integration.md)

**For Node.js/TypeScript:**
- Next.js apps: [Vercel AI SDK](ai-sdk-integration.md)

### Step 3: Set Environment Variables

```bash
export SKYFI_API_KEY="your-api-key"
# Plus your chosen platform's API key:
export ANTHROPIC_API_KEY="sk-ant-..."
# OR
export OPENAI_API_KEY="sk-..."
# OR
export GOOGLE_API_KEY="..."
```

### Step 4: Follow Platform Guide

Choose your integration above and follow the detailed guide with working examples.

## Common Workflows

### Search for Imagery

1. Use `geocode_location` to convert place name to WKT
2. Call `search_archive` with filters (cloud cover, date, resolution)
3. Review results with pricing
4. Optional: Use `get_archive_details` for full metadata

**Example Flow:**
```
"Find satellite imagery of Manhattan"
→ geocode_location("Manhattan")
→ search_archive(aoi=result_wkt, max_cloud_coverage_percent=10)
→ [returns list of images with prices]
```

### Order Archived Imagery

1. Call `get_pricing_options` to get pricing matrix and **confirmation_token**
2. Present pricing to user
3. Get explicit user approval
4. Call `create_archive_order` with confirmation_token

**Important:** Never skip the confirmation_token step. Orders will be rejected without it.

### Order Fresh Imagery (Tasking)

1. Call `check_feasibility` to verify possibility and get **confirmation_token**
2. Show feasibility score and pricing to user
3. Get explicit user approval
4. Call `create_tasking_order` with confirmation_token

### Monitor Area for New Imagery

1. Call `create_aoi_notification` with location and webhook URL
2. System will notify you when new imagery becomes available
3. Use `check_new_images` to poll for updates
4. Call `delete_notification` to stop monitoring

## Security Best Practices

- Never commit API keys to version control
- Use environment variables for credentials
- For web apps, handle API keys on the backend only
- Rotate API keys periodically
- Use firewall rules for self-hosted servers
- Monitor account usage with `get_account_info`

## Troubleshooting

### "Unauthorized" Error
- Verify API key format (should start with `sk_`)
- Check Bearer token is correctly formatted in headers
- Ensure API key hasn't expired

### "Tool Not Found"
- Verify MCP server URL is accessible
- Check that server is running (for local deployments)
- Confirm network connectivity to server

### "Confirmation Token Required"
- Always call `get_pricing_options` or `check_feasibility` first
- Get the returned `confirmation_token`
- Pass it to the order creation function
- Tokens expire after 5 minutes (see `token_valid_for_seconds`)

### Timeout on Feasibility Check
- Normal for `check_feasibility` (may take 30+ seconds)
- Uses polling internally
- Long async operations will eventually complete
- Use `get_feasibility_result` to check status

## API Response Format

All tools return JSON with structure:

```json
{
  "status": "success|error",
  "data": { /* tool-specific data */ },
  "confirmation_token": "token_if_applicable",
  "token_valid_for_seconds": 300
}
```

## Rate Limiting

- Cloud API: 100 requests/minute per account
- Burst: 10 requests/second
- Order operations: 1 request at a time (queued)

## Support

For issues:
1. Check the integration-specific guide
2. Verify API key and server connectivity
3. Review error message and troubleshooting section
4. Contact SkyFi support at support@skyfi.com

## Documentation Structure

Each integration guide includes:

1. **Prerequisites** - Required packages and setup
2. **Configuration** - How to set up the integration
3. **Full Working Example** - Runnable code you can use immediately
4. **API Details** - Configuration reference and parameters
5. **Error Handling** - Common issues and solutions
6. **What's Next** - Links to other relevant integrations

## Architecture Overview

```
User Query
    ↓
AI Platform (Claude, GPT, Gemini)
    ↓
MCP Client (LangChain, Vercel AI, etc.)
    ↓
SkyFi MCP Server (HTTP/SSE/Stdio)
    ↓
SkyFi API
    ↓
Satellite Imagery Database
```

## Feature Matrix

| Feature | LangChain | Claude Web | Anthropic API | OpenAI | Vercel AI SDK | ADK | Gemini |
|---------|-----------|-----------|---------|--------|---------|-----|--------|
| Search Imagery | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Place Orders | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Streaming | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Multi-turn | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Async | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Production Ready | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

---

**Last Updated:** March 2026

For the latest updates, visit: https://github.com/skyfi/skyfi-mcp-server
