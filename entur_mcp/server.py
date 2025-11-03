"""FastMCP server exposing Entur Journey Planner tooling."""

from __future__ import annotations

from typing import Iterable, Mapping, Optional, Sequence

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from entur_mcp.models import (
    NearestPlacesResult,
    ServiceAlertsResult,
    StopDeparturesResult,
    TripPlanResult,
)
from entur_mcp.service import (
    AlertLookupError,
    DeparturesLookupError,
    EnturService,
    EnturServiceError,
    LocationLookupError,
    TripPlanningError,
)

TransportMode = (
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
)

SeverityLevel = (
    "unknown",
    "noImpact",
    "verySlight",
    "slight",
    "normal",
    "severe",
    "verySevere",
    "undefined",
)

INSTRUCTIONS = (
    "This server provides access to Entur's Journey Planner APIs for Norwegian public transport. "
    "Always mention Entur as the data source and follow their usage guidelines, including supplying "
    "a descriptive ET-Client-Name header when reusing this service. Results are derived from real-time "
    "and timetable data provided by Entur partners."
)

server = FastMCP(
    name="entur-journey-planner",
    version="0.1.0",
    instructions=INSTRUCTIONS,
    website_url="https://developer.entur.org",
)

service = EnturService()


class PlanTripArgs(BaseModel):
    """Arguments for the plan_trip tool."""

    from_place_id: Optional[str] = Field(
        default=None,
        description="Entur stop place id for the origin (e.g. 'NSR:StopPlace:58404').",
    )
    from_text: Optional[str] = Field(
        default=None,
        description="Free-text origin. The server resolves this using Entur's geocoder.",
    )
    from_latitude: Optional[float] = Field(
        default=None,
        description="Origin latitude in decimal degrees (WGS84).",
    )
    from_longitude: Optional[float] = Field(
        default=None,
        description="Origin longitude in decimal degrees (WGS84).",
    )
    to_place_id: Optional[str] = Field(
        default=None,
        description="Entur stop place id for the destination.",
    )
    to_text: Optional[str] = Field(
        default=None,
        description="Free-text destination. The server resolves this using Entur's geocoder.",
    )
    to_latitude: Optional[float] = Field(
        default=None,
        description="Destination latitude in decimal degrees (WGS84).",
    )
    to_longitude: Optional[float] = Field(
        default=None,
        description="Destination longitude in decimal degrees (WGS84).",
    )
    departure_time: Optional[str] = Field(
        default=None,
        description="ISO8601 timestamp for desired departure (defaults to now).",
    )
    arrive_by: Optional[bool] = Field(
        default=False,
        description="Interpret departure_time as latest arrival instead of earliest departure.",
    )
    page_cursor: Optional[str] = Field(
        default=None,
        description="Pagination cursor returned by a previous trip search.",
    )
    num_trip_patterns: Optional[int] = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum number of itineraries to return (1-10).",
    )
    search_window: Optional[int] = Field(
        default=None,
        ge=1,
        description="Override search window in minutes. Leave blank for Entur default.",
    )
    transport_modes: Optional[list[str]] = Field(
        default=None,
        description="Optional list of transport modes to prioritise "
        "(e.g. ['rail', 'bus']). Valid modes: " + ", ".join(TransportMode),
    )


class StopDeparturesArgs(BaseModel):
    """Arguments for the stop_departures tool."""

    stop_place_id: Optional[str] = Field(
        default=None,
        description="Entur stop place id to fetch departures for.",
    )
    stop_text: Optional[str] = Field(
        default=None,
        description="Free-text stop description to resolve via Entur's geocoder.",
    )
    stop_latitude: Optional[float] = Field(
        default=None,
        description="Latitude used to resolve the nearest stop place.",
    )
    stop_longitude: Optional[float] = Field(
        default=None,
        description="Longitude used to resolve the nearest stop place.",
    )
    start_time: Optional[str] = Field(
        default=None,
        description="ISO8601 timestamp anchoring the departures window (defaults to now).",
    )
    time_range_minutes: int = Field(
        default=120,
        ge=1,
        description="Number of minutes to include after start_time.",
    )
    number_of_departures: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of departures to return (1-50).",
    )


class NearestPlacesArgs(BaseModel):
    """Arguments for the nearest_places tool."""

    latitude: Optional[float] = Field(
        default=None,
        description="Latitude of the location to search from.",
    )
    longitude: Optional[float] = Field(
        default=None,
        description="Longitude of the location to search from.",
    )
    text: Optional[str] = Field(
        default=None,
        description="Free-text location. The server geocodes this before searching.",
    )
    maximum_distance: float = Field(
        default=2000.0,
        gt=0,
        description="Maximum walking distance (meters) to consider.",
    )
    maximum_results: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of places to return (1-50).",
    )
    include_place_types: Optional[list[str]] = Field(
        default=None,
        description="Optional list of Entur place types to include (e.g. ['stopPlace', 'quay']).",
    )


class ServiceAlertsArgs(BaseModel):
    """Arguments for the service_alerts tool."""

    stop_place_id: Optional[str] = Field(
        default=None,
        description="Filter alerts affecting a specific stop place id.",
    )
    stop_text: Optional[str] = Field(
        default=None,
        description="Free-text stop description to resolve before fetching alerts.",
    )
    severities: Optional[list[str]] = Field(
        default=None,
        description="Optional subset of severity levels to include. "
        "Valid levels: " + ", ".join(SeverityLevel),
    )
    limit: int = Field(
        default=20,
        ge=1,
        description="Maximum number of alerts to return.",
    )


def _validate_location_arguments(
    arguments: Mapping[str, object], *, prefixes: Sequence[str]
) -> None:
    """Ensure location inputs contain resolvable hints for each prefix."""

    for prefix in prefixes:
        place_id = arguments.get(f"{prefix}_place_id")
        text = arguments.get(f"{prefix}_text")
        lat = arguments.get(f"{prefix}_latitude")
        lon = arguments.get(f"{prefix}_longitude")

        has_coordinates = lat is not None and lon is not None

        if place_id or text or has_coordinates:
            continue

        raise ValueError(
            f"Provide either '{prefix}_place_id', '{prefix}_text', or both "
            f"'{prefix}_latitude' and '{prefix}_longitude'."
        )


def _validate_allowed_values(
    values: Iterable[str] | None, allowed: Sequence[str], label: str
) -> None:
    """Ensure optional lists only contain accepted values."""

    if not values:
        return
    invalid = sorted({value for value in values if value not in allowed})
    if invalid:
        raise ValueError(
            f"Invalid {label}: {', '.join(invalid)}. Allowed values are: {', '.join(allowed)}."
        )


@server.tool(
    name="plan_trip",
    description=(
        "Plan door-to-door trips between two places using Entur's multimodal journey planner. "
        "Provide stop ids, free text, or coordinates for the origin and destination."
    ),
    output_schema=TripPlanResult.model_json_schema(),
)
async def plan_trip(arguments: PlanTripArgs) -> TripPlanResult:
    """Plan a trip between two locations."""

    data = arguments.model_dump()
    _validate_location_arguments(data, prefixes=("from", "to"))
    _validate_allowed_values(arguments.transport_modes, TransportMode, "transport modes")

    try:
        result = await service.plan_trip(
            from_place_id=arguments.from_place_id,
            from_text=arguments.from_text,
            from_latitude=arguments.from_latitude,
            from_longitude=arguments.from_longitude,
            to_place_id=arguments.to_place_id,
            to_text=arguments.to_text,
            to_latitude=arguments.to_latitude,
            to_longitude=arguments.to_longitude,
            departure_time=arguments.departure_time,
            arrive_by=arguments.arrive_by,
            page_cursor=arguments.page_cursor,
            num_trip_patterns=arguments.num_trip_patterns,
            search_window=arguments.search_window,
            transport_modes=arguments.transport_modes,
        )
    except (LocationLookupError, TripPlanningError) as exc:
        raise ValueError(str(exc)) from exc
    except EnturServiceError as exc:
        raise ValueError(f"Entur service error: {exc}") from exc

    return result


@server.tool(
    name="stop_departures",
    description=(
        "Retrieve upcoming departures for a specific stop place, including realtime delays when available."
    ),
    output_schema=StopDeparturesResult.model_json_schema(),
)
async def stop_departures(arguments: StopDeparturesArgs) -> StopDeparturesResult:
    """Fetch realtime departures for a stop place."""

    data = arguments.model_dump()
    _validate_location_arguments(data, prefixes=("stop",))

    try:
        result = await service.get_stop_departures(
            stop_place_id=arguments.stop_place_id,
            stop_text=arguments.stop_text,
            stop_latitude=arguments.stop_latitude,
            stop_longitude=arguments.stop_longitude,
            start_time=arguments.start_time,
            time_range_minutes=arguments.time_range_minutes,
            number_of_departures=arguments.number_of_departures,
        )
    except (LocationLookupError, DeparturesLookupError) as exc:
        raise ValueError(str(exc)) from exc
    except EnturServiceError as exc:
        raise ValueError(f"Entur service error: {exc}") from exc

    return result


@server.tool(
    name="nearest_places",
    description=(
        "Find nearby transport stops, quays, or other transit facilities based on coordinates or a location name."
    ),
    output_schema=NearestPlacesResult.model_json_schema(),
)
async def nearest_places(arguments: NearestPlacesArgs) -> NearestPlacesResult:
    """Find nearby transit places using Entur's nearest lookup."""

    has_coordinates = arguments.latitude is not None and arguments.longitude is not None
    if not (has_coordinates or arguments.text):
        raise ValueError(
            "Provide either both 'latitude' and 'longitude' or a 'text' query for nearest searches."
        )

    try:
        result = await service.get_nearest_places(
            latitude=arguments.latitude,
            longitude=arguments.longitude,
            text=arguments.text,
            maximum_distance=float(arguments.maximum_distance),
            maximum_results=arguments.maximum_results,
            include_place_types=arguments.include_place_types,
        )
    except LocationLookupError as exc:
        raise ValueError(str(exc)) from exc
    except EnturServiceError as exc:
        raise ValueError(f"Entur service error: {exc}") from exc

    return result


@server.tool(
    name="service_alerts",
    description=(
        "List active service alerts and disruptions published through Entur, optionally filtered by stop or severity."
    ),
    output_schema=ServiceAlertsResult.model_json_schema(),
)
async def service_alerts(arguments: ServiceAlertsArgs) -> ServiceAlertsResult:
    """Retrieve current service alerts from Entur."""

    data = arguments.model_dump()
    if arguments.stop_place_id or arguments.stop_text:
        _validate_location_arguments(data, prefixes=("stop",))

    _validate_allowed_values(arguments.severities, SeverityLevel, "severity levels")

    try:
        result = await service.get_service_alerts(
            stop_place_id=arguments.stop_place_id,
            stop_text=arguments.stop_text,
            severities=arguments.severities,
            limit=arguments.limit,
        )
    except (LocationLookupError, AlertLookupError) as exc:
        raise ValueError(str(exc)) from exc
    except EnturServiceError as exc:
        raise ValueError(f"Entur service error: {exc}") from exc

    return result


@server.tool
def greet(name: str) -> str:
    return f"Hello, {name}!"


__all__ = ["server"]

if __name__ == "__main__":
    server.run()
