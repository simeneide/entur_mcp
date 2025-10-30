"""CLI entrypoint for running the Entur MCP server over stdio."""

from __future__ import annotations

import anyio

from mcp.server import stdio

from .server import server


async def _amain() -> None:
    async with stdio.stdio_server() as (read_stream, write_stream):
        init_options = server.create_initialization_options()
        await server.run(read_stream, write_stream, init_options)


def main() -> None:
    anyio.run(_amain)


if __name__ == "__main__":
    main()
