"""Pydantic models representing Entur Journey Planner responses exposed via MCP tools."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class PlaceReference(BaseModel):
    """Lightweight reference to a place the assistant can surface."""

    id: str = Field(..., description="Entur internal identifier, e.g. 'NSR:StopPlace:59821'.")
    name: str = Field(..., description="Human friendly place name.")
    latitude: Optional[float] = Field(None, description="Latitude in WGS84 degrees.")
    longitude: Optional[float] = Field(None, description="Longitude in WGS84 degrees.")


class TripLeg(BaseModel):
    """Single leg of an itinerary."""

    mode: str = Field(..., description="Primary transport mode for the leg (e.g. 'rail', 'bus', 'foot').")
    transport_submode: Optional[str] = Field(
        None, description="More specific transport submode when provided by Entur."
    )
    distance_meters: Optional[float] = Field(
        None, description="Approximate distance of the leg in meters."
    )
    duration_seconds: Optional[float] = Field(
        None, description="Duration of the leg given in seconds."
    )
    aimed_start_time: Optional[datetime] = Field(
        None, description="Scheduled start time according to timetable."
    )
    expected_start_time: Optional[datetime] = Field(
        None, description="Latest realtime start time prediction."
    )
    aimed_end_time: Optional[datetime] = Field(
        None, description="Scheduled end time according to timetable."
    )
    expected_end_time: Optional[datetime] = Field(
        None, description="Latest realtime end time prediction."
    )
    realtime: Optional[bool] = Field(
        None, description="Whether realtime updates are applied to this leg."
    )
    line_id: Optional[str] = Field(None, description="Identifier of the line serving this leg.")
    line_name: Optional[str] = Field(None, description="Name of the line serving this leg.")
    line_public_code: Optional[str] = Field(
        None, description="Short public-facing line number or code."
    )
    service_journey_id: Optional[str] = Field(
        None, description="Service journey identifier for detailed follow-up lookups."
    )
    from_place: Optional[PlaceReference] = Field(
        None, description="Starting place for this leg."
    )
    to_place: Optional[PlaceReference] = Field(
        None, description="Ending place for this leg."
    )


class TripItinerary(BaseModel):
    """Collection of trip legs describing one travel alternative."""

    start_time: datetime = Field(..., description="Start time for the itinerary.")
    end_time: datetime = Field(..., description="End time for the itinerary.")
    duration_seconds: float = Field(..., description="Total itinerary duration in seconds.")
    legs: List[TripLeg] = Field(..., description="Ordered list of legs for this itinerary.")


class TripPlanResult(BaseModel):
    """Structured result for the `plan_trip` tool."""

    from_place: PlaceReference = Field(..., description="Origin place resolved by the planner.")
    to_place: PlaceReference = Field(..., description="Destination place resolved by the planner.")
    search_window_minutes: Optional[int] = Field(
        None, description="Actual search window used by the journey planner."
    )
    next_page_cursor: Optional[str] = Field(
        None, description="Cursor token to request the next set of itineraries."
    )
    previous_page_cursor: Optional[str] = Field(
        None, description="Cursor token to request the previous set of itineraries."
    )
    itineraries: List[TripItinerary] = Field(
        ..., description="List of available itineraries sorted by Entur preferences."
    )


class DepartureNotice(BaseModel):
    """Informational notices that may apply to a departure."""

    public_code: Optional[str] = Field(None, description="Provider supplied notice code.")
    text: str = Field(..., description="Notice text in the default locale.")


class StopDeparture(BaseModel):
    """Single departure (or arrival) from a stop place."""

    line_id: str = Field(..., description="Identifier of the associated line.")
    line_name: Optional[str] = Field(None, description="Descriptive line name.")
    line_public_code: Optional[str] = Field(None, description="Short code or number of the line.")
    destination_display: Optional[str] = Field(
        None, description="Front text / destination shown to riders."
    )
    quay_id: str = Field(..., description="Quay/platform identifier for this departure.")
    quay_name: Optional[str] = Field(None, description="Quay/platform name.")
    aimed_departure_time: datetime = Field(..., description="Scheduled departure time.")
    expected_departure_time: datetime = Field(
        ..., description="Realtime adjusted departure time."
    )
    realtime: bool = Field(..., description="Whether realtime information is applied.")
    realtime_state: str = Field(..., description="Realtime status, e.g. 'updated' or 'cancelled'.")
    service_journey_id: Optional[str] = Field(
        None, description="Service journey identifier for this call."
    )
    notices: List[DepartureNotice] = Field(
        default_factory=list, description="Operator notices attached to this departure."
    )


class StopDeparturesResult(BaseModel):
    """Structured departures response for a stop place."""

    stop_place: PlaceReference = Field(..., description="Stop place details.")
    departures: List[StopDeparture] = Field(..., description="Upcoming departures for the stop.")


class NearestPlace(BaseModel):
    """Single place candidate returned by Entur's nearest lookup."""

    place: PlaceReference = Field(..., description="Resolved place information.")
    distance_meters: float = Field(..., description="Walking network distance from query point.")


class NearestPlacesResult(BaseModel):
    """Response payload listing nearby transit places."""

    latitude: float = Field(..., description="Latitude used for the nearest search.")
    longitude: float = Field(..., description="Longitude used for the nearest search.")
    places: List[NearestPlace] = Field(..., description="Ordered nearest places.")


class ServiceAlertImpact(BaseModel):
    """Simplified description of which lines or stops are affected."""

    line_ids: List[str] = Field(default_factory=list, description="Impacted line identifiers.")
    line_public_codes: List[str] = Field(
        default_factory=list, description="Human readable line codes when available."
    )
    stop_place_ids: List[str] = Field(default_factory=list, description="Impacted stop place IDs.")


class ServiceAlert(BaseModel):
    """Single disruption or situation reported by Entur."""

    situation_number: Optional[str] = Field(
        None, description="Operator provided situation number if available."
    )
    severity: Optional[str] = Field(None, description="Severity classification reported by Entur.")
    summary: Optional[str] = Field(None, description="Short headline for the situation.")
    description: Optional[str] = Field(None, description="Longer free-text description.")
    advice: Optional[str] = Field(None, description="Recommended advice to travellers.")
    validity_start: Optional[datetime] = Field(None, description="Validity window start time.")
    validity_end: Optional[datetime] = Field(None, description="Validity window end time.")
    impact: ServiceAlertImpact = Field(
        default_factory=ServiceAlertImpact,
        description="Aggregated view of affected lines and stops.",
    )


class ServiceAlertsResult(BaseModel):
    """Collection of service alerts for the Entur network."""

    alerts: List[ServiceAlert] = Field(..., description="Matching service alerts.")

