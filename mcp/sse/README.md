# Care-Beacon MCP Server - HTTP/SSE Transport

Remote MCP server implementation using HTTP with Server-Sent Events (SSE) transport. This can be deployed to render.com or other hosting platforms.

## Features

- ✅ **Remote Access** - Connect from anywhere, not just localhost
- ✅ **Authentication** - API key-based security
- ✅ **FastAPI** - Production-ready HTTP server
- ✅ **SSE Transport** - Standard MCP protocol over HTTP
- ✅ **Health Checks** - Monitoring endpoints for deployment platforms
- ✅ **Same Tools** - Identical functionality to stdio version

## Quick Start

### 1. Local Testing

```bash
# Set environment variables
export CARE_BEACON_API_URL="http://localhost:8000"
export MCP_API_KEY="your-secret-key-here"  # Optional for local testing
export PORT=8001

# Start the server
python mcp/sse/mcp_server.py
```

The server will be available at:
- SSE endpoint: `http://localhost:8001/sse`
- Health check: `http://localhost:8001/health`
- API docs: `http://localhost:8001/docs`

### 2. Claude Desktop Configuration

Create or update `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "care-beacon-remote": {
      "url": "http://localhost:8001/sse",
      "headers": {
        "Authorization": "Bearer your-secret-key-here"
      }
    }
  }
}
```

For production (render.com):
```json
{
  "mcpServers": {
    "care-beacon-remote": {
      "url": "https://care-beacon-mcp.onrender.com/sse",
      "headers": {
        "Authorization": "Bearer your-production-api-key"
      }
    }
  }
}
```

### 3. Test the Connection

```bash
# Health check
curl http://localhost:8001/health

# Test with API key
curl -H "Authorization: Bearer your-secret-key-here" \
     http://localhost:8001/sse
```

## Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `CARE_BEACON_API_URL` | URL of the Care-Beacon API | `http://localhost:8000` | Yes |
| `MCP_API_KEY` | API key for authentication | (empty) | Production only |
| `PORT` | Server port | `8001` | No |
| `CARE_BEACON_TIMEOUT` | API request timeout (seconds) | `60.0` | No |

## Authentication

### Development Mode
If `MCP_API_KEY` is not set, the server runs in **development mode** with no authentication required.

### Production Mode
When `MCP_API_KEY` is set, clients must provide the key in the `Authorization` header:
```
Authorization: Bearer your-secret-key-here
```

## Deployment to Render.com

### Step 1: Add to render.yaml

The MCP server is configured in `render.yaml`:

```yaml
- type: web
  name: care-beacon-mcp
  runtime: python
  plan: starter
  buildCommand: pip install -r requirements.txt
  startCommand: python mcp/sse/mcp_server.py
  envVars:
    - key: CARE_BEACON_API_URL
      value: https://care-beacon-api.onrender.com
    - key: MCP_API_KEY
      generateValue: true  # Auto-generate secure key
    - key: PORT
      value: 10000
```

### Step 2: Deploy

```bash
git push origin main
```

Render will automatically deploy the MCP server alongside the main API.

### Step 3: Get the API Key

1. Go to Render Dashboard
2. Find the `care-beacon-mcp` service
3. Go to "Environment" tab
4. Copy the auto-generated `MCP_API_KEY`

### Step 4: Update Claude Desktop Config

```json
{
  "mcpServers": {
    "care-beacon": {
      "url": "https://care-beacon-mcp.onrender.com/sse",
      "headers": {
        "Authorization": "Bearer <paste-your-api-key-here>"
      }
    }
  }
}
```

## Available Tools

### 1. ask_medical_question

Ask cancer-related medical questions with citations.

**Parameters:**
- `question` (required): The medical question (3-500 characters)
- `source` (optional): Filter by "BC Cancer" or "Canadian Cancer Society"
- `min_similarity` (optional): Minimum similarity score 0.0-1.0 (default: 0.5)

**Example:**
```
Question: "What are the symptoms of prostate cancer?"
```

### 2. get_system_stats

Get system usage statistics including costs, cache performance, and token usage.

**Parameters:** None

## Endpoints

### GET /
Server information and available endpoints.

### GET /health
Health check endpoint. Returns:
```json
{
  "status": "healthy",
  "mcp_server": "running",
  "backend_api": "connected",
  "api_url": "https://care-beacon-api.onrender.com"
}
```

### GET /sse
SSE endpoint for MCP protocol communication.

Requires `Authorization: Bearer <api-key>` header in production.

### GET /docs
Interactive API documentation (FastAPI).

## Monitoring

The `/health` endpoint can be used for:
- Render.com health checks
- Uptime monitoring (UptimeRobot, etc.)
- Load balancer health checks

## Security Considerations

1. **API Key Storage**: Never commit API keys to git
2. **HTTPS Only**: Use HTTPS in production (render.com provides this)
3. **Key Rotation**: Rotate API keys periodically
4. **Rate Limiting**: Consider adding rate limiting for production

## Troubleshooting

### Server won't start
- Check that all environment variables are set
- Verify the main API is accessible
- Check port is not already in use

### Authentication failing
- Verify API key matches exactly (no extra spaces)
- Check `Authorization: Bearer` format is correct
- Ensure MCP_API_KEY is set on the server

### Connection timeout
- Increase `CARE_BEACON_TIMEOUT`
- Check network connectivity to backend API
- Verify API is not rate limiting

### Tools not appearing in Claude Desktop
- Restart Claude Desktop after config changes
- Check SSE endpoint is accessible
- Verify JSON config syntax is correct

## Comparison with stdio Version

| Feature | stdio | SSE |
|---------|-------|-----|
| Transport | stdin/stdout | HTTP/SSE |
| Location | Local only | Remote capable |
| Setup | Python env required | No local setup |
| Security | OS-level | API key |
| Latency | Very low | Network dependent |
| Deployment | N/A | render.com, etc. |
| Best for | Local dev | Production, sharing |

## Development

### Running locally with hot reload

```bash
# Install uvicorn with reload
pip install uvicorn[standard]

# Run with auto-reload
uvicorn mcp.sse.mcp_server:app --reload --port 8001
```

### Testing with curl

```bash
# Health check
curl http://localhost:8001/health

# Test authentication
curl -H "Authorization: Bearer test-key" \
     http://localhost:8001/sse
```

## Support

For issues or questions:
- Check server logs in Render Dashboard
- Verify health check endpoint
- Test main API independently
- Review Claude Desktop logs
