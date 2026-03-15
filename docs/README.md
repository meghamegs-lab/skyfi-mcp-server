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

All integrations provide access to the 12 core SkyFi tools:

### Search & Discovery (2 tools)
- `geocode_location` - Convert place names to WKT coordinates
- `search_satellite_imagery` - Find archived satellite imagery (includes auto-geocoding)
- `search_nearby_pois` - Find points of interest

### Pricing & Orders (3 tools)
- `preview_order` - Get cost estimates and confirmation_token
- `check_feasibility` - Verify tasking order feasibility (auto-polls)
- `confirm_order` - Place archive or tasking orders with confirmation_token

### Order Management (2 tools)
- `check_order_status` - View order history or track specific order progress
- `get_download_url` - Get download links

### Monitoring (2 tools)
- `setup_area_monitoring` - Create/list/history/delete area monitoring
- `check_new_images` - Check for new imagery

### Utilities (2 tools)
- `get_account_info` - Check budget and usage
- `get_pricing_overview` - Get general pricing information

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

1. Call `search_satellite_imagery` with location name (auto-geocodes) and filters
2. Or use `geocode_location` first if you need coordinates
3. Review results with pricing

**Example Flow:**
```
"Find satellite imagery of Manhattan"
→ search_satellite_imagery(location_name="Manhattan", max_cloud_coverage_percent=10)
→ [returns list of images with prices]
```

### Search & Order Workflow

1. Call `search_satellite_imagery` to find available imagery (auto-geocodes place names)
2. Call `preview_order` to get pricing matrix and **confirmation_token**
3. Present pricing to user
4. Get explicit user approval
5. Call `confirm_order` with confirmation_token and order_type (ARCHIVE or TASKING)

**Important:** Never skip the confirmation_token step. Orders will be rejected without it.

### Monitor Area for New Imagery

1. Call `setup_area_monitoring` with action=create, location, and webhook URL
2. System will notify you when new imagery becomes available
3. Use `check_new_images` to poll for updates
4. Call `setup_area_monitoring` with action=delete to stop monitoring

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
- Always call `preview_order` to get the confirmation_token
- Get the returned `confirmation_token`
- Pass it to `confirm_order` to place the order
- Tokens expire after 5 minutes (see `token_valid_for_seconds`)

### Timeout on Feasibility Check
- Normal for `check_feasibility` (may take 30+ seconds)
- Uses polling internally
- Long async operations will eventually complete

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
