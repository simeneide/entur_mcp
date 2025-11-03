# Entur MCP Server

`entur-mcp` is a [FastMCP](https://gofastmcp.com/) server that exposes Entur's Journey Planner APIs through the [Model Context Protocol](https://spec.modelcontextprotocol.io). It lets assistants and automations plan trips, inspect departures, and list service alerts for Norwegian public transport.

## Features
- `plan_trip`: multimodal journey planning between two places.
- `stop_departures`: realtime departures for a stop place.
- `nearest_places`: nearby stops, quays, and transit facilities.
- `service_alerts`: active disruptions, filterable by stop and severity.

## Installation

Using [uv](https://docs.astral.sh/uv):

```bash
uv tool install entur-mcp
```

Alternatively:

```bash
pipx install entur-mcp
# or
pip install entur-mcp
```

## Usage

### FastMCP CLI (recommended)

The project ships with a FastMCP server object named `server`. Run it with the FastMCP CLI (optionally via `uv` to pick up the project environment):

```bash
# From the repository root
uv run fastmcp run entur_mcp/server.py

# Explicit object selection (optional)
uv run fastmcp run entur_mcp/server.py:server

# Streamable HTTP transport for remote agents
uv run fastmcp run entur_mcp/server.py --transport http --host 0.0.0.0 --port 8000
# -> exposes https://localhost:8000/mcp by default
```

### Convenience entrypoint

A stdio wrapper is still provided for compatibility:

```bash
entur-mcp          # via console script
# or
python -m entur_mcp
```

The server registers its tools and schemas with MCP clients automatically.

## Configuration

Entur requires callers to identify themselves with a descriptive client name. Configure the following environment variables before launching the server:

- `ENTUR_CLIENT_NAME`: **Required**. e.g. `MyApp/1.0 (contact@example.com)`.
- `ENTUR_CLIENT_ID`: Optional. Supply an Entur-issued API key if you have one.
- `ENTUR_USER_AGENT`: Optional. Overrides the HTTP `User-Agent`. Defaults to `ENTUR_CLIENT_NAME`.

If the variables are omitted, the server falls back to a placeholder value, but you should always supply your own contact details to comply with Entur's usage guidelines.

## Development

```bash
uv venv  # or python -m venv .venv
source .venv/bin/activate
pip install -e .[test]
pytest
```

The test suite uses `respx` to mock Entur's HTTP APIs. No network calls are made during tests.

## FastMCP Cloud deployment

FastMCP Cloud makes your server available at a public HTTPS URL. Deploy in three steps:

1. Push this repository to GitHub (public or private).
2. Sign in to [fastmcp.cloud](https://fastmcp.cloud) with your GitHub account and create a new project.
3. Point the project at your repo and use `entur_mcp/server.py:server` as the entrypoint.

FastMCP Cloud installs dependencies from `pyproject.toml`, builds the project, and returns a URL such as `https://<project>.fastmcp.app/mcp`. Share that endpoint with MCP-compatible agents. (Replace the URL here once your deployment is live.)

## License

Distributed under the MIT License. See `LICENSE` for details.
