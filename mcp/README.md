# Care-Beacon MCP Servers

This directory contains Model Context Protocol (MCP) server implementations for Care-Beacon.

## Directory Structure

```
mcp/
├── stdio/          # Local stdio-based MCP server
│   └── mcp_server.py
└── sse/            # Remote HTTP/SSE-based MCP server (coming soon)
```

## Server Types

### stdio/ - Local MCP Server (Current)

**Transport:** Standard I/O (stdin/stdout)
**Use Case:** Local Claude Desktop integration
**Status:** ✅ Active

The stdio-based server is spawned as a local subprocess by Claude Desktop and communicates via pipes. This is the simplest implementation and works well for local development.

**Advantages:**
- Simple setup (no authentication needed)
- Low latency (local IPC)
- No exposure to internet

**Limitations:**
- Requires local Python environment
- Only works on the local machine
- Cannot be shared across devices

**Configuration Example:**
```json
{
  "mcpServers": {
    "care-beacon": {
      "command": "/path/to/python",
      "args": ["/path/to/Care-Beacon/mcp/stdio/mcp_server.py"],
      "env": {
        "CARE_BEACON_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

### sse/ - Remote MCP Server (Coming Soon)

**Transport:** HTTP with Server-Sent Events (SSE)
**Use Case:** Remote hosting on render.com
**Status:** 🚧 Planned

The SSE-based server will run as a web service and support remote connections via HTTPS. This enables:

**Advantages:**
- No local setup required
- Works from any device
- Centralized updates
- Can be deployed to render.com

**Considerations:**
- Requires authentication (API keys)
- Internet latency vs local IPC
- Security (exposed endpoint)
- Additional hosting costs

**Configuration Example (Future):**
```json
{
  "mcpServers": {
    "care-beacon-remote": {
      "url": "https://care-beacon-mcp.onrender.com/sse",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY"
      }
    }
  }
}
```

## Tools Available

Both implementations provide the same tools:

1. **ask_medical_question** - Ask cancer-related medical questions
2. **get_system_stats** - Get usage statistics

## Environment Variables

- `CARE_BEACON_API_URL` - URL of the Care-Beacon API (default: http://localhost:8000)
- `CARE_BEACON_TIMEOUT` - Request timeout in seconds (default: 60.0)

## Development

To test the stdio server locally:
```bash
/opt/anaconda3/envs/care-beacon/bin/python mcp/stdio/mcp_server.py
```

For Claude Desktop integration, update your Claude Desktop config file at:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Update the path to point to the new location

## Future Plans

- [ ] Implement HTTP/SSE transport for remote hosting
- [ ] Add API key authentication
- [ ] Deploy SSE server to render.com
- [ ] Add monitoring and rate limiting
- [ ] Support for additional tools (resources, prompts)
