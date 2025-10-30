"""Async client utilities for interacting with Entur Journey Planner APIs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

import httpx

from .models import (
    DepartureNotice,
    NearestPlace,
    NearestPlacesResult,
    PlaceReference,
    ServiceAlert,
    ServiceAlertImpact,
    ServiceAlertsResult,
    StopDeparture,
    StopDeparturesResult,
    TripItinerary,
    TripLeg,
    TripPlanResult,
)

DEFAULT_CLIENT_NAME = "EnturMCP/0.1 (replace-with-contact@example.com)"


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO8601 strings returned by Entur."""

    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _select_text(
    entries: Optional[Iterable[Dict[str, Any]]],
    *,
    preferred_languages: Sequence[str] = ("nb", "nn", "no", "en"),
) -> Optional[str]:
    """Extract a usable text from a list of MultilingualString dictionaries."""

    if not entries:
        return None

    fallback: Optional[str] = None
    for entry in entries:
        if not entry:
            continue
        value = entry.get("value")
        if not value:
            continue
        value = value.strip()
        if not value:
            continue
        language = (entry.get("language") or "").lower()
        if language in preferred_languages:
            return value
        if fallback is None:
            fallback = value
    return fallback


class EnturServiceError(RuntimeError):
    """Base exception for Entur service failures."""


class LocationLookupError(EnturServiceError):
    """Raised when location inputs cannot be resolved to stop places."""


class TripPlanningError(EnturServiceError):
    """Raised when the trip planner request fails."""


class DeparturesLookupError(EnturServiceError):
    """Raised when fetching departures fails."""


class AlertLookupError(EnturServiceError):
    """Raised when fetching disruptions fails."""


@dataclass
class _ResolvedStop:
    """Internal helper describing a resolved stop place."""

    id: str
    name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    def to_place(self) -> PlaceReference:
        return PlaceReference(id=self.id, name=self.name, latitude=self.latitude, longitude=self.longitude)


class EnturService:
    """High-level helper for Entur Journey Planner GraphQL API."""

    GRAPHQL_URL = "https://api.entur.io/journey-planner/v3/graphql"
    GEOCODER_URL = "https://api.entur.io/geocoder/v1/autocomplete"

    def __init__(
        self,
        *,
        client_name: Optional[str] = None,
        client_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        timeout: float = 15.0,
    ) -> None:
        self.client_name = client_name or os.environ.get("ENTUR_CLIENT_NAME") or DEFAULT_CLIENT_NAME
        self.client_id = client_id or os.environ.get("ENTUR_CLIENT_ID")
        self.user_agent = user_agent or os.environ.get("ENTUR_USER_AGENT") or self.client_name
        self.timeout = timeout

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def plan_trip(
        self,
        *,
        from_place_id: Optional[str] = None,
        to_place_id: Optional[str] = None,
        from_text: Optional[str] = None,
        to_text: Optional[str] = None,
        from_latitude: Optional[float] = None,
        from_longitude: Optional[float] = None,
        to_latitude: Optional[float] = None,
        to_longitude: Optional[float] = None,
        departure_time: Optional[str] = None,
        arrive_by: bool = False,
        page_cursor: Optional[str] = None,
        num_trip_patterns: int = 5,
        search_window: Optional[int] = None,
        transport_modes: Optional[Sequence[str]] = None,
    ) -> TripPlanResult:
        """Request itineraries between two stop places."""

        origin = await self._resolve_stop_place(
            place_id=from_place_id,
            text=from_text,
            latitude=from_latitude,
            longitude=from_longitude,
        )
        destination = await self._resolve_stop_place(
            place_id=to_place_id,
            text=to_text,
            latitude=to_latitude,
            longitude=to_longitude,
        )

        variables: Dict[str, Any] = {
            "from": {"place": origin.id},
            "to": {"place": destination.id},
            "arriveBy": arrive_by,
            "numTripPatterns": max(1, min(num_trip_patterns, 10)),
        }
        if departure_time:
            variables["dateTime"] = departure_time
        if search_window:
            variables["searchWindow"] = max(1, search_window)
        if page_cursor:
            variables["pageCursor"] = page_cursor
        if transport_modes:
            modes_payload = []
            for mode in transport_modes:
                normalized = (mode or "").strip().lower()
                if not normalized:
                    continue
                modes_payload.append({"transportMode": normalized})
            if modes_payload:
                variables["modes"] = {"transportModes": modes_payload}

        query = """
            query PlanTrip(
                $from: Location!
                $to: Location!
                $dateTime: DateTime
                $arriveBy: Boolean
                $numTripPatterns: Int
                $searchWindow: Int
                $pageCursor: String
                $modes: Modes
            ) {
                trip(
                    from: $from
                    to: $to
                    dateTime: $dateTime
                    arriveBy: $arriveBy
                    numTripPatterns: $numTripPatterns
                    searchWindow: $searchWindow
                    pageCursor: $pageCursor
                    modes: $modes
                ) {
                    metadata { searchWindowUsed }
                    fromPlace {
                        name
                        latitude
                        longitude
                        vertexType
                        quay { id name latitude longitude stopPlace { id name latitude longitude } }
                    }
                    toPlace {
                        name
                        latitude
                        longitude
                        vertexType
                        quay { id name latitude longitude stopPlace { id name latitude longitude } }
                    }
                    tripPatterns {
                        startTime
                        endTime
                        duration
                        legs {
                            mode
                            transportSubmode
                            distance
                            duration
                            aimedStartTime
                            expectedStartTime
                            aimedEndTime
                            expectedEndTime
                            realtime
                            fromPlace {
                                name
                                latitude
                                longitude
                                vertexType
                                quay { id name latitude longitude stopPlace { id name latitude longitude } }
                            }
                            toPlace {
                                name
                                latitude
                                longitude
                                vertexType
                                quay { id name latitude longitude stopPlace { id name latitude longitude } }
                            }
                            line { id name publicCode transportMode transportSubmode }
                            serviceJourney { id }
                        }
                    }
                    nextPageCursor
                    previousPageCursor
                }
            }
        """

        data = await self._graphql(query, variables)
        trip_payload = data.get("trip")
        if not trip_payload:
            raise TripPlanningError("Entur returned no itineraries for the requested journey.")

        trip_patterns = trip_payload.get("tripPatterns") or []
        itineraries = [
            TripItinerary(
                start_time=_parse_datetime(pattern.get("startTime")),
                end_time=_parse_datetime(pattern.get("endTime")),
                duration_seconds=float(pattern.get("duration") or 0),
                legs=self._build_trip_legs(pattern.get("legs") or []),
            )
            for pattern in trip_patterns
        ]

        if not itineraries:
            itineraries = []

        from_place = self._build_place(trip_payload.get("fromPlace")) or origin.to_place()
        to_place = self._build_place(trip_payload.get("toPlace")) or destination.to_place()

        metadata = trip_payload.get("metadata") or {}
        return TripPlanResult(
            from_place=from_place,
            to_place=to_place,
            search_window_minutes=metadata.get("searchWindowUsed"),
            next_page_cursor=trip_payload.get("nextPageCursor"),
            previous_page_cursor=trip_payload.get("previousPageCursor"),
            itineraries=itineraries,
        )

    async def get_stop_departures(
        self,
        *,
        stop_place_id: Optional[str] = None,
        stop_text: Optional[str] = None,
        stop_latitude: Optional[float] = None,
        stop_longitude: Optional[float] = None,
        start_time: Optional[str] = None,
        time_range_minutes: int = 120,
        number_of_departures: int = 10,
    ) -> StopDeparturesResult:
        """Fetch upcoming departures for a given stop place."""

        resolved = await self._resolve_stop_place(
            place_id=stop_place_id,
            text=stop_text,
            latitude=stop_latitude,
            longitude=stop_longitude,
        )

        variables: Dict[str, Any] = {
            "id": resolved.id,
            "startTime": start_time,
            "timeRange": max(60, time_range_minutes * 60),
            "numberOfDepartures": max(1, min(number_of_departures, 50)),
        }
        variables = {key: value for key, value in variables.items() if value is not None}

        query = """
            query StopDepartures(
                $id: String!
                $startTime: DateTime
                $timeRange: Int!
                $numberOfDepartures: Int!
            ) {
                stopPlace(id: $id) {
                    id
                    name
                    latitude
                    longitude
                    estimatedCalls(
                        startTime: $startTime
                        timeRange: $timeRange
                        numberOfDepartures: $numberOfDepartures
                    ) {
                        realtime
                        realtimeState
                        aimedDepartureTime
                        expectedDepartureTime
                        destinationDisplay { frontText }
                        quay { id name }
                        serviceJourney { id journeyPattern { line { id name publicCode transportMode transportSubmode } } }
                        notices { publicCode text }
                    }
                }
            }
        """

        data = await self._graphql(query, variables)
        stop_payload = data.get("stopPlace")
        if not stop_payload:
            raise DeparturesLookupError(f"Stop place '{resolved.id}' could not be fetched from Entur.")

        departures = [
            self._build_departure(call)
            for call in (stop_payload.get("estimatedCalls") or [])
            if call
        ]

        stop_place = self._build_place(stop_payload) or resolved.to_place()
        return StopDeparturesResult(stop_place=stop_place, departures=departures)

    async def get_nearest_places(
        self,
        *,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        text: Optional[str] = None,
        maximum_distance: float = 2000.0,
        maximum_results: int = 10,
        include_place_types: Optional[Sequence[str]] = None,
    ) -> NearestPlacesResult:
        """Find nearest places by coordinates or free-text lookup."""

        if text and (latitude is None or longitude is None):
            feature = await self._first_geocode_feature(text)
            if not feature:
                raise LocationLookupError(f"Entur geocoder returned no results for '{text}'.")
            coords = feature["geometry"]["coordinates"]
            longitude, latitude = coords[0], coords[1]

        if latitude is None or longitude is None:
            raise LocationLookupError("Provide coordinates or a textual query to find nearby places.")

        place_types = include_place_types or ["stopPlace", "quay"]
        variables: Dict[str, Any] = {
            "latitude": latitude,
            "longitude": longitude,
            "maximumDistance": max(1.0, float(maximum_distance)),
            "maximumResults": max(1, min(int(maximum_results), 50)),
            "placeTypes": list(dict.fromkeys(place_types)),
        }

        query = """
            query NearestPlaces(
                $latitude: Float!
                $longitude: Float!
                $maximumDistance: Float!
                $maximumResults: Int!
                $placeTypes: [FilterPlaceType!]
            ) {
                nearest(
                    latitude: $latitude
                    longitude: $longitude
                    maximumDistance: $maximumDistance
                    maximumResults: $maximumResults
                    filterByPlaceTypes: $placeTypes
                ) {
                    edges {
                        node {
                            distance
                            place {
                                __typename
                                ... on StopPlace { stopPlaceId: id stopPlaceName: name latitude longitude }
                                ... on Quay {
                                    quayId: id
                                    quayName: name
                                    latitude
                                    longitude
                                    stopPlace { id name latitude longitude }
                                }
                            }
                        }
                    }
                }
            }
        """

        data = await self._graphql(query, variables)
        edges = (((data.get("nearest") or {}).get("edges")) or [])

        places: List[NearestPlace] = []
        for edge in edges:
            node = edge.get("node") if edge else None
            if not node:
                continue
            place_payload = node.get("place") or {}
            place = self._build_place(place_payload)
            if not place:
                # For quays we fall back to parent stop place if present.
                if place_payload.get("__typename") == "Quay":
                    parent = self._build_place(place_payload.get("stopPlace"))
                    if parent:
                        place = PlaceReference(
                            id=place_payload.get("id"),
                            name=f"{place_payload.get('name') or 'Quay'} (at {parent.name})",
                            latitude=place_payload.get("latitude"),
                            longitude=place_payload.get("longitude"),
                        )
                else:
                    continue
            distance = float(node.get("distance") or 0.0)
            places.append(NearestPlace(place=place, distance_meters=distance))

        return NearestPlacesResult(latitude=latitude, longitude=longitude, places=places)

    async def get_service_alerts(
        self,
        *,
        stop_place_id: Optional[str] = None,
        stop_text: Optional[str] = None,
        severities: Optional[Sequence[str]] = None,
        limit: Optional[int] = 20,
    ) -> ServiceAlertsResult:
        """Fetch active service alerts across the network or for a specific stop place."""

        severity_list = None
        if severities:
            severity_list = [severity.lower() for severity in severities if severity]
            if not severity_list:
                severity_list = None

        if stop_place_id or stop_text:
            resolved = await self._resolve_stop_place(place_id=stop_place_id, text=stop_text)
            query = """
                query StopSituations($id: String!) {
                    stopPlace(id: $id) {
                        situations {
                            situationNumber
                            severity
                            summary { language value }
                            description { language value }
                            advice { language value }
                            validityPeriod { startTime endTime }
                            affects {
                                __typename
                                ... on AffectedLine { line { id name publicCode } }
                                ... on AffectedStopPlace { stopPlace { id name } }
                                ... on AffectedServiceJourney {
                                    serviceJourney { journeyPattern { line { id name publicCode } } }
                                }
                                ... on AffectedStopPlaceOnLine {
                                    line { id name publicCode }
                                    stopPlace { id name }
                                }
                            }
                        }
                    }
                }
            """
            data = await self._graphql(query, {"id": resolved.id})
            situations = (((data.get("stopPlace") or {}).get("situations")) or [])
        else:
            query = """
                query NetworkSituations($severities: [Severity!]) {
                    situations(severities: $severities) {
                        situationNumber
                        severity
                        summary { language value }
                        description { language value }
                        advice { language value }
                        validityPeriod { startTime endTime }
                        affects {
                            __typename
                            ... on AffectedLine { line { id name publicCode } }
                            ... on AffectedStopPlace { stopPlace { id name } }
                            ... on AffectedServiceJourney {
                                serviceJourney { journeyPattern { line { id name publicCode } } }
                            }
                            ... on AffectedStopPlaceOnLine {
                                line { id name publicCode }
                                stopPlace { id name }
                            }
                        }
                    }
                }
            """
            variables = {"severities": severity_list} if severity_list else {}
            data = await self._graphql(query, variables or None)
            situations = data.get("situations") or []

        alerts = [self._build_alert(item) for item in situations if item]
        if limit is not None and limit >= 0:
            alerts = alerts[: max(0, limit)]

        return ServiceAlertsResult(alerts=alerts)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    async def _graphql(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GraphQL request against Entur."""

        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        headers = self._graphql_headers()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.GRAPHQL_URL, json=payload, headers=headers)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise EnturServiceError(f"Entur GraphQL request failed: {exc}") from exc

        data = response.json()
        errors = data.get("errors")
        if errors:
            raise EnturServiceError(errors[0].get("message", "Entur GraphQL returned an error."))

        return data.get("data") or {}

    async def _geocoder(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a request against the Entur geocoder."""

        headers = self._geocoder_headers()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(self.GEOCODER_URL, params=params, headers=headers)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LocationLookupError(f"Entur geocoder request failed: {exc}") from exc

        return response.json()

    async def _first_geocode_feature(self, text: str) -> Optional[Dict[str, Any]]:
        """Return the first geocoder feature for a query limited to transport venues."""

        payload = await self._geocoder({"text": text, "size": 5, "layers": "venue"})
        features = payload.get("features") or []
        if not features:
            payload = await self._geocoder({"text": text, "size": 5})
            features = payload.get("features") or []
        return features[0] if features else None

    async def _resolve_stop_place(
        self,
        *,
        place_id: Optional[str] = None,
        text: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> _ResolvedStop:
        """Resolve inputs into a concrete stop place."""

        candidate_id = place_id.strip() if place_id else None

        if not candidate_id and text:
            feature = await self._first_geocode_feature(text)
            if feature:
                properties = feature.get("properties") or {}
                feature_id = properties.get("id")
                if feature_id and feature_id.startswith("NSR:StopPlace:"):
                    candidate_id = feature_id
                else:
                    coords = feature.get("geometry", {}).get("coordinates")
                    if coords:
                        longitude = coords[0]
                        latitude = coords[1]

        if not candidate_id and latitude is not None and longitude is not None:
            nearest = await self.get_nearest_places(
                latitude=latitude,
                longitude=longitude,
                maximum_distance=500,
                maximum_results=1,
            )
            place = None
            for candidate in nearest.places:
                if candidate.place.id.startswith("NSR:StopPlace:"):
                    place = candidate
                    break
            if place is None:
                place = next(iter(nearest.places), None)
            if place:
                candidate_id = place.place.id

        if candidate_id and candidate_id.startswith("NSR:Quay:"):
            quay_payload = await self._fetch_quay(candidate_id)
            stop = (quay_payload or {}).get("stopPlace") if quay_payload else None
            if stop and stop.get("id"):
                candidate_id = stop["id"]
                latitude = stop.get("latitude") or latitude
                longitude = stop.get("longitude") or longitude

        if not candidate_id:
            raise LocationLookupError("Unable to resolve a stop place from the provided inputs.")

        stop_payload = await self._fetch_stop_place(candidate_id)
        if not stop_payload:
            raise LocationLookupError(f"Stop place '{candidate_id}' does not exist in Entur.")

        return _ResolvedStop(
            id=stop_payload["id"],
            name=stop_payload.get("name") or candidate_id,
            latitude=stop_payload.get("latitude"),
            longitude=stop_payload.get("longitude"),
        )

    async def _fetch_stop_place(self, place_id: str) -> Optional[Dict[str, Any]]:
        """Fetch stop place details by id."""

        query = """
            query StopPlaceDetails($id: String!) {
                stopPlace(id: $id) {
                    id
                    name
                    latitude
                    longitude
                }
            }
        """
        data = await self._graphql(query, {"id": place_id})
        return data.get("stopPlace")

    async def _fetch_quay(self, quay_id: str) -> Optional[Dict[str, Any]]:
        """Fetch quay details, including parent stop place."""

        query = """
            query QuayDetails($id: String!) {
                quay(id: $id) {
                    id
                    name
                    latitude
                    longitude
                    stopPlace { id name latitude longitude }
                }
            }
        """
        data = await self._graphql(query, {"id": quay_id})
        return data.get("quay")

    def _graphql_headers(self) -> Dict[str, str]:
        headers = {
            "ET-Client-Name": self.client_name,
            "Accept": "application/json",
        }
        if self.client_id:
            headers["ET-Client-ID"] = self.client_id
        if self.user_agent:
            headers["User-Agent"] = self.user_agent
        return headers

    def _geocoder_headers(self) -> Dict[str, str]:
        headers = {
            "ET-Client-Name": self.client_name,
            "Accept": "application/json",
        }
        if self.user_agent:
            headers["User-Agent"] = self.user_agent
        return headers

    def _build_trip_legs(self, legs: Iterable[Dict[str, Any]]) -> List[TripLeg]:
        """Convert raw leg payloads into TripLeg models."""

        result: List[TripLeg] = []
        for leg in legs:
            if not leg:
                continue
            line = leg.get("line") or {}
            result.append(
                TripLeg(
                    mode=leg.get("mode") or "unknown",
                    transport_submode=leg.get("transportSubmode"),
                    distance_meters=float(leg.get("distance") or 0.0),
                    duration_seconds=float(leg.get("duration") or 0.0),
                    aimed_start_time=_parse_datetime(leg.get("aimedStartTime")),
                    expected_start_time=_parse_datetime(leg.get("expectedStartTime")),
                    aimed_end_time=_parse_datetime(leg.get("aimedEndTime")),
                    expected_end_time=_parse_datetime(leg.get("expectedEndTime")),
                    realtime=bool(leg.get("realtime")) if leg.get("realtime") is not None else None,
                    line_id=line.get("id"),
                    line_name=line.get("name"),
                    line_public_code=line.get("publicCode"),
                    service_journey_id=((leg.get("serviceJourney") or {}).get("id")),
                    from_place=self._build_place(leg.get("fromPlace")),
                    to_place=self._build_place(leg.get("toPlace")),
                )
            )
        return result

    def _build_place(self, payload: Optional[Dict[str, Any]]) -> Optional[PlaceReference]:
        """Create a PlaceReference from GraphQL fragments."""

        if not payload:
            return None

        quay = payload.get("quay") or {}
        stop_place = quay.get("stopPlace") or {}

        candidate_ids = [
            payload.get("id"),
            payload.get("stopPlaceId"),
            payload.get("quayId"),
            stop_place.get("id"),
            quay.get("id"),
        ]
        place_id = next((value for value in candidate_ids if value), None)
        if not place_id:
            return None

        name_candidates = [
            payload.get("name"),
            payload.get("stopPlaceName"),
            payload.get("quayName"),
            stop_place.get("name"),
            quay.get("name"),
        ]
        name = next((value for value in name_candidates if value), None)
        if not name:
            name = place_id

        latitude = payload.get("latitude")
        longitude = payload.get("longitude")
        if latitude is None or longitude is None:
            latitude = stop_place.get("latitude") if latitude is None else latitude
            longitude = stop_place.get("longitude") if longitude is None else longitude
        if latitude is None or longitude is None:
            latitude = quay.get("latitude") if latitude is None else latitude
            longitude = quay.get("longitude") if longitude is None else longitude

        return PlaceReference(id=place_id, name=name, latitude=latitude, longitude=longitude)

    def _build_departure(self, call: Dict[str, Any]) -> StopDeparture:
        """Convert estimated call payload into StopDeparture model."""

        service_journey = call.get("serviceJourney") or {}
        journey_pattern = (service_journey.get("journeyPattern") or {})
        line = journey_pattern.get("line") or {}
        notices_payload = call.get("notices") or []
        notices = [
            DepartureNotice(public_code=item.get("publicCode"), text=item.get("text", "").strip())
            for item in notices_payload
            if item and item.get("text")
        ]

        return StopDeparture(
            line_id=line.get("id") or "unknown",
            line_name=line.get("name"),
            line_public_code=line.get("publicCode"),
            destination_display=(call.get("destinationDisplay") or {}).get("frontText"),
            quay_id=((call.get("quay") or {}).get("id") or "unknown"),
            quay_name=(call.get("quay") or {}).get("name"),
            aimed_departure_time=_parse_datetime(call.get("aimedDepartureTime")),
            expected_departure_time=_parse_datetime(call.get("expectedDepartureTime")),
            realtime=bool(call.get("realtime")),
            realtime_state=call.get("realtimeState") or "unknown",
            service_journey_id=service_journey.get("id"),
            notices=notices,
        )

    def _build_alert(self, payload: Dict[str, Any]) -> ServiceAlert:
        """Convert situation payload into ServiceAlert model."""

        validity = payload.get("validityPeriod") or {}
        impact = ServiceAlertImpact()

        for affected in payload.get("affects") or []:
            if not affected:
                continue
            typename = affected.get("__typename")
            if typename in {"AffectedLine", "AffectedStopPlaceOnLine"}:
                line = affected.get("line") or {}
                if line.get("id"):
                    impact.line_ids.append(line["id"])
                if line.get("publicCode"):
                    impact.line_public_codes.append(line["publicCode"])
            if typename in {"AffectedStopPlace", "AffectedStopPlaceOnLine"}:
                stop = affected.get("stopPlace") or {}
                if stop.get("id"):
                    impact.stop_place_ids.append(stop["id"])
            if typename == "AffectedServiceJourney":
                service_journey = (affected.get("serviceJourney") or {})
                journey_pattern = (service_journey.get("journeyPattern") or {})
                line = journey_pattern.get("line") or {}
                if line.get("id"):
                    impact.line_ids.append(line["id"])
                if line.get("publicCode"):
                    impact.line_public_codes.append(line["publicCode"])

        # Deduplicate while preserving order
        impact.line_ids = list(dict.fromkeys(impact.line_ids))
        impact.line_public_codes = list(dict.fromkeys(impact.line_public_codes))
        impact.stop_place_ids = list(dict.fromkeys(impact.stop_place_ids))

        return ServiceAlert(
            situation_number=payload.get("situationNumber"),
            severity=payload.get("severity"),
            summary=_select_text(payload.get("summary")),
            description=_select_text(payload.get("description")),
            advice=_select_text(payload.get("advice")),
            validity_start=_parse_datetime(validity.get("startTime")),
            validity_end=_parse_datetime(validity.get("endTime")),
            impact=impact,
        )
