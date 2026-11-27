"""Create a static key for /api/mcp (development, evals, smoke tests).

Usage (from the repo root):  make mcp-key NAME=claude-desktop-kam

Prints the raw key once (it is never stored) and the `name:sha256` line that
goes into the MCP_API_KEYS environment variable. Several keys are
comma-separated in that variable; delete a line and redeploy to revoke one.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.mcp_server.auth import make_key  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name", help="Key name, e.g. claude-desktop-kam (letters, digits, . _ -)")
    args = parser.parse_args()
    try:
        raw, line = make_key(args.name)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print("Raw key (shown once; paste it into the client, never commit it):")
    print(f"  {raw}")
    print()
    print("Add this entry to MCP_API_KEYS (comma-separate several):")
    print(f"  {line}")
    print()
    print("Then, for example:")
    print("  vercel env add MCP_API_KEYS preview      # paste the entry when prompted")
    print("  ...and redeploy the preview.")
    print("Client header:  authorization: Bearer <raw key>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
