"""MCP server entrypoint exposing Entur Journey Planner tooling."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from mcp import types
from mcp.server import Server

from .models import (
    NearestPlacesResult,
    ServiceAlertsResult,
    StopDeparturesResult,
    TripPlanResult,
)
from .service import (
    AlertLookupError,
    DeparturesLookupError,
    EnturService,
    EnturServiceError,
    LocationLookupError,
    TripPlanningError,
)

server = Server(
    name="entur-journey-planner",
    version="0.1.0",
    instructions=(
        "This server provides access to Entur's Journey Planner APIs for Norwegian public transport. "
        "Always mention Entur as the data source and follow their usage guidelines, including supplying "
        "a descriptive ET-Client-Name header when reusing this service. Results are derived from real-time "
        "and timetable data provided by Entur partners."
    ),
    website_url="https://developer.entur.org",
)

service = EnturService()

TRANSPORT_MODES = [
    "air",
    "bus",
    "cableway",
    "water",
    "funicular",
    "lift",
    "rail",
    "metro",
    "taxi",
    "tram",
    "trolleybus",
    "monorail",
    "coach",
    "unknown",
]

SEVERITY_LEVELS = [
    "unknown",
    "noImpact",
    "verySlight",
    "slight",
    "normal",
    "severe",
    "verySevere",
    "undefined",
]

PLAN_TRIP_INPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "from_place_id": {
            "type": "string",
            "description": "Entur stop place id for the origin (e.g. 'NSR:StopPlace:58404').",
        },
        "from_text": {
            "type": "string",
            "description": "Free-text origin (e.g. 'Nationaltheatret'). The server will resolve this via Entur's geocoder.",
        },
        "from_latitude": {
            "type": "number",
            "description": "Latitude for the origin in decimal degrees (WGS84).",
        },
        "from_longitude": {
            "type": "number",
            "description": "Longitude for the origin in decimal degrees (WGS84).",
        },
        "to_place_id": {
            "type": "string",
            "description": "Entur stop place id for the destination.",
        },
        "to_text": {
            "type": "string",
            "description": "Free-text destination. The server will resolve this via Entur's geocoder.",
        },
        "to_latitude": {
            "type": "number",
            "description": "Latitude for the destination in decimal degrees (WGS84).",
        },
        "to_longitude": {
            "type": "number",
            "description": "Longitude for the destination in decimal degrees (WGS84).",
        },
        "departure_time": {
            "type": "string",
            "description": "ISO8601 timestamp for desired departure (defaults to now if omitted).",
        },
        "arrive_by": {
            "type": "boolean",
            "description": "Interpret departure_time as latest arrival time instead of earliest departure.",
            "default": False,
        },
        "page_cursor": {
            "type": "string",
            "description": "Pagination cursor returned by a previous trip search to fetch more results.",
        },
        "num_trip_patterns": {
            "type": "integer",
            "description": "Maximum number of itineraries to return (1-10, default 5).",
            "minimum": 1,
            "maximum": 10,
            "default": 5,
        },
        "search_window": {
            "type": "integer",
            "description": "Override search window in minutes. Leave blank to let Entur decide.",
            "minimum": 1,
        },
        "transport_modes": {
            "type": "array",
            "description": "Optional list of transport modes to prioritise (e.g. ['rail', 'bus']).",
            "items": {"type": "string", "enum": TRANSPORT_MODES},
        },
    },
    "required": [],
    "additionalProperties": False,
}

STOP_DEPARTURES_INPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "stop_place_id": {
            "type": "string",
            "description": "Entur stop place id to fetch departures for.",
        },
        "stop_text": {
            "type": "string",
            "description": "Free-text stop description to resolve via Entur's geocoder.",
        },
        "stop_latitude": {
            "type": "number",
            "description": "Latitude to resolve the nearest stop place.",
        },
        "stop_longitude": {
            "type": "number",
            "description": "Longitude to resolve the nearest stop place.",
        },
        "start_time": {
            "type": "string",
            "description": "ISO8601 timestamp to anchor the departures window (default now).",
        },
        "time_range_minutes": {
            "type": "integer",
            "description": "Number of minutes to include after start_time (default 120 minutes).",
            "minimum": 1,
            "default": 120,
        },
        "number_of_departures": {
            "type": "integer",
            "description": "Maximum number of departures to return (default 10, max 50).",
            "minimum": 1,
            "maximum": 50,
            "default": 10,
        },
    },
    "required": [],
    "additionalProperties": False,
}

NEAREST_PLACES_INPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "latitude": {
            "type": "number",
            "description": "Latitude of the location to search from.",
        },
        "longitude": {
            "type": "number",
            "description": "Longitude of the location to search from.",
        },
        "text": {
            "type": "string",
            "description": "Free-text location; geocoded to coordinates before searching.",
        },
        "maximum_distance": {
            "type": "number",
            "description": "Maximum walking distance (meters) to consider (default 2000).",
            "minimum": 1,
            "default": 2000,
        },
        "maximum_results": {
            "type": "integer",
            "description": "Maximum number of places to return (default 10).",
            "minimum": 1,
            "maximum": 50,
            "default": 10,
        },
        "include_place_types": {
            "type": "array",
            "description": "Optional list of Entur place types to include (e.g. ['stopPlace', 'quay']).",
            "items": {"type": "string"},
        },
    },
    "required": [],
    "additionalProperties": False,
}

SERVICE_ALERTS_INPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "stop_place_id": {
            "type": "string",
            "description": "Filter alerts affecting a specific stop place id.",
        },
        "stop_text": {
            "type": "string",
            "description": "Free-text stop description to resolve before fetching alerts.",
        },
        "severities": {
            "type": "array",
            "description": "Optional subset of severity levels to include.",
            "items": {"type": "string", "enum": SEVERITY_LEVELS},
        },
        "limit": {
            "type": "integer",
            "description": "Maximum number of alerts to return (default 20).",
            "minimum": 1,
            "default": 20,
        },
    },
    "required": [],
    "additionalProperties": False,
}

PLAN_TRIP_OUTPUT_SCHEMA = TripPlanResult.model_json_schema()
STOP_DEPARTURES_OUTPUT_SCHEMA = StopDeparturesResult.model_json_schema()
NEAREST_PLACES_OUTPUT_SCHEMA = NearestPlacesResult.model_json_schema()
SERVICE_ALERTS_OUTPUT_SCHEMA = ServiceAlertsResult.model_json_schema()


@server.list_tools()
async def list_tools() -> List[types.Tool]:
    """Expose the available Entur tools to MCP clients."""

    return [
        types.Tool(
            name="plan_trip",
            description=(
                "Plan door-to-door trips between two places using Entur's multimodal journey planner. "
                "Provide stop ids, free text, or coordinates for the origin and destination."
            ),
            inputSchema=PLAN_TRIP_INPUT_SCHEMA,
            outputSchema=PLAN_TRIP_OUTPUT_SCHEMA,
        ),
        types.Tool(
            name="stop_departures",
            description=(
                "Retrieve upcoming departures for a specific stop place, including realtime delays when available."
            ),
            inputSchema=STOP_DEPARTURES_INPUT_SCHEMA,
            outputSchema=STOP_DEPARTURES_OUTPUT_SCHEMA,
        ),
        types.Tool(
            name="nearest_places",
            description=(
                "Find nearby transport stops, quays, or other transit facilities based on coordinates or a location name."
            ),
            inputSchema=NEAREST_PLACES_INPUT_SCHEMA,
            outputSchema=NEAREST_PLACES_OUTPUT_SCHEMA,
        ),
        types.Tool(
            name="service_alerts",
            description=(
                "List active service alerts and disruptions published through Entur, optionally filtered by stop or severity."
            ),
            inputSchema=SERVICE_ALERTS_INPUT_SCHEMA,
            outputSchema=SERVICE_ALERTS_OUTPUT_SCHEMA,
        ),
    ]


@server.call_tool()
async def call_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch tool invocations to the Entur service."""

    try:
        if tool_name == "plan_trip":
            _validate_location_arguments(arguments, prefixes=("from", "to"))
            result = await service.plan_trip(
                from_place_id=arguments.get("from_place_id"),
                from_text=arguments.get("from_text"),
                from_latitude=arguments.get("from_latitude"),
                from_longitude=arguments.get("from_longitude"),
                to_place_id=arguments.get("to_place_id"),
                to_text=arguments.get("to_text"),
                to_latitude=arguments.get("to_latitude"),
                to_longitude=arguments.get("to_longitude"),
                departure_time=arguments.get("departure_time"),
                arrive_by=bool(arguments.get("arrive_by")),
                page_cursor=arguments.get("page_cursor"),
                num_trip_patterns=_coerce_int(arguments.get("num_trip_patterns"), default=5),
                search_window=_coerce_int(arguments.get("search_window")),
                transport_modes=_coerce_str_list(arguments.get("transport_modes")),
            )
            return result.model_dump(mode="json")

        if tool_name == "stop_departures":
            _validate_location_arguments(arguments, prefixes=("stop",))
            result = await service.get_stop_departures(
                stop_place_id=arguments.get("stop_place_id"),
                stop_text=arguments.get("stop_text"),
                stop_latitude=arguments.get("stop_latitude"),
                stop_longitude=arguments.get("stop_longitude"),
                start_time=arguments.get("start_time"),
                time_range_minutes=_coerce_int(arguments.get("time_range_minutes"), default=120),
                number_of_departures=_coerce_int(arguments.get("number_of_departures"), default=10),
            )
            return result.model_dump(mode="json")

        if tool_name == "nearest_places":
            if not (
                (_is_number(arguments.get("latitude")) and _is_number(arguments.get("longitude")))
                or arguments.get("text")
            ):
                raise ValueError(
                    "Provide either both 'latitude' and 'longitude' or a 'text' query for nearest searches."
                )
            result = await service.get_nearest_places(
                latitude=arguments.get("latitude"),
                longitude=arguments.get("longitude"),
                text=arguments.get("text"),
                maximum_distance=float(arguments.get("maximum_distance")) if arguments.get("maximum_distance") else 2000.0,
                maximum_results=_coerce_int(arguments.get("maximum_results"), default=10),
                include_place_types=_coerce_str_list(arguments.get("include_place_types")),
            )
            return result.model_dump(mode="json")

        if tool_name == "service_alerts":
            if arguments.get("stop_place_id") or arguments.get("stop_text"):
                _validate_location_arguments(arguments, prefixes=("stop",))
            result = await service.get_service_alerts(
                stop_place_id=arguments.get("stop_place_id"),
                stop_text=arguments.get("stop_text"),
                severities=_coerce_str_list(arguments.get("severities")),
                limit=_coerce_int(arguments.get("limit"), default=20),
            )
            return result.model_dump(mode="json")

    except (LocationLookupError, TripPlanningError, DeparturesLookupError, AlertLookupError) as exc:
        raise ValueError(str(exc)) from exc
    except EnturServiceError as exc:
        raise ValueError(f"Entur service error: {exc}") from exc

    raise ValueError(f"Unknown tool '{tool_name}'.")


def _validate_location_arguments(arguments: Dict[str, Any], *, prefixes: Sequence[str]) -> None:
    """Ensure location inputs contain resolvable hints for each prefix."""

    for prefix in prefixes:
        place_id = arguments.get(f"{prefix}_place_id")
        text = arguments.get(f"{prefix}_text")
        lat = arguments.get(f"{prefix}_latitude")
        lon = arguments.get(f"{prefix}_longitude")

        if place_id or text:
            continue
        if _is_number(lat) and _is_number(lon):
            continue
        raise ValueError(
            f"Provide either '{prefix}_place_id', '{prefix}_text', or both '{prefix}_latitude' and '{prefix}_longitude'."
        )


def _is_number(value: Any) -> bool:
    try:
        return value is not None and float(value) == float(value)
    except (TypeError, ValueError):
        return False


def _coerce_int(value: Any, *, default: int | None = None) -> Optional[int]:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"Expected integer-compatible value, received {value!r}.") from None


def _coerce_str_list(value: Any) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    try:
        return [str(item) for item in value if item is not None]
    except TypeError as exc:  # pragma: no cover - defensive guard for non-iterables
        raise ValueError("Expected a list of strings.") from exc
