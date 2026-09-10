"""Small, provider-isolated adapters. Each returns structured data or an availability note."""
from __future__ import annotations

from datetime import date
from typing import Any
import httpx

from config import settings


def _disabled(provider: str, key: str) -> dict[str, Any]:
    return {"provider": provider, "available": False, "note": f"{key} is not configured."}


def _client() -> httpx.Client:
    return httpx.Client(timeout=float(settings()["timeout"]))


def _iso_date(value: date | str) -> str:
    """Accept either a native date from graph state or an ISO date from another caller."""
    if isinstance(value, str):
        return value
    return value.isoformat()


def amadeus_token() -> str | None:
    cfg = settings()
    if not cfg["amadeus_client_id"] or not cfg["amadeus_client_secret"]:
        return None
    try:
        response = _client().post(
            f'{str(cfg["amadeus_base_url"]).rstrip("/")}/v1/security/oauth2/token',
            data={"grant_type": "client_credentials", "client_id": cfg["amadeus_client_id"], "client_secret": cfg["amadeus_client_secret"]},
        )
        return response.raise_for_status().json().get("access_token")
    except httpx.HTTPError:
        return None


def _amadeus_city_code(city: str, token: str) -> str | None:
    """Resolve a readable city/airport name to an IATA location code."""
    try:
        response = _client().get(
            f'{str(settings()["amadeus_base_url"]).rstrip("/")}/v1/reference-data/locations',
            headers={"Authorization": f"Bearer {token}"},
            params={"keyword": city, "subType": "CITY,AIRPORT", "page[limit]": 1},
        )
        results = response.raise_for_status().json().get("data", [])
        return results[0].get("iataCode") if results else None
    except httpx.HTTPError:
        return None


def flight_offers(origin: str, destination: str, depart: date, returning: date, travelers: int) -> dict[str, Any]:
    token = amadeus_token()
    if not token:
        return _disabled("Amadeus Flight Offers", "AMADEUS_CLIENT_ID / AMADEUS_CLIENT_SECRET")
    origin_code, destination_code = _amadeus_city_code(origin, token), _amadeus_city_code(destination, token)
    if not origin_code or not destination_code:
        return {"provider": "Amadeus Flight Offers", "available": False, "note": "Could not resolve an IATA city/airport code.", "origin": origin, "destination": destination}
    try:
        response = _client().get(
            f'{str(settings()["amadeus_base_url"]).rstrip("/")}/v2/shopping/flight-offers',
            headers={"Authorization": f"Bearer {token}"},
            params={"originLocationCode": origin_code, "destinationLocationCode": destination_code, "departureDate": _iso_date(depart), "returnDate": _iso_date(returning), "adults": travelers, "max": 5, "currencyCode": "USD"},
        )
        return {"provider": "Amadeus Flight Offers", "available": True, "origin_code": origin_code, "destination_code": destination_code, "data": response.raise_for_status().json().get("data", [])}
    except httpx.HTTPError as exc:
        return {"provider": "Amadeus Flight Offers", "available": False, "note": f"Provider response unavailable: {exc}"}


def hotel_offers(city: str, check_in: date, check_out: date, adults: int) -> dict[str, Any]:
    """Get a small live sample. Production apps should add pagination and rate-limit handling."""
    token = amadeus_token()
    if not token:
        return _disabled("Amadeus Hotel Search", "AMADEUS_CLIENT_ID / AMADEUS_CLIENT_SECRET")
    city_code = _amadeus_city_code(city, token)
    if not city_code:
        return {"provider": "Amadeus Hotel Search", "available": False, "note": "Could not resolve the destination IATA city code."}
    headers = {"Authorization": f"Bearer {token}"}
    try:
        hotels = _client().get(f'{str(settings()["amadeus_base_url"]).rstrip("/")}/v1/reference-data/locations/hotels/by-city', headers=headers, params={"cityCode": city_code, "radius": 10, "radiusUnit": "KM", "hotelSource": "ALL"}).raise_for_status().json().get("data", [])[:5]
        ids = ",".join(hotel["hotelId"] for hotel in hotels if hotel.get("hotelId"))
        if not ids:
            return {"provider": "Amadeus Hotel Search", "available": True, "data": [], "note": "No hotels returned for this location."}
        offers = _client().get(f'{str(settings()["amadeus_base_url"]).rstrip("/")}/v3/shopping/hotel-offers', headers=headers, params={"hotelIds": ids, "checkInDate": _iso_date(check_in), "checkOutDate": _iso_date(check_out), "adults": adults, "roomQuantity": 1}).raise_for_status().json().get("data", [])
        return {"provider": "Amadeus Hotel Search", "available": True, "city_code": city_code, "data": offers}
    except httpx.HTTPError as exc:
        return {"provider": "Amadeus Hotel Search", "available": False, "note": f"Provider response unavailable: {exc}"}


def weather(city: str) -> dict[str, Any]:
    key = settings()["openweather_api_key"]
    if not key:
        return _disabled("OpenWeather", "OPENWEATHER_API_KEY")
    try:
        response = _client().get("https://api.openweathermap.org/data/2.5/forecast", params={"q": city, "appid": key, "units": "metric"})
        payload = response.raise_for_status().json()
        return {"provider": "OpenWeather", "available": True, "data": payload.get("list", [])[:12]}
    except httpx.HTTPError as exc:
        return {"provider": "OpenWeather", "available": False, "note": f"Provider response unavailable: {exc}"}


def places(query: str) -> dict[str, Any]:
    key = settings()["google_maps_api_key"]
    if not key:
        return _disabled("Google Places", "GOOGLE_MAPS_API_KEY")
    try:
        response = _client().get("https://maps.googleapis.com/maps/api/place/textsearch/json", params={"query": query, "key": key})
        return {"provider": "Google Places", "available": True, "data": response.raise_for_status().json().get("results", [])[:10]}
    except httpx.HTTPError as exc:
        return {"provider": "Google Places", "available": False, "note": f"Provider response unavailable: {exc}"}


def exchange_rates(base: str) -> dict[str, Any]:
    key = settings()["exchange_rate_api_key"]
    if not key:
        return _disabled("ExchangeRate-API", "EXCHANGERATE_API_KEY")
    try:
        response = _client().get(f"https://v6.exchangerate-api.com/v6/{key}/latest/{base}")
        return {"provider": "ExchangeRate-API", "available": True, "data": response.raise_for_status().json().get("conversion_rates", {})}
    except httpx.HTTPError as exc:
        return {"provider": "ExchangeRate-API", "available": False, "note": f"Provider response unavailable: {exc}"}
