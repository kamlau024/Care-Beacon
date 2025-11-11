# Care-Beacon MCP Server

This MCP (Model Context Protocol) server allows you to use the Care-Beacon Medical RAG system as a tool in Claude Desktop and other MCP clients.

## What is MCP?

The Model Context Protocol (MCP) is an open protocol that allows AI assistants like Claude to connect to external data sources and tools. By installing the Care-Beacon MCP server, you can ask Claude medical questions and it will automatically use your Care-Beacon RAG system to provide evidence-based answers with citations.

## Features

The MCP server exposes two tools:

1. **ask_medical_question**: Ask cancer-related medical questions and get evidence-based answers from BC Cancer and Canadian Cancer Society resources
   - Supports filtering by source (BC Cancer or Canadian Cancer Society)
   - Supports filtering by cancer type
   - Configurable similarity threshold for source relevance
   - Returns answers with citations, similarity scores, and metadata

2. **get_system_stats**: Get usage statistics including LLM costs, cache performance, and token usage

## Installation

### 1. Install Required Dependencies

The MCP server requires the `mcp` package:

```bash
pip install mcp httpx
```

Or if you're using the conda environment:

```bash
conda run -n care-beacon pip install mcp httpx
```

### 2. Configure Claude Desktop

Edit your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Add the Care-Beacon MCP server to the `mcpServers` section:

```json
{
  "mcpServers": {
    "care-beacon": {
      "command": "/opt/anaconda3/envs/care-beacon/bin/python",
      "args": [
        "/Users/username/Projects/Care-Beacon/mcp_server.py"
      ],
      "env": {
        "CARE_BEACON_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

**Important**: Update the paths to match your system:
- Replace `/opt/anaconda3/envs/care-beacon/bin/python` with your Python path
- Replace `/Users/username/Projects/Care-Beacon/mcp_server.py` with the actual path to the MCP server

To find your Python path:
```bash
conda activate care-beacon
which python
```

### 3. Start the Care-Beacon API

The MCP server connects to your Care-Beacon API, so make sure it's running:

```bash
cd /Users/username/Projects/Care-Beacon
conda activate care-beacon
python scripts/start_api.py
```

The API should be running at `http://localhost:8000` (default).

### 4. Restart Claude Desktop

After updating the configuration, completely quit and restart Claude Desktop.

## Usage

Once configured, you can ask Claude medical questions naturally, and it will automatically use the Care-Beacon MCP server when appropriate.

### Example Conversations

**Simple Question:**
```
You: What are the symptoms of breast cancer?

Claude: Let me check the Care-Beacon medical database for you.
[Uses ask_medical_question tool]

The main symptoms of breast cancer include:
- Lumps in the breast or underarm
- Changes in breast shape or size
- Skin changes or dimpling
...

Sources:
1. BC Cancer - Breast Cancer - Symptoms (95% similarity)
   URL: https://www.bccancer.bc.ca/...
```

**Filtered by Source:**
```
You: What are the treatment options for lung cancer? Only use Canadian Cancer Society sources.

Claude: I'll search the Canadian Cancer Society resources specifically.
[Uses ask_medical_question with source filter]
```

**With Similarity Control:**
```
You: Tell me about prostate cancer screening, but only use highly relevant sources (70% similarity or higher).

Claude: I'll search with a higher similarity threshold to get the most relevant information.
[Uses ask_medical_question with min_similarity=0.7]
```

**Check System Stats:**
```
You: Can you show me the Care-Beacon system statistics?

Claude: [Uses get_system_stats tool]

Here are the current statistics:
- Total Cost: $0.0245
- Cost Saved: $0.0180 (42.4% reduction)
- Cache Hit Rate: 65.2%
...
```

## Configuration Options

### Environment Variables

You can configure the MCP server using environment variables in the Claude Desktop config:

- **CARE_BEACON_API_URL**: URL of the Care-Beacon API (default: `http://localhost:8000`)
- **CARE_BEACON_TIMEOUT**: API request timeout in seconds (default: `60.0`)

### Example with Production API

If you want to use the production API on Render.com instead of localhost:

```json
{
  "mcpServers": {
    "care-beacon": {
      "command": "/opt/anaconda3/envs/care-beacon/bin/python",
      "args": [
        "/Users/kamlau/Projects/Care-Beacon/mcp_server.py"
      ],
      "env": {
        "CARE_BEACON_API_URL": "https://care-beacon-api.onrender.com",
        "CARE_BEACON_TIMEOUT": "120.0"
      }
    }
  }
}
```

Note: Using the production API will consume actual API quota and incur costs.

## Troubleshooting

### Claude Desktop doesn't show the tool

1. Make sure the configuration file path is correct
2. Check that all paths in the config are absolute paths (not relative)
3. Completely quit Claude Desktop (not just close the window) and restart
4. Check Claude Desktop logs for errors:
   - **macOS**: `~/Library/Logs/Claude/`
   - **Windows**: `%APPDATA%\Claude\logs\`

### Connection errors

If you see "Could not connect to Care-Beacon API" errors:

1. Make sure the Care-Beacon API is running:
   ```bash
   curl http://localhost:8000/health
   ```

2. Check the API URL in your Claude Desktop config matches where the API is running

3. If using production, make sure the URL is correct and the service is deployed

### Python/conda environment issues

Make sure you're using the correct Python interpreter with all dependencies installed:

```bash
# Activate environment
conda activate care-beacon

# Install MCP dependencies
pip install mcp httpx

# Verify installation
python -c "import mcp; print('MCP installed successfully')"

# Get Python path for config
which python
```

## Testing the MCP Server

You can test the MCP server directly before configuring it in Claude Desktop:

```bash
# Activate environment
conda activate care-beacon

# Make sure API is running
python scripts/start_api.py &

# Test the MCP server (it will wait for input via stdin)
python mcp_server.py

# Or use the MCP inspector tool (if installed)
npx @modelcontextprotocol/inspector python mcp_server.py
```

## Updating the Server

After making changes to the MCP server:

1. Save your changes to `mcp_server.py`
2. Completely quit and restart Claude Desktop
3. The new version will be loaded automatically

## Security Considerations

- The MCP server runs locally on your machine with full access to the Care-Beacon API
- It does not expose any authentication or require API keys
- If using the production API, be aware that queries will consume your API quota
- Consider adding rate limiting or authentication if exposing this more broadly

## Learn More

- [Model Context Protocol Documentation](https://modelcontextprotocol.io/)
- [Claude Desktop MCP Setup Guide](https://docs.anthropic.com/claude/docs/model-context-protocol)
- [Care-Beacon API Documentation](http://localhost:8000/docs)
