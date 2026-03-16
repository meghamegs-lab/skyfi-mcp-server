# Local Development Setup

This guide walks you through setting up the SkyFi MCP Server for local development, testing, and contributing.

## Prerequisites

**Required:**

- Python 3.11 or higher
- pip (comes with Python)
- A SkyFi API key (get one from [app.skyfi.com](https://app.skyfi.com) — requires Pro account)

**Optional (for Worker development):**

- Node.js 20+ and npm
- Wrangler CLI (`npm install -g wrangler`)

## Installation

Clone the repository and install in development mode:

```bash
git clone https://github.com/skyfi/skyfi-mcp-server.git
cd skyfi-mcp-server
pip install -e ".[dev]"
```

This installs the package in editable mode along with dev dependencies (pytest, ruff, respx, pytest-asyncio).

## Configuration

You need a SkyFi API key. There are two ways to configure it:

**Option 1: Environment variable (recommended for development)**

```bash
export SKYFI_API_KEY="sk-your-key-here"
```

**Option 2: Config file**

```bash
skyfi-mcp config --init       # Creates ~/.skyfi/config.json template
skyfi-mcp config --show        # Verify current configuration
```

Then edit `~/.skyfi/config.json`:

```json
{
  "api_key": "sk-your-key-here"
}
```

The resolution order is: environment variable > config file. If neither is set, the server will return an error when tools try to call the SkyFi API.

## Running the Server

### HTTP mode (default)

```bash
skyfi-mcp serve
```

This starts the server at `http://localhost:8000` with Streamable HTTP + SSE transport. You can connect any MCP client to `http://localhost:8000/mcp`.

**Custom port:**

```bash
skyfi-mcp serve --port 3000
```

**Verify it's running:**

```bash
# Health check
curl http://localhost:8000/health

# Landing page (shows available endpoints)
curl http://localhost:8000/
```

The `/mcp` endpoint only responds to MCP clients. Browsers will get a `406 Not Acceptable` error — this is expected behavior.

### stdio mode (for local MCP clients)

For Claude Desktop, Claude Code, or other clients that use stdio transport:

```bash
skyfi-mcp serve --transport stdio
```

**Claude Desktop configuration** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "skyfi": {
      "command": "skyfi-mcp",
      "args": ["serve", "--transport", "stdio"],
      "env": {
        "SKYFI_API_KEY": "sk-your-key-here"
      }
    }
  }
}
```

## Running Tests

```bash
# Run all tests (212 tests)
pytest -v

# Run specific test files
pytest tests/test_models.py -v
pytest tests/test_tokens.py -v
pytest tests/test_webhooks.py -v
pytest tests/test_server_helpers.py -v

# Run golden evals only
pytest tests/golden/ -v

# Run with coverage
pytest --cov=skyfi_mcp -v
```

Tests use `pytest-asyncio` with `asyncio_mode = "auto"`. No SkyFi API key is needed — tests mock all external calls.

## Linting

```bash
# Check for errors
ruff check src/ tests/

# Auto-fix what's possible
ruff check --fix src/ tests/

# Check formatting
ruff format --check src/ tests/

# Auto-format
ruff format src/ tests/
```

Ruff configuration is in `pyproject.toml`:

- Target: Python 3.11
- Line length: 100 characters
- Rules: E, F, I (isort), N, W, UP (pyupgrade)

## Worker Development (Optional)

If you're working on the Cloudflare Worker (TypeScript proxy):

```bash
cd worker
npm install

# Local dev server
npx wrangler dev

# The Worker proxies to your local Python backend at localhost:8000
```

Make sure the Python backend is running first. The Worker's `wrangler.toml` sets `PYTHON_BACKEND_URL = "http://localhost:8000"` for local development.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SKYFI_API_KEY` | Yes* | — | SkyFi Platform API key |
| `SKYFI_BASE_URL` | No | `https://app.skyfi.com/platform-api` | Override API base URL |
| `SKYFI_TOKEN_SECRET` | No | Built-in default | HMAC secret for confirmation tokens |
| `SKYFI_MCP_DATA_DIR` | No | `.` (current dir) | Directory for SQLite webhook DB |

*Required for actual SkyFi API calls. Not needed for running tests.

## Docker

Build and run locally with Docker:

```bash
docker build -t skyfi-mcp .
docker run -p 8000:8000 -e SKYFI_API_KEY="sk-..." skyfi-mcp
```

The Dockerfile uses `python:3.12-slim` and runs `skyfi-mcp serve --host 0.0.0.0 --port 8000`.

## Project Dependencies

**Runtime:**

- `fastmcp>=2.0.0` — Prefect's FastMCP library (NOT the official `mcp` SDK's built-in FastMCP)
- `mcp>=1.0.0` — MCP types and protocol definitions
- `httpx>=0.27.0` — Async HTTP client for SkyFi API
- `pydantic>=2.0.0` — Data validation (57 API models)
- `shapely>=2.0.0` — WKT geometry handling
- `geopy>=2.4.0` — Geocoding utilities
- `uvicorn>=0.30.0` — ASGI server
- `wsproto>=1.2.0` — WebSocket protocol (avoids websockets deprecation warnings)

**Dev:**

- `pytest>=8.0`, `pytest-asyncio>=0.24` — Testing
- `ruff>=0.8.0` — Linting and formatting
- `respx>=0.22.0` — HTTP mocking for tests

**Demo agents:**

- `langchain>=0.3.0`, `langgraph>=0.2.0` — Agent framework
- `langchain-openai>=0.2.0`, `langchain-anthropic>=0.3.0` — LLM integrations
- `langchain-mcp-adapters>=0.1.0` — MCP tool wrappers

Install demo deps with: `pip install -e ".[demo]"`

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests: `pytest -v`
5. Run linter: `ruff check src/ tests/`
6. Commit and push
7. Open a pull request against `main`

CI runs automatically on PRs — lint and tests must pass before merge.

## Troubleshooting

**"Connection refused" when starting the server**
Check if another process is using port 8000. Use `--port` to choose a different port.

**"API key not found" errors**
Make sure `SKYFI_API_KEY` is set in your environment or `~/.skyfi/config.json` exists.

**websockets deprecation warnings**
These are suppressed by using `wsproto` instead of `websockets`. If you see them, make sure `wsproto` is installed: `pip install wsproto`.

**Import errors after pulling new code**
Reinstall in dev mode: `pip install -e ".[dev]"`

**Tests fail with "No module named 'skyfi_mcp'"**
The package isn't installed. Run `pip install -e ".[dev]"` first.
