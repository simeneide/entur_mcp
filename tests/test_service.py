"""Unit tests for the Entur service layer."""

from __future__ import annotations

import asyncio
import httpx
import pytest
import respx

from entur_mcp.service import EnturService, LocationLookupError, TripPlanningError


@respx.mock
def test_plan_trip_parses_itinerary() -> None:
    """Entur trip planning should return structured itineraries."""

    service = EnturService()

    route = respx.post(EnturService.GRAPHQL_URL)
    route.mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "data": {
                        "stopPlace": {
                            "id": "NSR:StopPlace:1",
                            "name": "Origin stop",
                            "latitude": 59.91,
                            "longitude": 10.75,
                        }
                    }
                },
            ),
            httpx.Response(
                200,
                json={
                    "data": {
                        "stopPlace": {
                            "id": "NSR:StopPlace:2",
                            "name": "Destination stop",
                            "latitude": 59.74,
                            "longitude": 10.21,
                        }
                    }
                },
            ),
            httpx.Response(
                200,
                json={
                    "data": {
                        "trip": {
                            "metadata": {"searchWindowUsed": 45},
                            "fromPlace": {
                                "name": "Origin station",
                                "latitude": 59.91,
                                "longitude": 10.75,
                                "vertexType": "transit",
                                "quay": {
                                    "id": "NSR:Quay:1",
                                    "name": "Track 1",
                                    "latitude": 59.91,
                                    "longitude": 10.75,
                                    "stopPlace": {
                                        "id": "NSR:StopPlace:1",
                                        "name": "Origin stop",
                                        "latitude": 59.91,
                                        "longitude": 10.75,
                                    },
                                },
                            },
                            "toPlace": {
                                "name": "Destination station",
                                "latitude": 59.74,
                                "longitude": 10.21,
                                "vertexType": "transit",
                                "quay": {
                                    "id": "NSR:Quay:2",
                                    "name": "Platform",
                                    "latitude": 59.74,
                                    "longitude": 10.21,
                                    "stopPlace": {
                                        "id": "NSR:StopPlace:2",
                                        "name": "Destination stop",
                                        "latitude": 59.74,
                                        "longitude": 10.21,
                                    },
                                },
                            },
                            "tripPatterns": [
                                {
                                    "startTime": "2024-07-01T08:00:00+02:00",
                                    "endTime": "2024-07-01T08:45:00+02:00",
                                    "duration": 2700,
                                    "legs": [
                                        {
                                            "mode": "rail",
                                            "transportSubmode": "local",
                                            "distance": 38925.0,
                                            "duration": 2700,
                                            "aimedStartTime": "2024-07-01T08:00:00+02:00",
                                            "expectedStartTime": "2024-07-01T08:00:00+02:00",
                                            "aimedEndTime": "2024-07-01T08:45:00+02:00",
                                            "expectedEndTime": "2024-07-01T08:45:00+02:00",
                                            "realtime": True,
                                            "fromPlace": {
                                                "name": "Origin station",
                                                "latitude": 59.91,
                                                "longitude": 10.75,
                                                "vertexType": "transit",
                                                "quay": {
                                                    "id": "NSR:Quay:1",
                                                    "name": "Track 1",
                                                    "latitude": 59.91,
                                                    "longitude": 10.75,
                                                    "stopPlace": {
                                                        "id": "NSR:StopPlace:1",
                                                        "name": "Origin stop",
                                                        "latitude": 59.91,
                                                        "longitude": 10.75,
                                                    },
                                                },
                                            },
                                            "toPlace": {
                                                "name": "Destination station",
                                                "latitude": 59.74,
                                                "longitude": 10.21,
                                                "vertexType": "transit",
                                                "quay": {
                                                    "id": "NSR:Quay:2",
                                                    "name": "Platform",
                                                    "latitude": 59.74,
                                                    "longitude": 10.21,
                                                    "stopPlace": {
                                                        "id": "NSR:StopPlace:2",
                                                        "name": "Destination stop",
                                                        "latitude": 59.74,
                                                        "longitude": 10.21,
                                                    },
                                                },
                                            },
                                            "line": {
                                                "id": "VYG:Line:R12",
                                                "name": "Kongsberg-Oslo S",
                                                "publicCode": "R12",
                                                "transportMode": "rail",
                                                "transportSubmode": "local",
                                            },
                                            "serviceJourney": {"id": "VYG:SJ:1"},
                                        }
                                    ],
                                }
                            ],
                            "nextPageCursor": "cursor-next",
                            "previousPageCursor": None,
                        }
                    }
                },
            ),
        ]
    )

    result = asyncio.run(
        service.plan_trip(
            from_place_id="NSR:StopPlace:1",
            to_place_id="NSR:StopPlace:2",
            num_trip_patterns=1,
        )
    )

    assert result.from_place.id == "NSR:StopPlace:1"
    assert result.to_place.name == "Destination station"
    assert result.search_window_minutes == 45
    assert result.next_page_cursor == "cursor-next"
    assert len(result.itineraries) == 1
    leg = result.itineraries[0].legs[0]
    assert leg.mode == "rail"
    assert leg.line_public_code == "R12"
    assert leg.service_journey_id == "VYG:SJ:1"


@respx.mock
def test_plan_trip_without_results_raises() -> None:
    """Missing itineraries should surface as a TripPlanningError."""

    service = EnturService()

    respx.post(EnturService.GRAPHQL_URL).mock(
        side_effect=[
            httpx.Response(200, json={"data": {"stopPlace": {"id": "NSR:StopPlace:1", "name": "Origin"}}}),
            httpx.Response(200, json={"data": {"stopPlace": {"id": "NSR:StopPlace:2", "name": "Destination"}}}),
            httpx.Response(200, json={"data": {"trip": None}}),
        ]
    )

    with pytest.raises(TripPlanningError):
        asyncio.run(
            service.plan_trip(
                from_place_id="NSR:StopPlace:1",
                to_place_id="NSR:StopPlace:2",
            )
        )


@respx.mock
def test_get_stop_departures_returns_realtime_data() -> None:
    """Stop departures should expose realtime state and notices."""

    service = EnturService()

    respx.post(EnturService.GRAPHQL_URL).mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "data": {
                        "stopPlace": {
                            "id": "NSR:StopPlace:58404",
                            "name": "Nationaltheatret",
                            "latitude": 59.91,
                            "longitude": 10.73,
                        }
                    }
                },
            ),
            httpx.Response(
                200,
                json={
                    "data": {
                        "stopPlace": {
                            "id": "NSR:StopPlace:58404",
                            "name": "Nationaltheatret",
                            "latitude": 59.91,
                            "longitude": 10.73,
                            "estimatedCalls": [
                                {
                                    "realtime": True,
                                    "realtimeState": "updated",
                                    "aimedDepartureTime": "2024-07-01T21:10:00+02:00",
                                    "expectedDepartureTime": "2024-07-01T21:12:50+02:00",
                                    "destinationDisplay": {"frontText": "Drammen"},
                                    "quay": {"id": "NSR:Quay:7349", "name": "Platform A"},
                                    "serviceJourney": {
                                        "id": "RUT:SJ:37",
                                        "journeyPattern": {
                                            "line": {
                                                "id": "RUT:Line:37",
                                                "name": "Line 37",
                                                "publicCode": "37",
                                                "transportMode": "bus",
                                                "transportSubmode": "localBus",
                                            }
                                        },
                                    },
                                    "notices": [
                                        {"publicCode": "INFO", "text": "Limited capacity"}
                                    ],
                                }
                            ],
                        }
                    }
                },
            ),
        ]
    )

    result = asyncio.run(
        service.get_stop_departures(
            stop_place_id="NSR:StopPlace:58404",
            number_of_departures=1,
        )
    )

    assert result.stop_place.id == "NSR:StopPlace:58404"
    assert len(result.departures) == 1
    departure = result.departures[0]
    assert departure.line_id == "RUT:Line:37"
    assert departure.destination_display == "Drammen"
    assert departure.realtime_state == "updated"
    assert departure.notices[0].text == "Limited capacity"


@respx.mock
def test_get_nearest_places_handles_quays() -> None:
    """Nearest places should merge quay and stop place information."""

    service = EnturService()

    respx.post(EnturService.GRAPHQL_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "nearest": {
                        "edges": [
                            {
                                "node": {
                                    "distance": 120.5,
                                    "place": {
                                        "__typename": "Quay",
                                        "quayId": "NSR:Quay:60954",
                                        "quayName": "Sogndal skysstasjon",
                                        "latitude": 61.229,
                                        "longitude": 7.096,
                                        "stopPlace": {
                                            "id": "NSR:StopPlace:35169",
                                            "name": "Sogndal skysstasjon",
                                            "latitude": 61.229,
                                            "longitude": 7.096,
                                        },
                                    },
                                }
                            },
                            {
                                "node": {
                                    "distance": 220.0,
                                    "place": {
                                        "__typename": "StopPlace",
                                        "stopPlaceId": "NSR:StopPlace:35169",
                                        "stopPlaceName": "Sogndal skysstasjon",
                                        "latitude": 61.229,
                                        "longitude": 7.096,
                                    },
                                }
                            },
                        ]
                    }
                }
            },
        )
    )

    result = asyncio.run(
        service.get_nearest_places(
            latitude=61.229,
            longitude=7.096,
            maximum_results=2,
        )
    )

    assert len(result.places) == 2
    first = result.places[0]
    assert first.place.id == "NSR:Quay:60954"
    assert first.place.name.startswith("Sogndal")
    assert first.distance_meters == pytest.approx(120.5)


@respx.mock
def test_get_service_alerts_aggregates_impacts() -> None:
    """Service alerts should aggregate affected lines and stops."""

    service = EnturService()

    respx.post(EnturService.GRAPHQL_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "situations": [
                        {
                            "situationNumber": "ENT:1",
                            "severity": "severe",
                            "summary": [{"language": "nb", "value": "Innstilt"}],
                            "description": [{"language": "nb", "value": "Stengt strekning"}],
                            "advice": [{"language": "nb", "value": "Bruk alternativ transport"}],
                            "validityPeriod": {
                                "startTime": "2024-07-01T08:00:00+02:00",
                                "endTime": "2024-07-01T10:00:00+02:00",
                            },
                            "affects": [
                                {
                                    "__typename": "AffectedLine",
                                    "line": {"id": "RUT:Line:37", "name": "Line 37", "publicCode": "37"},
                                },
                                {
                                    "__typename": "AffectedServiceJourney",
                                    "serviceJourney": {
                                        "journeyPattern": {
                                            "line": {
                                                "id": "VYG:Line:R12",
                                                "name": "R12",
                                                "publicCode": "R12",
                                            }
                                        }
                                    },
                                },
                                {
                                    "__typename": "AffectedStopPlaceOnLine",
                                    "line": {"id": "VYG:Line:R12", "name": "R12", "publicCode": "R12"},
                                    "stopPlace": {"id": "NSR:StopPlace:58404", "name": "Nationaltheatret"},
                                },
                            ],
                        }
                    ]
                }
            },
        )
    )

    result = asyncio.run(service.get_service_alerts(severities=["severe"], limit=5))

    assert len(result.alerts) == 1
    alert = result.alerts[0]
    assert alert.severity == "severe"
    assert alert.summary == "Innstilt"
    assert set(alert.impact.line_ids) == {"RUT:Line:37", "VYG:Line:R12"}
    assert alert.impact.stop_place_ids == ["NSR:StopPlace:58404"]


@respx.mock
def test_resolve_stop_place_missing_id_raises() -> None:
    """Unknown stop place ids should raise a helpful error."""

    service = EnturService()

    respx.post(EnturService.GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json={"data": {"stopPlace": None}})
    )

    with pytest.raises(LocationLookupError):
        asyncio.run(
            service.get_stop_departures(
                stop_place_id="NSR:StopPlace:unknown",
            )
        )
