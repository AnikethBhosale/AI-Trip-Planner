"""Low-cost travel-data adapters with explicit fallback and attribution-friendly results."""
from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from config import settings

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OSRM_URL = "https://router.project-osrm.org"
TAVILY_URL = "https://api.tavily.com/search"


def _disabled(provider: str, key: str) -> dict[str, Any]:
    return {"provider": provider, "available": False, "note": f"{key} is not configured."}


def _client() -> httpx.Client:
    return httpx.Client(
        timeout=float(settings()["timeout"]),
        headers={"User-Agent": str(settings()["osm_user_agent"]), "Accept": "application/json"},
    )


def _iso_date(value: date | str) -> str:
    return value if isinstance(value, str) else value.isoformat()


def tavily_search(query: str, max_results: int = 5) -> dict[str, Any]:
    """Current web research for flights, stays, closures, and travel advisories."""
    key = settings()["tavily_api_key"]
    if not key:
        return _disabled("Tavily web research", "TAVILY_API_KEY")
    try:
        response = _client().post(
            TAVILY_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={"query": query, "search_depth": "basic", "max_results": max_results, "include_answer": False},
        )
        payload = response.raise_for_status().json()
        results = [
            {"title": item.get("title"), "url": item.get("url"), "snippet": item.get("content")}
            for item in payload.get("results", [])
        ]
        return {"provider": "Tavily", "available": True, "query": query, "sources": results}
    except httpx.HTTPError as exc:
        return {"provider": "Tavily", "available": False, "note": f"Research request unavailable: {exc}"}


def flight_research(origin: str, destination: str, depart: date | str, returning: date | str, travelers: int) -> dict[str, Any]:
    return tavily_search(
        f"flight options {origin} to {destination} departing {_iso_date(depart)} returning {_iso_date(returning)} for {travelers} travellers official airline or reputable travel source"
    )


def hotel_research(city: str, check_in: date | str, check_out: date | str, travelers: int) -> dict[str, Any]:
    return tavily_search(
        f"best areas and accommodation options in {city} for {travelers} travellers {_iso_date(check_in)} to {_iso_date(check_out)} reputable travel source"
    )


def geocode_city(city: str) -> dict[str, Any]:
    try:
        response = _client().get(NOMINATIM_URL, params={"q": city, "format": "jsonv2", "limit": 1})
        item = response.raise_for_status().json()
        if not item:
            return {"provider": "OpenStreetMap Nominatim", "available": False, "note": "Location was not found."}
        return {"provider": "OpenStreetMap Nominatim", "available": True, "lat": float(item[0]["lat"]), "lon": float(item[0]["lon"]), "display_name": item[0].get("display_name")}
    except httpx.HTTPError as exc:
        return {"provider": "OpenStreetMap Nominatim", "available": False, "note": f"Geocoding unavailable: {exc}"}


def places(city: str, interests: list[str]) -> dict[str, Any]:
    """Find nearby attractions and food venues from OpenStreetMap without a maps key."""
    location = geocode_city(city)
    if not location.get("available"):
        return location
    lat, lon = location["lat"], location["lon"]
    query = f"""[out:json][timeout:20];
    (nwr(around:6000,{lat},{lon})[tourism];
     nwr(around:6000,{lat},{lon})[historic];
     nwr(around:6000,{lat},{lon})[leisure];
     nwr(around:6000,{lat},{lon})[amenity~\"restaurant|cafe\"]);
    out center tags 30;"""
    try:
        response = _client().post(OVERPASS_URL, data={"data": query})
        elements = response.raise_for_status().json().get("elements", [])
        candidates = []
        for item in elements:
            tags = item.get("tags", {})
            name = tags.get("name")
            item_lat = item.get("lat", item.get("center", {}).get("lat"))
            item_lon = item.get("lon", item.get("center", {}).get("lon"))
            if name and item_lat is not None and item_lon is not None:
                candidates.append({"name": name, "category": tags.get("tourism") or tags.get("historic") or tags.get("leisure") or tags.get("amenity"), "lat": item_lat, "lon": item_lon, "tags": {key: tags[key] for key in ("cuisine", "opening_hours", "website") if key in tags}})
        return {"provider": "OpenStreetMap / Overpass", "available": True, "location": location, "interests": interests, "data": candidates[:20], "attribution": "© OpenStreetMap contributors"}
    except httpx.HTTPError as exc:
        return {"provider": "OpenStreetMap / Overpass", "available": False, "note": f"Places request unavailable: {exc}"}


def route_estimate(place_data: dict[str, Any]) -> dict[str, Any]:
    """A small OSRM sample to inform the route agent; never presented as guaranteed transit time."""
    candidates = place_data.get("data", [])[:4]
    if len(candidates) < 2:
        return {"provider": "OSRM", "available": False, "note": "Not enough mapped places for a route sample."}
    coordinates = ";".join(f"{item['lon']},{item['lat']}" for item in candidates)
    try:
        response = _client().get(f"{OSRM_URL}/route/v1/driving/{coordinates}", params={"overview": "false", "steps": "false"})
        route = response.raise_for_status().json().get("routes", [{}])[0]
        return {"provider": "OSRM", "available": True, "sample_places": [item["name"] for item in candidates], "distance_km": round(route.get("distance", 0) / 1000, 1), "duration_minutes": round(route.get("duration", 0) / 60)}
    except (httpx.HTTPError, IndexError) as exc:
        return {"provider": "OSRM", "available": False, "note": f"Route sample unavailable: {exc}"}


def weather(city: str) -> dict[str, Any]:
    key = settings()["openweather_api_key"]
    if not key:
        return _disabled("OpenWeather", "OPENWEATHER_API_KEY")
    try:
        response = _client().get("https://api.openweathermap.org/data/2.5/forecast", params={"q": city, "appid": key, "units": "metric"})
        payload = response.raise_for_status().json()
        return {"provider": "OpenWeather", "available": True, "data": payload.get("list", [])[:12]}
    except httpx.HTTPError as exc:
        return {"provider": "OpenWeather", "available": False, "note": f"Weather request unavailable: {exc}"}


def exchange_rates(base: str) -> dict[str, Any]:
    key = settings()["exchange_rate_api_key"]
    if not key:
        return _disabled("ExchangeRate-API", "EXCHANGERATE_API_KEY")
    try:
        response = _client().get(f"https://v6.exchangerate-api.com/v6/{key}/latest/{base}")
        return {"provider": "ExchangeRate-API", "available": True, "data": response.raise_for_status().json().get("conversion_rates", {})}
    except httpx.HTTPError as exc:
        return {"provider": "ExchangeRate-API", "available": False, "note": f"Currency request unavailable: {exc}"}
