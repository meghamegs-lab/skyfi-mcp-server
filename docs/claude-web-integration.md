# Claude Web Integration Guide

This guide shows how to add the SkyFi MCP server as a **Custom Integration** in Claude for web browser access. This enables you to use SkyFi tools directly in Claude.com conversations.

## Overview

Claude supports custom MCP server integrations through the Claude settings. Once configured, you can reference SkyFi tools in conversations just like built-in tools.

## Step-by-Step Setup

### 1. Get Your SkyFi API Key

1. Go to [SkyFi Dashboard](https://app.skyfi.com)
2. Navigate to **Settings** → **API Keys**
3. Copy your API key (starts with `sk_`)

### 2. Add Custom Integration in Claude

1. Open [Claude.com](https://claude.com)
2. Click your **Profile** (bottom left)
3. Select **Settings**
4. Click **Custom Integrations** (or **MCP Servers**)
5. Click **Add Integration**

### 3. Configure SkyFi MCP Server

Fill in the following details:

| Field | Value |
|-------|-------|
| **Name** | SkyFi MCP |
| **Description** | Access satellite imagery from SkyFi platform |
| **Server URL** | `https://skyfi-mcp.fly.dev/mcp` |
| **Transport** | Streamable HTTP |
| **Authentication Type** | Bearer Token |
| **Token** | `your-skyfi-api-key-here` |

**Alternative: Self-Hosted Instance**

If you're running your own SkyFi MCP server:

| Field | Value |
|-------|-------|
| **Server URL** | `https://your-domain.com/mcp` |
| **Authentication Type** | Bearer Token |
| **Token** | Your API key |

### 4. Test the Integration

Once saved, start a new conversation and try:

```
Find satellite imagery of Tokyo from the last 2 weeks
```

Claude will automatically:
1. Use `geocode_location` to find Tokyo's coordinates (if needed)
2. Use `search_satellite_imagery` to find available imagery
3. Present results with thumbnails and pricing

## Using SkyFi Tools in Claude

### Example 1: Simple Imagery Search

**You:** "Show me recent satellite imagery of the Port of Singapore"

**Claude:**
- Geocodes "Port of Singapore" to coordinates
- Searches available imagery
- Returns results with preview images

### Example 2: Pricing and Feasibility

**You:** "How much would a new satellite capture of our warehouse cost?"

**Claude:**
- Uses `preview_order` to retrieve pricing and confirmation token
- Presents costs to you
- Waits for approval before ordering

### Example 3: Setting Up Monitoring

**You:** "Monitor Manhattan for new satellite imagery and tell me when any becomes available"

**Claude:**
- Creates AOI notification with `setup_area_monitoring` (action=create)
- Stores the monitoring ID
- Checks periodically with `check_new_images`

## Authentication Details

### How Headers Are Passed

Claude passes your Bearer token in the `Authorization` header:

```http
POST https://skyfi-mcp.fly.dev/mcp
Authorization: Bearer sk_your_api_key_here
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  ...
}
```

### Secure Token Storage

- Your API key is encrypted in Claude's backend
- Never transmitted to the frontend
- Only used for requests to the MCP server
- Can be revoked anytime from SkyFi Settings

## Available Tools Reference

### Search & Discover

- **`geocode_location`** - Convert place name to WKT polygon
- **`search_satellite_imagery`** - Find archived satellite imagery (includes auto-geocoding)
- **`search_nearby_pois`** - Find points of interest

### Check Pricing & Feasibility

- **`preview_order`** - Get cost estimate and confirmation_token
- **`check_feasibility`** - Check if tasking order is possible

### Place Orders

- **`confirm_order`** - Place archive or tasking orders with confirmation_token
- **`get_download_url`** - Get download links for imagery

### Monitor Areas

- **`setup_area_monitoring`** - Create/list/delete area monitoring
- **`check_new_images`** - Check for updates

### Manage Orders

- **`check_order_status`** - View order history or track specific order progress

### Account

- **`get_account_info`** - Check budget and usage

## Advanced: Custom Conversation Instructions

You can add custom instructions to your Claude profile to always use certain SkyFi workflows:

1. Go to **Settings** → **Custom Instructions**
2. Add instructions like:

```
When users ask about satellite imagery:
1. First geocode their location using geocode_location (or use auto-geocoding in search_satellite_imagery)
2. Search for available imagery using search_satellite_imagery
3. ALWAYS present pricing using preview_order BEFORE placing any order
4. Only create orders after explicit user approval using confirm_order with confirmation_token
5. For long-term monitoring, use setup_area_monitoring
```

## Troubleshooting

### "Integration Failed to Connect"

- Verify your API key is correct
- Check that the API key has proper permissions
- Ensure your firewall allows connections to `skyfi-mcp.fly.dev`

### "Tool Not Available"

- Refresh your browser (`Ctrl+Shift+R` or `Cmd+Shift+R`)
- Remove and re-add the integration
- Check that the server URL is correct

### "Authorization Error"

- Verify the Bearer token is set in settings
- Make sure your API key hasn't expired
- Check the API key format (should start with `sk_`)

### "Timeout Errors"

- Some tools (like `check_feasibility`) poll async operations
- They may take 30-60 seconds
- This is normal for feasibility checks

## What's Next

- **Claude Desktop Integration**: See [anthropic-api-integration.md](anthropic-api-integration.md) for Claude Desktop/API setup
- **LangChain Integration**: See [langchain-integration.md](langchain-integration.md) for Python agent workflows
- **OpenAI Integration**: See [openai-integration.md](openai-integration.md) for OpenAI API compatibility
- **Vercel AI SDK**: See [ai-sdk-integration.md](ai-sdk-integration.md) for Node.js applications
