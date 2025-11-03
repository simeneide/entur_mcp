"""CLI entrypoint for running the Entur FastMCP server over stdio."""

from __future__ import annotations

from .server import server


def main() -> None:
    server.run()


if __name__ == "__main__":
    main()
