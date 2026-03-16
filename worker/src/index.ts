/**
 * SkyFi MCP Worker — Thin proxy on Cloudflare Workers.
 *
 * This is the "MCP front door." It handles:
 *   - MCP protocol (Streamable HTTP + legacy SSE)
 *   - Tool registration with Zod schemas
 *   - OAuth 2.1 for Claude Web (via @cloudflare/workers-oauth-provider)
 *   - Bearer token extraction for programmatic clients
 *   - Session management via Durable Objects
 *
 * All business logic lives in the Python backend. The Worker only proxies
 * tool calls as HTTP requests to the backend.
 */

import { McpAgent } from "agents/mcp";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import {
  OAuthProvider,
  type OAuthHelpers,
  type AuthRequest,
} from "@cloudflare/workers-oauth-provider";
import { z } from "zod";

// ── Environment Bindings ────────────────────────────────────────────────────

export interface Env {
  MCP_OBJECT: DurableObjectNamespace;
  PYTHON_BACKEND_URL: string;
  SKYFI_OAUTH_CLIENT_ID?: string;
  SKYFI_OAUTH_CLIENT_SECRET?: string;
  COOKIE_ENCRYPTION_KEY?: string;
  OAUTH_KV: KVNamespace;
  OAUTH_PROVIDER?: OAuthHelpers; // Injected by OAuthProvider at runtime
}

// Per-session state stored in the Durable Object
interface SessionState {
  apiKey?: string;
}

// ── Helper: SHA-256 hex hash (same algorithm as the OAuth library) ──────────

async function sha256Hex(input: string): Promise<string> {
  const data = new TextEncoder().encode(input);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}

// ── Helper: Ensure OAuth client exists in KV ────────────────────────────────
//
// The OAuthProvider library stores clients in KV as `client:<id>` and looks
// them up via `env.OAUTH_KV.get("client:<id>")`. Its `createClient()` method
// ignores any clientId you pass and generates a random one. So we must write
// the client record to KV ourselves in the exact format the library expects.

async function ensureClientRegistered(env: Env): Promise<void> {
  const clientId = env.SKYFI_OAUTH_CLIENT_ID!;
  const kvKey = `client:${clientId}`;

  // Hash the secret the same way the library does (SHA-256 hex)
  const rawSecret = env.SKYFI_OAUTH_CLIENT_SECRET ?? "";
  const hashedSecret = rawSecret ? await sha256Hex(rawSecret) : undefined;

  // Write client in the exact ClientInfo format the library expects.
  // Always overwrite to ensure redirect URIs and auth methods stay current.
  const clientInfo = {
    clientId,
    clientSecret: hashedSecret,
    redirectUris: [
      "https://claude.ai/oauth/callback",
      "https://claude.ai/api/mcp/auth_callback",
    ],
    clientName: "SkyFi MCP for Claude",
    grantTypes: ["authorization_code", "refresh_token"],
    responseTypes: ["code"],
    tokenEndpointAuthMethod: "client_secret_post",
    registrationDate: Math.floor(Date.now() / 1000),
  };

  await env.OAUTH_KV.put(kvKey, JSON.stringify(clientInfo));
}

// ── OAuth 2.1 Handler ───────────────────────────────────────────────────────
//
// For Claude Web and other OAuth-based MCP clients. The flow:
//   1. Client redirects user to /authorize
//   2. Worker shows API key entry form
//   3. User enters their SkyFi API key
//   4. Worker validates key, issues OAuth authorization code
//   5. Client exchanges code for access token at /token
//   6. Client uses the access token in Bearer header for MCP calls

async function handleOAuthAuthorize(
  request: Request,
  env: Env,
  oauthHelpers: OAuthHelpers,
): Promise<Response> {
  // Ensure the OAuth client exists in KV before the library tries to look it up
  await ensureClientRegistered(env);

  // Use the library's parser to get a proper AuthRequest object
  const authRequest = await oauthHelpers.parseAuthRequest(request);

  if (!authRequest.clientId || !authRequest.redirectUri) {
    return new Response("Missing required OAuth parameters", { status: 400 });
  }

  // Store the parsed AuthRequest so we can pass it to completeAuthorization later
  const authId = crypto.randomUUID();
  await env.OAUTH_KV.put(
    `auth:${authId}`,
    JSON.stringify(authRequest),
    { expirationTtl: 600 }, // 10 minutes
  );

  // Serve a simple API key entry page
  const html = `<!DOCTYPE html>
<html>
<head>
  <title>SkyFi MCP — Connect Your Account</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
           display: flex; justify-content: center; align-items: center; min-height: 100vh;
           margin: 0; background: #f0f4f8; }
    .card { background: white; border-radius: 12px; padding: 2rem; max-width: 420px;
            width: 90%; box-shadow: 0 4px 24px rgba(0,0,0,0.08); }
    h1 { font-size: 1.4rem; margin-top: 0; }
    p { color: #555; font-size: 0.95rem; line-height: 1.5; }
    input { width: 100%; padding: 0.75rem; border: 1px solid #ddd; border-radius: 8px;
            font-size: 1rem; box-sizing: border-box; margin-bottom: 1rem; }
    button { width: 100%; padding: 0.75rem; background: #2563eb; color: white;
             border: none; border-radius: 8px; font-size: 1rem; cursor: pointer; }
    button:hover { background: #1d4ed8; }
    .info { font-size: 0.8rem; color: #888; margin-top: 1rem; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Connect SkyFi to Claude</h1>
    <p>Enter your SkyFi Platform API key to connect satellite imagery tools.</p>
    <form method="POST" action="/oauth/callback">
      <input type="hidden" name="auth_id" value="${authId}">
      <input type="password" name="api_key" placeholder="sk-..." required autofocus>
      <button type="submit">Connect</button>
    </form>
    <p class="info">Your API key is stored securely and only used to authenticate
    with the SkyFi Platform API. Get a key at
    <a href="https://app.skyfi.com/settings/api" target="_blank">app.skyfi.com</a>.</p>
  </div>
</body>
</html>`;

  return new Response(html, {
    headers: { "Content-Type": "text/html" },
  });
}

async function handleOAuthCallback(
  request: Request,
  env: Env,
  oauthHelpers: OAuthHelpers,
): Promise<Response> {
  // Parse the form submission
  const formData = await request.formData();
  const authId = formData.get("auth_id") as string;
  const apiKey = formData.get("api_key") as string;

  if (!authId || !apiKey) {
    return new Response("Missing auth_id or api_key", { status: 400 });
  }

  // Retrieve the stored AuthRequest object
  const stored = await env.OAUTH_KV.get(`auth:${authId}`);
  if (!stored) {
    return new Response("Authorization session expired. Please try again.", { status: 400 });
  }
  await env.OAUTH_KV.delete(`auth:${authId}`);

  const authRequest = JSON.parse(stored) as AuthRequest;

  // Validate the API key by making a quick whoami call to SkyFi
  try {
    const checkResp = await fetch(`${env.PYTHON_BACKEND_URL}/tool/get_account_info`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: apiKey }),
    });
    if (!checkResp.ok) {
      return new Response(
        "Invalid API key. Please check your key and try again. " +
        '<a href="javascript:history.back()">Go back</a>',
        { status: 401, headers: { "Content-Type": "text/html" } },
      );
    }
  } catch {
    // Backend unreachable — allow anyway (key will fail on actual tool calls)
  }

  // Complete the OAuth flow with the proper AuthRequest object.
  // authRequest.scope is already a string[] from parseAuthRequest.
  // IMPORTANT: userId is used in the auth code format "userId:grantId:secret"
  // and the library splits on ":". The raw API key may contain ":" or other
  // characters that break this format, so we use a safe hash as the userId
  // and store the actual API key in props.
  const safeUserId = await sha256Hex(apiKey);
  const { redirectTo } = await oauthHelpers.completeAuthorization({
    request: authRequest,
    userId: safeUserId,
    metadata: { apiKey },
    scope: authRequest.scope || [],
    props: {
      apiKey,
    },
  });

  // Redirect the user back to Claude with the authorization code
  return new Response(null, {
    status: 302,
    headers: { Location: redirectTo },
  });
}

// ── Helper: Proxy a tool call to the Python backend ─────────────────────────

async function proxyToolCall(
  env: Env,
  toolName: string,
  args: Record<string, unknown>,
  apiKey?: string,
): Promise<string> {
  // Inject the API key so the Python backend can authenticate with SkyFi
  const payload = { ...args };
  if (apiKey) {
    payload.api_key = apiKey;
  }

  const url = `${env.PYTHON_BACKEND_URL}/tool/${toolName}`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const detail = await response.text();
    return JSON.stringify({
      error: `Backend error (${response.status}): ${detail}`,
    });
  }

  return await response.text();
}

// ── McpAgent: 12 tools with Zod schemas ─────────────────────────────────────

export class SkyFiMcpAgent extends McpAgent<Env, SessionState, { apiKey?: string }> {
  // The MCP server instance — required as a class field by McpAgent (abstract property)
  server = new McpServer({
    name: "SkyFi MCP Server",
    version: "0.1.0",
  });

  // Store the API key from the initial connection
  private apiKey?: string;

  async init() {
    // Extract the API key from OAuth token props (set during completeAuthorization).
    if (this.props?.apiKey) {
      this.apiKey = this.props.apiKey;
    }

    // ── Tool 1: search_satellite_imagery ──────────────────────────────────
    this.server.tool(
      "search_satellite_imagery",
      "Search the SkyFi satellite image catalog. Accepts plain location names " +
      "(auto-geocoded) or WKT polygons. Use next_page to paginate.",
      {
        location: z.string().describe("Place name or WKT polygon"),
        from_date: z.string().optional().describe("Start date (ISO format)"),
        to_date: z.string().optional().describe("End date (ISO format)"),
        max_cloud_coverage_percent: z.number().min(0).max(100).optional()
          .describe("Maximum cloud cover (0-100)"),
        max_off_nadir_angle: z.number().min(0).max(50).optional()
          .describe("Maximum off-nadir angle (0-50)"),
        resolutions: z.array(z.string()).optional()
          .describe("Resolution filter: LOW, MEDIUM, HIGH, VERY_HIGH, ULTRA_HIGH"),
        product_types: z.array(z.string()).optional()
          .describe("Product filter: DAY, NIGHT, VIDEO, SAR, HYPERSPECTRAL, MULTISPECTRAL, STEREO"),
        providers: z.array(z.string()).optional()
          .describe("Provider filter: PLANET, UMBRA, SATELLOGIC, etc."),
        open_data: z.boolean().optional().describe("Only return free open data"),
        min_overlap_ratio: z.number().min(0).max(1).optional()
          .describe("Minimum overlap between image and AOI"),
        page_size: z.number().min(1).max(100).default(20).describe("Results per page"),
        next_page: z.string().optional().describe("Pagination cursor from previous search"),
      },
      async (args) => ({
        content: [{
          type: "text" as const,
          text: await proxyToolCall(this.env, "search_satellite_imagery", args, this.apiKey),
        }],
      }),
    );

    // ── Tool 2: check_feasibility ─────────────────────────────────────────
    this.server.tool(
      "check_feasibility",
      "Check feasibility of a new satellite capture. Read-only exploration " +
      "— does NOT return a confirmation token. Use preview_order when ready to order.",
      {
        location: z.string().describe("Place name or WKT polygon"),
        product_type: z.string().describe("DAY, NIGHT, SAR, etc."),
        resolution: z.string().describe("Resolution level"),
        start_date: z.string().describe("Capture window start (ISO format)"),
        end_date: z.string().describe("Capture window end (ISO format)"),
        max_cloud_coverage_percent: z.number().optional(),
        priority_item: z.boolean().optional(),
        required_provider: z.string().optional(),
      },
      async (args) => ({
        content: [{
          type: "text" as const,
          text: await proxyToolCall(this.env, "check_feasibility", args, this.apiKey),
        }],
      }),
    );

    // ── Tool 3: get_pricing_overview ──────────────────────────────────────
    this.server.tool(
      "get_pricing_overview",
      "Get a broad pricing overview across all products and resolutions. " +
      "For exact pricing on a specific image, use preview_order instead.",
      {
        location: z.string().optional().describe("Optional place name or WKT for area-specific pricing"),
      },
      async (args) => ({
        content: [{
          type: "text" as const,
          text: await proxyToolCall(this.env, "get_pricing_overview", args, this.apiKey),
        }],
      }),
    );

    // ── Tool 4: preview_order ─────────────────────────────────────────────
    this.server.tool(
      "preview_order",
      "Add an image to cart / preview an order. When a user says 'order', 'buy', " +
      "'purchase', or 'add to cart', call this tool FIRST automatically — do NOT " +
      "ask the user whether to preview. This returns pricing details and a " +
      "confirmation_token. Present the pricing to the user and ask for confirmation " +
      "before calling confirm_order.",
      {
        order_type: z.enum(["ARCHIVE", "TASKING"]).describe("Order type"),
        location: z.string().describe("Place name or WKT polygon"),
        archive_id: z.string().optional().describe("Required for ARCHIVE orders"),
        window_start: z.string().optional().describe("Required for TASKING: capture start (ISO)"),
        window_end: z.string().optional().describe("Required for TASKING: capture end (ISO)"),
        product_type: z.string().optional().describe("Required for TASKING: DAY, NIGHT, SAR, etc."),
        resolution: z.string().optional().describe("Required for TASKING: resolution level"),
        max_cloud_coverage_percent: z.number().optional(),
        priority_item: z.boolean().optional(),
        required_provider: z.string().optional(),
      },
      async (args) => ({
        content: [{
          type: "text" as const,
          text: await proxyToolCall(this.env, "preview_order", args, this.apiKey),
        }],
      }),
    );

    // ── Tool 5: confirm_order (destructive) ───────────────────────────────
    this.server.tool(
      "confirm_order",
      "Confirm and place a satellite imagery order. CHARGES THE USER'S ACCOUNT. " +
      "ONLY call this after the user explicitly approves the pricing shown by " +
      "preview_order. Requires the confirmation_token returned by preview_order.",
      {
        confirmation_token: z.string().describe("Token from preview_order (required)"),
        order_type: z.enum(["ARCHIVE", "TASKING"]),
        location: z.string().describe("Place name or WKT polygon"),
        archive_id: z.string().optional(),
        window_start: z.string().optional(),
        window_end: z.string().optional(),
        product_type: z.string().optional(),
        resolution: z.string().optional(),
        priority_item: z.boolean().default(false),
        max_cloud_coverage_percent: z.number().default(20),
        max_off_nadir_angle: z.number().default(30),
        required_provider: z.string().optional(),
        sar_product_types: z.array(z.string()).optional(),
        sar_polarisation: z.string().optional(),
        sar_grazing_angle_min: z.number().optional(),
        sar_grazing_angle_max: z.number().optional(),
        sar_azimuth_angle_min: z.number().optional(),
        sar_azimuth_angle_max: z.number().optional(),
        sar_number_of_looks: z.number().optional(),
        provider_window_id: z.string().optional(),
        delivery_driver: z.enum(["NONE", "S3", "GS", "AZURE"]).default("NONE"),
        delivery_params: z.record(z.unknown()).optional(),
        label: z.string().default("MCP Order"),
        webhook_url: z.string().optional(),
        metadata: z.record(z.unknown()).optional(),
      },
      async (args) => ({
        content: [{
          type: "text" as const,
          text: await proxyToolCall(this.env, "confirm_order", args, this.apiKey),
        }],
      }),
    );

    // ── Tool 6: check_order_status ────────────────────────────────────────
    this.server.tool(
      "check_order_status",
      "Check a specific order's status, or list recent orders with pagination.",
      {
        order_id: z.string().optional().describe("Order UUID. Omit to list recent orders."),
        order_type: z.enum(["ARCHIVE", "TASKING"]).optional().describe("Filter by type (for listing)"),
        page_number: z.number().default(0),
        page_size: z.number().default(25),
        sort_by: z.string().default("created_at"),
        sort_direction: z.enum(["asc", "desc"]).default("desc"),
      },
      async (args) => ({
        content: [{
          type: "text" as const,
          text: await proxyToolCall(this.env, "check_order_status", args, this.apiKey),
        }],
      }),
    );

    // ── Tool 7: get_download_url ──────────────────────────────────────────
    this.server.tool(
      "get_download_url",
      "Get a time-limited download URL for an order's deliverable.",
      {
        order_id: z.string().describe("Order UUID"),
        deliverable_type: z.enum(["image", "payload", "cog"]).default("image"),
      },
      async (args) => ({
        content: [{
          type: "text" as const,
          text: await proxyToolCall(this.env, "get_download_url", args, this.apiKey),
        }],
      }),
    );

    // ── Tool 8: setup_area_monitoring ─────────────────────────────────────
    this.server.tool(
      "setup_area_monitoring",
      "Manage AOI monitoring. Actions: create (new monitor), list (active monitors), " +
      "history (trigger history), delete (remove monitor).",
      {
        action: z.enum(["create", "list", "history", "delete"]),
        location: z.string().optional().describe("Place name or WKT. Required for 'create'."),
        webhook_url: z.string().optional().describe("Webhook URL. Required for 'create'."),
        notification_id: z.string().optional().describe("Monitor ID. Required for 'history'/'delete'."),
        gsd_min: z.number().optional(),
        gsd_max: z.number().optional(),
        product_type: z.string().optional(),
        page_number: z.number().default(0),
        page_size: z.number().default(10),
      },
      async (args) => ({
        content: [{
          type: "text" as const,
          text: await proxyToolCall(this.env, "setup_area_monitoring", args, this.apiKey),
        }],
      }),
    );

    // ── Tool 9: check_new_images ──────────────────────────────────────────
    this.server.tool(
      "check_new_images",
      "Check for new satellite images from AOI monitoring webhooks.",
      {
        notification_id: z.string().optional().describe("Filter by monitor ID"),
        hours: z.number().default(24).describe("Look back hours"),
        mark_as_read: z.boolean().default(true),
      },
      async (args) => ({
        content: [{
          type: "text" as const,
          text: await proxyToolCall(this.env, "check_new_images", args, this.apiKey),
        }],
      }),
    );

    // ── Tool 10: geocode_location ─────────────────────────────────────────
    this.server.tool(
      "geocode_location",
      "Convert a place name to WKT coordinates via OpenStreetMap. " +
      "For imagery search, use search_satellite_imagery instead (it auto-geocodes).",
      {
        location_name: z.string().describe("Place name (e.g., 'Suez Canal')"),
        buffer_km: z.number().default(1.0).describe("Buffer around point locations (km)"),
      },
      async (args) => ({
        content: [{
          type: "text" as const,
          text: await proxyToolCall(this.env, "geocode_location", args, this.apiKey),
        }],
      }),
    );

    // ── Tool 11: search_nearby_pois ───────────────────────────────────────
    this.server.tool(
      "search_nearby_pois",
      "Find points of interest near a location using OpenStreetMap. " +
      "Useful for discovering imagery targets like airports, ports, military bases.",
      {
        lat: z.number().describe("Center latitude"),
        lon: z.number().describe("Center longitude"),
        feature_type: z.string().default("aeroway")
          .describe("OSM type: aeroway, amenity, building, military, power, etc."),
        radius_km: z.number().default(50).describe("Search radius in km"),
        limit: z.number().default(10).describe("Max results"),
      },
      async (args) => ({
        content: [{
          type: "text" as const,
          text: await proxyToolCall(this.env, "search_nearby_pois", args, this.apiKey),
        }],
      }),
    );

    // ── Tool 12: get_account_info ─────────────────────────────────────────
    this.server.tool(
      "get_account_info",
      "Get SkyFi account info including budget usage and payment status.",
      {},
      async (args) => ({
        content: [{
          type: "text" as const,
          text: await proxyToolCall(this.env, "get_account_info", args, this.apiKey),
        }],
      }),
    );
  }
}

// ── HTTP Handler: Routing ───────────────────────────────────────────────────

async function handleMcpRoutes(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);

  // Health check
  if (url.pathname === "/health") {
    return Response.json({
      status: "healthy",
      service: "skyfi-mcp-worker",
      backend: env.PYTHON_BACKEND_URL,
      tools: 12,
      auth: env.SKYFI_OAUTH_CLIENT_ID ? "oauth+bearer" : "bearer-only",
    });
  }

  // Landing page
  if (url.pathname === "/") {
    return Response.json({
      name: "SkyFi MCP Server",
      version: "0.1.0",
      description: "Satellite imagery via Model Context Protocol",
      architecture: "Cloudflare Worker (proxy) + Python backend",
      endpoints: {
        mcp: "/mcp  (MCP protocol — Streamable HTTP)",
        sse: "/sse  (MCP protocol — legacy SSE)",
        health: "/health  (GET — health check)",
        authorize: "/authorize  (OAuth 2.1 — for Claude Web)",
      },
      docs: "https://github.com/skyfi/skyfi-mcp-server",
    });
  }

  // OAuth callback (POST from API key form)
  if (url.pathname === "/oauth/callback" && request.method === "POST") {
    return new Response("OAuth not configured", { status: 501 });
  }

  // Streamable HTTP transport (modern)
  if (url.pathname === "/mcp") {
    return SkyFiMcpAgent.serve("/mcp").fetch(request, env);
  }

  // Legacy SSE transport (backward compatibility for older MCP clients)
  if (url.pathname === "/sse" || url.pathname.startsWith("/sse/")) {
    return SkyFiMcpAgent.serve("/sse").fetch(request, env);
  }

  return new Response("Not Found", { status: 404 });
}

// ── Main Entry Point ────────────────────────────────────────────────────────

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    // If OAuth secrets are configured, wrap with OAuthProvider
    if (env.SKYFI_OAUTH_CLIENT_ID && env.COOKIE_ENCRYPTION_KEY) {
      // Pre-register the OAuth client in KV before any request is processed.
      // The library's createClient() ignores our clientId, so we write directly.
      console.log("[OAuth] Client ID:", env.SKYFI_OAUTH_CLIENT_ID);
      console.log("[OAuth] Expected: skyfi-mcp-claude-web");
      console.log("[OAuth] Match:", env.SKYFI_OAUTH_CLIENT_ID === "skyfi-mcp-claude-web");

      await ensureClientRegistered(env);

      const mcpHandler = SkyFiMcpAgent.serve("/mcp");
      return new OAuthProvider({
        apiRoute: "/mcp",
        apiHandler: mcpHandler,
        authorizeEndpoint: "/authorize",
        tokenEndpoint: "/token",
        defaultHandler: {
          fetch: async (req: Request, handlerEnv: Env, handlerCtx: ExecutionContext) => {
            const url = new URL(req.url);
            const oauthHelpers = handlerEnv.OAUTH_PROVIDER!;

            // Custom authorize page (API key entry form)
            if (url.pathname === "/authorize") {
              return handleOAuthAuthorize(req, handlerEnv, oauthHelpers);
            }

            // OAuth callback (user submitted their API key)
            if (url.pathname === "/oauth/callback" && req.method === "POST") {
              return handleOAuthCallback(req, handlerEnv, oauthHelpers);
            }

            // All other routes (health, landing, SSE)
            return handleMcpRoutes(req, handlerEnv);
          },
        },
        // Access token TTL: 24 hours
        accessTokenTTL: 86400,
      }).fetch(request, env, ctx);
    }

    // No OAuth configured — direct Bearer token / API key mode
    return handleMcpRoutes(request, env);
  },
};
