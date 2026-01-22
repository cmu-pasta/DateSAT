#!/usr/bin/env python3
"""
Launch script for the DateSMT MCP Server.

This script starts an HTTP server with SSE (Server-Sent Events) transport
for the Model Context Protocol, allowing AI agents to access DateSMT's
constraint solving capabilities.

Usage:
    python bin/datesmt_mcp.py                    # Start on default port 8000
    python bin/datesmt_mcp.py --port 3000        # Start on port 3000
    python bin/datesmt_mcp.py --host 0.0.0.0     # Listen on all interfaces
"""

import argparse
import os
import sys

# Add the parent directory to the path so we can import datesmt
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def main():
    parser = argparse.ArgumentParser(
        description="DateSMT MCP Server - Expose DateSMT constraint solving via MCP protocol",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Start server on default port (8000)
    python bin/datesmt_mcp.py

    # Start server on custom port
    python bin/datesmt_mcp.py --port 3000

    # Listen on all network interfaces
    python bin/datesmt_mcp.py --host 0.0.0.0 --port 8080

    # With auto-reload for development
    python bin/datesmt_mcp.py --reload

MCP Endpoint:
    Once running, the MCP server is available at:
    http://<host>:<port>/sse

    AI agents can connect to this endpoint to use the 'solve' tool
    for solving date constraints.
        """
    )

    parser.add_argument(
        "-p", "--port",
        type=int,
        default=8000,
        help="Port to bind the server to (default: 8000)"
    )

    parser.add_argument(
        "-H", "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind the server to (default: 127.0.0.1)"
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )

    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is required to run the MCP server.", file=sys.stderr)
        print("Install it with: pip install uvicorn", file=sys.stderr)
        sys.exit(1)

    print(f"Starting DateSMT MCP Server...")
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"MCP SSE Endpoint: http://{args.host}:{args.port}/sse")
    print()

    uvicorn.run(
        "bin.mcp_server:sse_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()
