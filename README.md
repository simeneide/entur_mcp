# Entur MCP Server

`entur-mcp` exposes Entur's Journey Planner APIs through the [Model Context Protocol](https://spec.modelcontextprotocol.io), enabling assistants and automations to plan trips, inspect departures, and list service alerts for Norwegian public transport.

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

```bash
# Run over stdio (default for MCP clients)
entur-mcp

# Or explicitly
python -m entur_mcp
```

The server announces its tools and schemas according to the MCP specification, so any compliant client can consume it.

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

## License

Distributed under the MIT License. See `LICENSE` for details.
