"""Startup script for Care-Beacon API server.

This script starts the FastAPI server using uvicorn.
"""

import sys
from pathlib import Path
import os

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# Disable ChromaDB telemetry
os.environ["ANONYMIZED_TELEMETRY"] = "False"

import uvicorn
from src.config_loader import get_config


def main():
    """Start the API server."""
    config = get_config()
    api_config = config.get("api", {})

    host = api_config.get("host", "0.0.0.0")
    port = api_config.get("port", 8000)
    debug = api_config.get("debug", False)

    print("=" * 70)
    print("Starting Care-Beacon Medical RAG API")
    print("=" * 70)
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Debug mode: {debug}")
    print()
    print(f"API Documentation: http://localhost:{port}/docs")
    print(f"ReDoc: http://localhost:{port}/redoc")
    print(f"Health Check: http://localhost:{port}/health")
    print("=" * 70)
    print()

    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=debug,  # Auto-reload on code changes in debug mode
        log_level="info" if not debug else "debug",
    )


if __name__ == "__main__":
    main()
