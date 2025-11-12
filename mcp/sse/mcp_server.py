"""MCP Server for Care-Beacon Medical RAG API - HTTP/SSE Transport.

This server exposes the Care-Beacon API as MCP tools using HTTP with
Server-Sent Events (SSE) transport, enabling remote access from Claude Desktop
and other MCP clients.

This implementation can be deployed to render.com or other hosting platforms.
"""

import os
import asyncio
from typing import Any, Optional
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount
from starlette.exceptions import HTTPException
import httpx
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.sse import SseServerTransport
from mcp.types import (
    Tool,
    TextContent,
)

# Configuration
API_BASE_URL = os.getenv("CARE_BEACON_API_URL", "http://localhost:8000")
API_TIMEOUT = float(os.getenv("CARE_BEACON_TIMEOUT", "60.0"))
MCP_API_KEY = os.getenv("MCP_API_KEY", "")  # Required for production

# Create MCP server and SSE transport
mcp_server = Server("care-beacon-medical-rag")
sse = SseServerTransport("/messages/")


def verify_api_key(authorization: Optional[str] = None) -> bool:
    """Verify API key from Authorization header.

    Args:
        authorization: Authorization header value

    Returns:
        True if valid, False otherwise
    """
    # If no API key is configured, allow all requests (development mode)
    if not MCP_API_KEY:
        return True

    if not authorization:
        return False

    # Expected format: "Bearer <api_key>"
    if not authorization.startswith("Bearer "):
        return False

    token = authorization[7:]  # Remove "Bearer " prefix
    return token == MCP_API_KEY


async def root(request: Request):
    """Root endpoint with server information."""
    return JSONResponse({
        "name": "Care-Beacon MCP Server",
        "version": "1.0.0",
        "transport": "sse",
        "status": "running",
        "endpoints": {
            "sse": "/sse",
            "health": "/health"
        }
    })


async def health_check(request: Request):
    """Health check endpoint."""
    try:
        # Check if backend API is accessible
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{API_BASE_URL}/health")
            api_healthy = response.status_code == 200
    except Exception:
        api_healthy = False

    return JSONResponse({
        "status": "healthy" if api_healthy else "degraded",
        "mcp_server": "running",
        "backend_api": "connected" if api_healthy else "disconnected",
        "api_url": API_BASE_URL
    })


async def handle_sse(request: Request):
    """SSE endpoint for MCP communication.

    This endpoint handles the SSE transport for MCP protocol.
    """
    # Get authorization header
    authorization = request.headers.get("authorization")

    # Verify API key
    if not verify_api_key(authorization):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Use Authorization: Bearer <key>"
        )

    # Connect SSE and run MCP server
    async with sse.connect_sse(
        request.scope,
        request.receive,
        request._send
    ) as streams:
        await mcp_server.run(
            streams[0],
            streams[1],
            InitializationOptions(
                server_name="care-beacon-medical-rag",
                server_version="1.0.0",
                capabilities=mcp_server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                )
            )
        )


@mcp_server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="ask_medical_question",
            description=(
                "Ask a medical question about cancer and get evidence-based answers from BC Cancer "
                "and Canadian Cancer Society resources. The system uses RAG (Retrieval-Augmented Generation) "
                "to find relevant information and generate accurate answers with citations. "
                "Use this tool when you need authoritative cancer-related medical information."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The medical question to ask (3-500 characters)",
                        "minLength": 3,
                        "maxLength": 500
                    },
                    "source": {
                        "type": "string",
                        "description": "Filter by information source (optional)",
                        "enum": ["BC Cancer", "Canadian Cancer Society"]
                    },
                    "min_similarity": {
                        "type": "number",
                        "description": "Minimum similarity score (0.0-1.0) for sources to be included. Higher values return fewer but more relevant sources. Default is 0.5 (50%)",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.5
                    }
                },
                "required": ["question"]
            }
        ),
        Tool(
            name="get_system_stats",
            description=(
                "Get usage statistics for the Care-Beacon system including LLM costs, cache performance, "
                "and token usage. Use this to monitor system usage and efficiency."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]


@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    """Handle tool calls."""
    if arguments is None:
        arguments = {}

    if name == "ask_medical_question":
        return await ask_medical_question(arguments)
    elif name == "get_system_stats":
        return await get_system_stats()
    else:
        raise ValueError(f"Unknown tool: {name}")


async def ask_medical_question(arguments: dict) -> list[TextContent]:
    """Ask a medical question using the Care-Beacon API."""
    question = arguments.get("question")
    if not question:
        return [TextContent(
            type="text",
            text="Error: 'question' parameter is required"
        )]

    # Build request payload
    payload = {
        "question": question,
        "min_similarity": arguments.get("min_similarity", 0.5)
    }

    # Add optional filters
    if "source" in arguments:
        payload["source"] = arguments["source"]

    # Make API request
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(
                f"{API_BASE_URL}/api/v1/ask",
                json=payload
            )
            response.raise_for_status()
            data = response.json()

        # Format response
        answer_text = data.get("answer", "")
        sources = data.get("sources", [])
        metadata = data.get("metadata", {})
        disclaimer = data.get("disclaimer")

        # Build formatted response
        result = f"## Answer\n\n{answer_text}\n\n"

        # Add sources
        if sources:
            result += "## Sources\n\n"
            for i, source in enumerate(sources, 1):
                similarity = source.get("similarity_score", 0) * 100
                result += f"{i}. **{source.get('article_title')}** - {source.get('section')}\n"
                result += f"   - Source: {source.get('source')}\n"
                result += f"   - Similarity: {similarity:.0f}%\n"
                result += f"   - URL: {source.get('url')}\n"
                if source.get("text_excerpt"):
                    result += f"   - Excerpt: \"{source.get('text_excerpt')}\"\n"
                result += "\n"

        # Add metadata
        if metadata:
            result += "## Metadata\n\n"
            if metadata.get("cached"):
                result += "- **Cached**: Yes (retrieved from cache)\n"
            else:
                result += "- **Cached**: No (freshly generated)\n"
            result += f"- **Model**: {data.get('model', 'unknown')}\n"
            result += f"- **Tokens Used**: {metadata.get('tokens_used', 0)}\n"
            result += f"- **Cost**: ${metadata.get('cost', 0):.6f}\n"
            result += f"- **Generation Time**: {metadata.get('generation_time_ms', 0):.0f}ms\n"
            result += f"- **Sources Used**: {metadata.get('sources_count', 0)}\n"

        # Add disclaimer
        if disclaimer:
            result += f"\n---\n\n*{disclaimer}*\n"

        return [TextContent(type="text", text=result)]

    except httpx.HTTPStatusError as e:
        error_msg = f"API Error ({e.response.status_code}): "
        try:
            error_data = e.response.json()
            error_msg += error_data.get("message", str(e))
        except:
            error_msg += str(e)

        return [TextContent(type="text", text=f"Error: {error_msg}")]

    except httpx.RequestError as e:
        return [TextContent(
            type="text",
            text=f"Connection Error: Could not connect to Care-Beacon API at {API_BASE_URL}. "
                 f"Make sure the API is running. Error: {str(e)}"
        )]

    except Exception as e:
        return [TextContent(type="text", text=f"Unexpected Error: {str(e)}")]


async def get_system_stats() -> list[TextContent]:
    """Get system statistics from the Care-Beacon API."""
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.get(f"{API_BASE_URL}/api/v1/stats")
            response.raise_for_status()
            data = response.json()

        # Format statistics
        result = "## Care-Beacon System Statistics\n\n"

        # Overall costs
        result += "### Cost Summary\n\n"
        result += f"- **Total Cost**: ${data.get('total_cost', 0):.4f}\n"
        result += f"- **Cost Saved (Cache)**: ${data.get('total_cost_saved', 0):.4f}\n"
        result += f"- **Cost Reduction**: {data.get('cost_reduction_percent', 0):.1f}%\n\n"

        # LLM Statistics
        llm_stats = data.get("llm", {})
        if llm_stats:
            result += "### LLM Usage\n\n"
            result += f"- **Total Calls**: {llm_stats.get('total_calls', 0)}\n"
            result += f"- **Total Tokens**: {llm_stats.get('total_tokens', 0):,}\n"
            result += f"- **Input Tokens**: {llm_stats.get('total_input_tokens', 0):,}\n"
            result += f"- **Output Tokens**: {llm_stats.get('total_output_tokens', 0):,}\n"
            result += f"- **Total Cost**: ${llm_stats.get('total_cost', 0):.4f}\n\n"

        # Cache Statistics
        cache_stats = data.get("cache", {})
        if cache_stats:
            result += "### Cache Performance\n\n"
            result += f"- **Enabled**: {cache_stats.get('enabled', False)}\n"
            result += f"- **Total Queries**: {cache_stats.get('total_queries', 0)}\n"
            result += f"- **Cache Hits**: {cache_stats.get('cache_hits', 0)}\n"
            result += f"- **Cache Misses**: {cache_stats.get('cache_misses', 0)}\n"
            hit_rate = cache_stats.get('hit_rate', 0) * 100
            result += f"- **Hit Rate**: {hit_rate:.1f}%\n\n"

        # Retrieval Statistics
        retrieval_stats = data.get("retrieval", {})
        if retrieval_stats:
            result += "### Retrieval/Embedding\n\n"
            result += f"- **Total Embeddings**: {retrieval_stats.get('total_embeddings', 0)}\n"
            result += f"- **Total Cost**: ${retrieval_stats.get('total_cost', 0):.6f}\n"

        return [TextContent(type="text", text=result)]

    except httpx.HTTPStatusError as e:
        error_msg = f"API Error ({e.response.status_code}): "
        try:
            error_data = e.response.json()
            error_msg += error_data.get("message", str(e))
        except:
            error_msg += str(e)

        return [TextContent(type="text", text=f"Error: {error_msg}")]

    except httpx.RequestError as e:
        return [TextContent(
            type="text",
            text=f"Connection Error: Could not connect to Care-Beacon API at {API_BASE_URL}. "
                 f"Make sure the API is running. Error: {str(e)}"
        )]

    except Exception as e:
        return [TextContent(type="text", text=f"Unexpected Error: {str(e)}")]


# Create Starlette app with routes
app = Starlette(
    debug=False,
    routes=[
        Route("/", root, methods=["GET"]),
        Route("/health", health_check, methods=["GET"]),
        Route("/sse", handle_sse, methods=["GET"]),
        Mount("/messages", app=sse.handle_post_message),
    ]
)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8001"))

    print("=" * 70)
    print("Care-Beacon MCP Server (HTTP/SSE)")
    print("=" * 70)
    print(f"🚀 Starting server on port {port}")
    print(f"📡 API URL: {API_BASE_URL}")
    print(f"🔑 Auth: {'Enabled (API key required)' if MCP_API_KEY else 'Disabled (development mode)'}")
    print(f"🔗 SSE Endpoint: http://0.0.0.0:{port}/sse")
    print(f"❤️  Health Check: http://0.0.0.0:{port}/health")
    print("=" * 70)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
