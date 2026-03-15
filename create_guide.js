const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, HeadingLevel, BorderStyle,
  WidthType, ShadingType, PageNumber, PageBreak, TabStopType, TabStopPosition
} = require("docx");

const LETTER_W = 12240;
const LETTER_H = 15840;
const MARGIN = 1440;
const CONTENT_W = LETTER_W - 2 * MARGIN; // 9360

const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };
const cellPad = { top: 60, bottom: 60, left: 120, right: 120 };

function heading1(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 360, after: 200 }, children: [new TextRun({ text, bold: true, size: 32, font: "Arial" })] });
}
function heading2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 280, after: 160 }, children: [new TextRun({ text, bold: true, size: 28, font: "Arial" })] });
}
function heading3(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_3, spacing: { before: 200, after: 120 }, children: [new TextRun({ text, bold: true, size: 24, font: "Arial" })] });
}
function para(text, opts = {}) {
  return new Paragraph({ spacing: { after: 120 }, ...opts, children: [new TextRun({ text, size: 22, font: "Arial", ...opts.run })] });
}
function bold(text) {
  return new TextRun({ text, bold: true, size: 22, font: "Arial" });
}
function normal(text) {
  return new TextRun({ text, size: 22, font: "Arial" });
}
function code(text) {
  return new TextRun({ text, size: 20, font: "Courier New", color: "1A1A1A" });
}
function codePara(text) {
  return new Paragraph({
    spacing: { after: 40 },
    indent: { left: 360 },
    children: [new TextRun({ text, size: 20, font: "Courier New", color: "1A1A1A" })]
  });
}
function codeBlock(lines) {
  return lines.map(l => codePara(l));
}
function bullet(children, ref = "bullets", level = 0) {
  return new Paragraph({
    numbering: { reference: ref, level },
    spacing: { after: 80 },
    children: Array.isArray(children) ? children : [normal(children)]
  });
}
function numberedItem(children, ref = "steps", level = 0) {
  return new Paragraph({
    numbering: { reference: ref, level },
    spacing: { after: 100 },
    children: Array.isArray(children) ? children : [normal(children)]
  });
}
function stepItem(children) {
  return numberedItem(children, "steps", 0);
}

function headerCell(text, width) {
  return new TableCell({
    borders, width: { size: width, type: WidthType.DXA },
    shading: { fill: "2563EB", type: ShadingType.CLEAR },
    margins: cellPad,
    children: [new Paragraph({ children: [new TextRun({ text, bold: true, size: 20, font: "Arial", color: "FFFFFF" })] })]
  });
}
function cell(text, width) {
  return new TableCell({
    borders, width: { size: width, type: WidthType.DXA },
    margins: cellPad,
    children: [new Paragraph({ children: [new TextRun({ text, size: 20, font: "Arial" })] })]
  });
}
function codeCell(text, width) {
  return new TableCell({
    borders, width: { size: width, type: WidthType.DXA },
    shading: { fill: "F5F5F5", type: ShadingType.CLEAR },
    margins: cellPad,
    children: [new Paragraph({ children: [new TextRun({ text, size: 18, font: "Courier New" })] })]
  });
}

// ── Build Document ──

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial", color: "1A1A1A" },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: "2563EB" },
        paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: "333333" },
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 2 } },
    ]
  },
  numbering: {
    config: [
      { reference: "bullets", levels: [
        { level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
        { level: 1, format: LevelFormat.BULLET, text: "\u25E6", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 1440, hanging: 360 } } } },
      ]},
      { reference: "steps", levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
      ]},
      { reference: "steps2", levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
      ]},
      { reference: "steps3", levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
      ]},
      { reference: "steps4", levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
      ]},
      { reference: "steps5", levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
      ]},
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: LETTER_W, height: LETTER_H },
        margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN }
      }
    },
    headers: {
      default: new Header({ children: [
        new Paragraph({
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "2563EB", space: 1 } },
          children: [
            new TextRun({ text: "SkyFi MCP Server", bold: true, size: 18, font: "Arial", color: "2563EB" }),
            new TextRun({ text: "\tTesting & Deployment Guide", size: 18, font: "Arial", color: "666666" }),
          ],
          tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
        })
      ]})
    },
    footers: {
      default: new Footer({ children: [
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ text: "Page ", size: 18, font: "Arial", color: "999999" }),
            new TextRun({ children: [PageNumber.CURRENT], size: 18, font: "Arial", color: "999999" }),
          ]
        })
      ]})
    },
    children: [
      // ── TITLE ──
      new Paragraph({ spacing: { after: 80 }, children: [
        new TextRun({ text: "SkyFi MCP Server", size: 48, bold: true, font: "Arial", color: "1A1A1A" })
      ]}),
      new Paragraph({ spacing: { after: 40 }, children: [
        new TextRun({ text: "Testing & Deployment Guide", size: 32, font: "Arial", color: "2563EB" })
      ]}),
      new Paragraph({ spacing: { after: 400 }, children: [
        new TextRun({ text: "March 2026  |  Hybrid Architecture: Cloudflare Worker + Python Backend", size: 20, font: "Arial", color: "888888" })
      ]}),

      // ── ARCHITECTURE OVERVIEW ──
      heading1("Architecture Overview"),
      new Paragraph({ spacing: { after: 120 }, children: [
        normal("The SkyFi MCP Server uses a "), bold("two-tier hybrid architecture"), normal(":"),
      ]}),
      bullet([bold("Cloudflare Worker"), normal(" (TypeScript) \u2014 Thin MCP proxy, OAuth 2.1, Zod schema validation, Durable Objects for sessions")]),
      bullet([bold("Python Backend"), normal(" (FastMCP + uvicorn on Fly.io) \u2014 All business logic, 12 MCP tools, SkyFi API client, geocoding, HMAC tokens")]),
      para("The Worker proxies tool calls via POST /tool/<name> to the Python backend. For local development, you only need the Python backend \u2014 it runs as a full standalone MCP server."),

      // ── PREREQUISITES ──
      heading1("Prerequisites"),
      new Table({
        width: { size: CONTENT_W, type: WidthType.DXA },
        columnWidths: [2800, 3280, 3280],
        rows: [
          new TableRow({ children: [headerCell("Component", 2800), headerCell("Requirement", 3280), headerCell("Install", 3280)] }),
          new TableRow({ children: [cell("Python Backend", 2800), cell("Python 3.11+", 3280), codeCell("python3 --version", 3280)] }),
          new TableRow({ children: [cell("Python Backend", 2800), cell("pip (package manager)", 3280), codeCell("pip --version", 3280)] }),
          new TableRow({ children: [cell("CF Worker", 2800), cell("Node.js 18+", 3280), codeCell("node --version", 3280)] }),
          new TableRow({ children: [cell("CF Worker", 2800), cell("Wrangler CLI", 3280), codeCell("npm install -g wrangler", 3280)] }),
          new TableRow({ children: [cell("Deployment", 2800), cell("Fly.io CLI", 3280), codeCell("curl -L https://fly.io/install.sh | sh", 3280)] }),
          new TableRow({ children: [cell("Deployment", 2800), cell("Cloudflare account", 3280), cell("https://dash.cloudflare.com", 3280)] }),
          new TableRow({ children: [cell("Both", 2800), cell("SkyFi API key", 3280), cell("https://app.skyfi.com/settings/api", 3280)] }),
        ]
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // ══════════════════════════════════════════════════════════════════════
      // PART 1: LOCAL TESTING
      // ══════════════════════════════════════════════════════════════════════
      heading1("Part 1: Local Testing"),
      para("Local testing uses the Python backend only. It runs as a complete MCP server with all 12 tools, no Worker needed."),

      heading2("Step 1: Clone & Install"),
      ...codeBlock([
        "git clone https://github.com/skyfi/skyfi-mcp-server.git",
        "cd skyfi-mcp-server",
        "pip install -e \".[dev]\"",
      ]),

      heading2("Step 2: Configure Your API Key"),
      para("Choose one of these methods (checked in this order):"),
      numberedItem([bold("Environment variable"), normal(" (recommended for local dev):")], "steps2"),
      ...codeBlock(["export SKYFI_API_KEY=\"sk-your-key-here\""]),
      numberedItem([bold("Config file"), normal(":")], "steps2"),
      ...codeBlock([
        "skyfi-mcp config --init",
        "# Edit ~/.skyfi/config.json and replace YOUR_SKYFI_API_KEY_HERE",
      ]),
      numberedItem([bold("Verify"), normal(" your config is loaded:")], "steps2"),
      ...codeBlock(["skyfi-mcp config --show"]),

      heading2("Step 3: Run the Tests"),
      ...codeBlock([
        "# Run all unit tests",
        "pytest",
        "",
        "# Run with verbose output",
        "pytest -v",
        "",
        "# Run specific test files",
        "pytest tests/test_tokens.py     # HMAC token tests",
        "pytest tests/test_webhooks.py   # SQLite webhook store",
        "pytest tests/test_models.py     # Pydantic model validation",
        "pytest tests/test_server_helpers.py  # Tool helpers & annotations",
      ]),
      para("All tests should pass. If you see import errors, confirm pip install succeeded."),

      heading2("Step 4: Run the Lint"),
      ...codeBlock(["ruff check src/ tests/"]),
      para("Fix any issues before proceeding."),

      heading2("Step 5: Start the Server Locally"),
      ...codeBlock([
        "# Streamable HTTP on port 8000 (default)",
        "skyfi-mcp serve",
        "",
        "# Custom port",
        "skyfi-mcp serve --port 3000",
        "",
        "# stdio transport (for local MCP clients like Claude Desktop)",
        "skyfi-mcp serve --transport stdio",
      ]),
      para("You should see output like:"),
      ...codeBlock([
        "Starting SkyFi MCP Server",
        "  Transport: streamable-http",
        "  Host: 0.0.0.0:8000",
        "  MCP endpoint:     http://0.0.0.0:8000/mcp",
        "  Health check:     http://0.0.0.0:8000/health",
        "  Webhook receiver: http://0.0.0.0:8000/webhook",
        "  Landing page:     http://0.0.0.0:8000/",
      ]),

      heading2("Step 6: Verify Endpoints"),
      ...codeBlock([
        "# Health check",
        "curl http://localhost:8000/health",
        "# Expected: {\"status\":\"healthy\",\"service\":\"skyfi-mcp\",\"tools\":12}",
        "",
        "# Landing page",
        "curl http://localhost:8000/",
        "",
        "# Test a tool directly via /tool/<name> proxy",
        "curl -X POST http://localhost:8000/tool/geocode_location \\",
        "  -H \"Content-Type: application/json\" \\",
        "  -d '{\"location_name\": \"Golden Gate Bridge\"}'",
      ]),

      heading2("Step 7: Test with the Simple Agent"),
      ...codeBlock([
        "python examples/simple_agent.py \"Golden Gate Bridge\"",
        "python examples/simple_agent.py \"Port of Singapore\"",
        "python examples/simple_agent.py --mcp-url http://localhost:8000/mcp \"LAX Airport\"",
      ]),
      para("This runs the search \u2192 preview \u2192 confirm flow. It will ask for confirmation before placing any order."),

      heading2("Step 8: Test with an MCP Client"),
      para("Connect any MCP-compatible client to the server:"),
      bullet([bold("Claude Desktop"), normal(": Add to claude_desktop_config.json:")]),
      ...codeBlock([
        "{",
        "  \"mcpServers\": {",
        "    \"skyfi\": {",
        "      \"command\": \"skyfi-mcp\",",
        "      \"args\": [\"serve\", \"--transport\", \"stdio\"]",
        "    }",
        "  }",
        "}",
      ]),
      bullet([bold("Any HTTP MCP client"), normal(": Connect to http://localhost:8000/mcp")]),
      bullet([bold("LangChain demo agent"), normal(":")]),
      ...codeBlock([
        "pip install -e \".[demo]\"",
        "export OPENAI_API_KEY=\"sk-...\"  # or ANTHROPIC_API_KEY",
        "python examples/demo_agent.py",
      ]),

      new Paragraph({ children: [new PageBreak()] }),

      heading2("Step 9: Test the Worker Locally (Optional)"),
      para("If you want to test the full hybrid stack with the Cloudflare Worker proxying to the Python backend:"),
      numberedItem("Start the Python backend in one terminal:", "steps3"),
      ...codeBlock(["skyfi-mcp serve --port 8000"]),
      numberedItem("In a second terminal, start the Worker:", "steps3"),
      ...codeBlock([
        "cd worker",
        "npm install",
        "npx wrangler dev",
      ]),
      numberedItem("The Worker runs on port 8787 by default. Test it:", "steps3"),
      ...codeBlock([
        "curl http://localhost:8787/health",
        "# Should show {\"status\":\"healthy\",\"service\":\"skyfi-mcp-worker\",...}",
      ]),
      para("The Worker proxies tool calls to localhost:8000 (set in wrangler.toml). OAuth is not active locally unless you configure the secrets."),

      // ══════════════════════════════════════════════════════════════════════
      // PART 2: PRODUCTION DEPLOYMENT
      // ══════════════════════════════════════════════════════════════════════

      new Paragraph({ children: [new PageBreak()] }),

      heading1("Part 2: Production Deployment"),
      para("Production uses the full hybrid stack: Cloudflare Worker (edge, global) \u2192 Python backend (Fly.io, single region)."),

      heading2("Phase A: Deploy the Python Backend to Fly.io"),

      numberedItem([bold("Log in"), normal(" to Fly.io:")], "steps4"),
      ...codeBlock(["fly auth login"]),

      numberedItem([bold("Launch"), normal(" the app (first time only):")], "steps4"),
      ...codeBlock([
        "fly launch",
        "# Accept the defaults, or customize the app name",
        "# This creates the app and a persistent volume for SQLite",
      ]),

      numberedItem([bold("Create"), normal(" the persistent volume for SQLite (if not auto-created):")], "steps4"),
      ...codeBlock(["fly volumes create skyfi_data --size 1 --region iad"]),

      numberedItem([bold("Set"), normal(" your SkyFi API key as a secret:")], "steps4"),
      ...codeBlock(["fly secrets set SKYFI_API_KEY=\"sk-your-production-key\""]),

      numberedItem([bold("Deploy"), normal(":")], "steps4"),
      ...codeBlock(["fly deploy"]),

      numberedItem([bold("Verify"), normal(" the backend is running:")], "steps4"),
      ...codeBlock([
        "curl https://skyfi-mcp-server.fly.dev/health",
        "# Expected: {\"status\":\"healthy\",\"service\":\"skyfi-mcp\",\"tools\":12}",
        "",
        "# Test a tool",
        "curl -X POST https://skyfi-mcp-server.fly.dev/tool/geocode_location \\",
        "  -H \"Content-Type: application/json\" \\",
        "  -d '{\"location_name\": \"Tokyo Tower\"}'",
      ]),
      para("At this point, the Python backend is live and can be used directly by any MCP client via https://skyfi-mcp-server.fly.dev/mcp. The Worker adds OAuth + edge caching on top."),

      heading2("Phase B: Deploy the Cloudflare Worker"),

      numberedItem([bold("Navigate"), normal(" to the worker directory:")], "steps5"),
      ...codeBlock(["cd worker"]),

      numberedItem([bold("Install"), normal(" dependencies:")], "steps5"),
      ...codeBlock(["npm install"]),

      numberedItem([bold("Create"), normal(" the KV namespace for OAuth state:")], "steps5"),
      ...codeBlock([
        "npx wrangler kv namespace create OAUTH_KV",
        "# Copy the output ID and update wrangler.toml:",
        "#   id = \"<the-id-from-output>\"",
      ]),

      numberedItem([bold("Update"), normal(" wrangler.toml with your Python backend URL:")], "steps5"),
      ...codeBlock([
        "# In [env.production]",
        "vars = { PYTHON_BACKEND_URL = \"https://skyfi-mcp-server.fly.dev\" }",
      ]),

      numberedItem([bold("Set"), normal(" OAuth secrets (for Claude Web integration):")], "steps5"),
      ...codeBlock([
        "# Generate secure values",
        "npx wrangler secret put SKYFI_OAUTH_CLIENT_ID",
        "npx wrangler secret put SKYFI_OAUTH_CLIENT_SECRET",
        "npx wrangler secret put COOKIE_ENCRYPTION_KEY",
      ]),
      para("These are only needed if you want Claude Web OAuth. Without them, the Worker still works with Bearer token / API key auth."),

      numberedItem([bold("Deploy"), normal(" the Worker:")], "steps5"),
      ...codeBlock(["npx wrangler deploy"]),

      numberedItem([bold("Verify"), normal(" the Worker is live:")], "steps5"),
      ...codeBlock([
        "curl https://skyfi-mcp-worker.<your-subdomain>.workers.dev/health",
        "# Expected: {\"status\":\"healthy\",\"service\":\"skyfi-mcp-worker\",...}",
      ]),

      new Paragraph({ children: [new PageBreak()] }),

      heading2("Phase C: Connect MCP Clients to Production"),

      heading3("Programmatic clients (Bearer token)"),
      para("Any MCP client can connect using an API key in the Authorization header:"),
      ...codeBlock([
        "# MCP endpoint (Streamable HTTP)",
        "https://skyfi-mcp-worker.<subdomain>.workers.dev/mcp",
        "",
        "# Legacy SSE endpoint",
        "https://skyfi-mcp-worker.<subdomain>.workers.dev/sse",
        "",
        "# Auth header:",
        "Authorization: Bearer sk-your-skyfi-api-key",
        "# or",
        "X-Skyfi-Api-Key: sk-your-skyfi-api-key",
      ]),

      heading3("Claude Web (OAuth)"),
      para("If OAuth secrets are configured, Claude Web users are redirected to /authorize where they enter their SkyFi API key via a web form. The Worker handles the full OAuth 2.1 flow automatically."),

      heading3("Direct Python backend access"),
      para("Clients can also bypass the Worker entirely and connect directly to Fly.io:"),
      ...codeBlock([
        "# MCP endpoint",
        "https://skyfi-mcp-server.fly.dev/mcp",
        "",
        "# Tool proxy (for custom integrations)",
        "https://skyfi-mcp-server.fly.dev/tool/<tool_name>",
      ]),

      // ── TROUBLESHOOTING ──
      heading1("Troubleshooting"),

      new Table({
        width: { size: CONTENT_W, type: WidthType.DXA },
        columnWidths: [3120, 3120, 3120],
        rows: [
          new TableRow({ children: [headerCell("Symptom", 3120), headerCell("Cause", 3120), headerCell("Fix", 3120)] }),
          new TableRow({ children: [cell("406 Not Acceptable on /mcp", 3120), cell("Browser hit the MCP endpoint", 3120), cell("Use an MCP client, not a browser. /mcp requires Accept: text/event-stream", 3120)] }),
          new TableRow({ children: [cell("\"No SkyFi API key found\"", 3120), cell("Key not configured", 3120), cell("Set SKYFI_API_KEY env var or run skyfi-mcp config --init", 3120)] }),
          new TableRow({ children: [cell("Worker returns 502", 3120), cell("Python backend unreachable", 3120), cell("Check PYTHON_BACKEND_URL in wrangler.toml matches your Fly.io URL", 3120)] }),
          new TableRow({ children: [cell("Token expired error on confirm_order", 3120), cell("Too much time between preview and confirm", 3120), cell("Archive tokens: 5 min. Tasking tokens: 24 hr. Call preview_order again.", 3120)] }),
          new TableRow({ children: [cell("Feasibility returns \"pending\"", 3120), cell("SkyFi API still processing", 3120), cell("Auto-poll runs 30s. If still pending, wait and call check_feasibility again.", 3120)] }),
          new TableRow({ children: [cell("OAuth callback error", 3120), cell("Auth session expired", 3120), cell("KV TTL is 10 min. Start the OAuth flow again.", 3120)] }),
          new TableRow({ children: [cell("Import errors on pip install", 3120), cell("Python < 3.11", 3120), cell("Upgrade to Python 3.11+ (uses X | Y union syntax)", 3120)] }),
        ]
      }),

      // ── QUICK REFERENCE ──
      heading1("Quick Reference: Key URLs"),
      new Table({
        width: { size: CONTENT_W, type: WidthType.DXA },
        columnWidths: [2400, 6960],
        rows: [
          new TableRow({ children: [headerCell("What", 2400), headerCell("URL", 6960)] }),
          new TableRow({ children: [cell("Local MCP", 2400), codeCell("http://localhost:8000/mcp", 6960)] }),
          new TableRow({ children: [cell("Local health", 2400), codeCell("http://localhost:8000/health", 6960)] }),
          new TableRow({ children: [cell("Local tool proxy", 2400), codeCell("http://localhost:8000/tool/<name>", 6960)] }),
          new TableRow({ children: [cell("Local Worker", 2400), codeCell("http://localhost:8787/mcp", 6960)] }),
          new TableRow({ children: [cell("Prod backend", 2400), codeCell("https://skyfi-mcp-server.fly.dev/mcp", 6960)] }),
          new TableRow({ children: [cell("Prod Worker", 2400), codeCell("https://skyfi-mcp-worker.<sub>.workers.dev/mcp", 6960)] }),
          new TableRow({ children: [cell("SkyFi API keys", 2400), codeCell("https://app.skyfi.com/settings/api", 6960)] }),
        ]
      }),
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("/sessions/gifted-pensive-ptolemy/mnt/skyfi-mcp-server/SkyFi_MCP_Testing_Deployment_Guide.docx", buffer);
  console.log("Guide created successfully");
});
