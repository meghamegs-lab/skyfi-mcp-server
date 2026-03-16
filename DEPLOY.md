# Production Deployment

This guide covers deploying the SkyFi MCP Server to production using the hybrid architecture: Python backend on Fly.io + Cloudflare Worker as the MCP front door.

## Architecture Overview

```
MCP Clients  →  Cloudflare Worker  →  Python Backend (Fly.io)  →  SkyFi API
                 (MCP protocol,        (business logic,
                  OAuth 2.1,            12 tools, geocoding,
                  Zod schemas)          HMAC tokens, webhooks)
```

For simpler deployments, you can skip the Worker and deploy the Python backend alone — it runs as a full MCP server on its own.

---

## Phase 1: Deploy the Python Backend to Fly.io

### 1.1 Install the Fly CLI

```bash
curl -L https://fly.io/install.sh | sh
fly auth login
```

### 1.2 Launch the App (first time only)

If you haven't created the app yet:

```bash
fly launch
```

This reads `fly.toml` and provisions the app. If the app already exists (`skyfi-mcp-server`), skip this step.

### 1.3 Create the Persistent Volume

The SQLite webhook event store needs a persistent volume:

```bash
fly volumes create skyfi_data --region iad --size 1
```

This matches the `[mounts]` section in `fly.toml`:

```toml
[[mounts]]
  source = 'skyfi_data'
  destination = '/data'
```

### 1.4 Set Secrets

```bash
# Required: your SkyFi API key
fly secrets set SKYFI_API_KEY="sk-your-key-here"

# Optional: custom HMAC secret (defaults to built-in if not set)
fly secrets set SKYFI_TOKEN_SECRET="your-random-secret"
```

Verify secrets are set:

```bash
fly secrets list
```

### 1.5 Deploy

```bash
fly deploy
```

This builds the Docker image remotely and deploys it. The Dockerfile uses `python:3.12-slim` and runs `skyfi-mcp serve --host 0.0.0.0 --port 8000`.

### 1.6 Verify

```bash
# Health check
curl https://skyfi-mcp-server.fly.dev/health

# Landing page
curl https://skyfi-mcp-server.fly.dev/
```

Your MCP endpoint is now live at `https://skyfi-mcp-server.fly.dev/mcp`.

### 1.7 View Logs

```bash
fly logs
fly logs --app skyfi-mcp-server
```

---

## Phase 2: Deploy the Cloudflare Worker

The Worker is optional but recommended for production. It adds OAuth 2.1 for Claude Web, Zod schema validation, and Durable Objects for session management.

### 2.1 Install Wrangler

```bash
cd worker
npm install
```

### 2.2 Create the KV Namespace

The Worker uses a KV namespace for OAuth state storage:

```bash
npx wrangler kv namespace create "OAUTH_KV"
```

Copy the returned namespace ID and update `wrangler.toml`:

```toml
[[kv_namespaces]]
binding = "OAUTH_KV"
id = "your-namespace-id-here"
```

### 2.3 Set Secrets

```bash
# Required: point to your Fly.io backend
npx wrangler secret put PYTHON_BACKEND_URL
# Enter: https://skyfi-mcp-server.fly.dev

# For OAuth 2.1 (Claude Web integration):
npx wrangler secret put SKYFI_OAUTH_CLIENT_ID
npx wrangler secret put SKYFI_OAUTH_CLIENT_SECRET
npx wrangler secret put COOKIE_ENCRYPTION_KEY
```

The `PYTHON_BACKEND_URL` is also set in `wrangler.toml` under `[env.production]`, but secrets take precedence.

### 2.4 Deploy

```bash
npx wrangler deploy --env production
```

### 2.5 Verify

```bash
curl https://skyfi-mcp-worker.<your-subdomain>.workers.dev/health
```

The Worker's MCP endpoint is at `/mcp`. Programmatic clients authenticate with:

```
Authorization: Bearer <skyfi-api-key>
```

or:

```
X-Skyfi-Api-Key: <skyfi-api-key>
```

---

## Phase 3: CI/CD Pipeline

The project includes a GitHub Actions workflow (`.github/workflows/ci.yml`) that automates lint, test, and deployment.

### Pipeline Structure

```
Push/PR to main:
  ├── lint   (ruff check + format check)
  └── test   (pytest)

Push to main only (after lint + test pass):
  ├── deploy-backend  (Fly.io)
  └── deploy-worker   (Cloudflare)
```

PRs only run lint and test. Deployment happens automatically when code is merged to `main`.

### Required GitHub Secrets

Go to your repo Settings > Secrets and variables > Actions, and add:

| Secret | How to get it |
|--------|---------------|
| `FLY_API_TOKEN` | Run `fly tokens create deploy -x 999999h` in your terminal |
| `CLOUDFLARE_API_TOKEN` | Cloudflare dashboard > My Profile > API Tokens > Create Token (use "Edit Cloudflare Workers" template) |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare dashboard > any domain > Overview > right sidebar under "API" |

### Testing the Pipeline

1. Create a feature branch and push changes
2. Open a PR to `main` — lint and test jobs run automatically
3. Merge the PR — deploy jobs trigger after tests pass
4. Check the Actions tab for deployment status

---

## Python-Only Deployment (No Worker)

If you don't need OAuth or the Cloudflare proxy, deploy the Python backend alone:

### Fly.io

```bash
fly secrets set SKYFI_API_KEY="sk-..."
fly deploy
```

Clients connect directly to `https://skyfi-mcp-server.fly.dev/mcp`.

### Docker (any cloud provider)

```bash
docker build -t skyfi-mcp .
docker run -p 8000:8000 \
  -e SKYFI_API_KEY="sk-..." \
  -e SKYFI_TOKEN_SECRET="your-secret" \
  -v skyfi-data:/data \
  skyfi-mcp
```

The `-v skyfi-data:/data` mount persists the SQLite webhook database across container restarts.

### AWS ECS Fargate

Use the provided `Dockerfile` with your ECS task definition. Set environment variables via task definition secrets. Map port 8000 and mount an EFS volume at `/data` for webhook persistence.

---

## Client Authentication

### Local mode (single user)

Set `SKYFI_API_KEY` as an environment variable or in `~/.skyfi/config.json`. All tool calls use this key.

### Cloud mode (multi-user)

Clients pass their own SkyFi API key in each request:

```
Authorization: Bearer <skyfi-api-key>
X-Skyfi-Api-Key: <skyfi-api-key>
```

Every tool also accepts an optional `api_key` parameter for programmatic use.

### OAuth 2.1 (Claude Web)

When the Worker is deployed with OAuth secrets, Claude Web users get a web form at `/authorize` where they enter their SkyFi API key. The Worker validates it, issues an OAuth token, and handles the authorization flow automatically.

---

## Environment Variables Reference

### Python Backend (Fly.io secrets)

| Variable | Required | Description |
|----------|----------|-------------|
| `SKYFI_API_KEY` | Yes (single-user) | Default SkyFi API key |
| `SKYFI_TOKEN_SECRET` | No | HMAC secret for confirmation tokens |
| `SKYFI_BASE_URL` | No | Override SkyFi API base URL |
| `SKYFI_MCP_DATA_DIR` | No | SQLite database directory (default: `/data` in Docker) |

### Cloudflare Worker (wrangler secrets)

| Variable | Required | Description |
|----------|----------|-------------|
| `PYTHON_BACKEND_URL` | Yes | Backend URL (e.g. `https://skyfi-mcp-server.fly.dev`) |
| `SKYFI_OAUTH_CLIENT_ID` | For OAuth | OAuth client ID for Claude Web |
| `SKYFI_OAUTH_CLIENT_SECRET` | For OAuth | OAuth client secret |
| `COOKIE_ENCRYPTION_KEY` | For OAuth | Session cookie encryption key |

### GitHub Actions Secrets

| Secret | Used by |
|--------|---------|
| `FLY_API_TOKEN` | deploy-backend job |
| `CLOUDFLARE_API_TOKEN` | deploy-worker job |
| `CLOUDFLARE_ACCOUNT_ID` | deploy-worker job |

---

## Monitoring and Troubleshooting

### Fly.io

```bash
# View live logs
fly logs

# Check app status
fly status

# SSH into the running machine
fly ssh console

# Check the SQLite database
fly ssh console -C "ls -la /data/"

# Scale up if needed
fly scale count 2
```

### Cloudflare Worker

```bash
# View recent logs
npx wrangler tail --env production

# Check deployment status
npx wrangler deployments list
```

### Common Issues

**Backend returns 502/503**
The Fly.io machine may have stopped (auto-stop is enabled). The first request after idle triggers a cold start — wait a few seconds and retry.

**Worker returns "Unknown tool" error**
The Worker's tool list must match the Python backend's 12 tools. Redeploy both if you've added or renamed tools.

**OAuth flow fails**
Check that all three OAuth secrets are set: `SKYFI_OAUTH_CLIENT_ID`, `SKYFI_OAUTH_CLIENT_SECRET`, `COOKIE_ENCRYPTION_KEY`. Also verify the KV namespace ID in `wrangler.toml` matches the one you created.

**Webhook events not persisting**
The SQLite database is stored at `/data/webhook_events.db`. Make sure the Fly.io volume is mounted correctly. Check with `fly volumes list`.

**Token validation fails after deploy**
If you changed `SKYFI_TOKEN_SECRET` between deploys, all existing tokens become invalid. Users will need to re-run `preview_order` to get a new token. This is expected.

---

## Phase 2 Roadmap

The following feature is planned but not yet implemented:

- **SSE Push Notifications (Req #11):** Currently, `check_new_images` uses a polling pattern against the local SQLite store. A future update will add server-sent events so agents receive new imagery notifications in real time without polling.
