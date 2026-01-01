#!/usr/bin/env python3
"""Weather tool using Open-Meteo API.

CLI: uv run weather "New York"
Tool: Registered as GetWeather for OpenAI function calling
"""

import httpx
from pydantic import BaseModel, Field

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
IP_LOCATION_URL = "http://ip-api.com/json/"

DEFAULT_LOCATION = ("Hoboken", 40.7440, -74.0324)  # name, lat, lon

# WMO Weather interpretation codes
# https://open-meteo.com/en/docs
WEATHER_CODES = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "foggy",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    56: "light freezing drizzle",
    57: "dense freezing drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    66: "light freezing rain",
    67: "heavy freezing rain",
    71: "slight snowfall",
    73: "moderate snowfall",
    75: "heavy snowfall",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}


def _get_location_from_ip() -> tuple[str, float, float]:
    """Get location from IP address. Returns (display_name, lat, lon)."""
    resp = httpx.get(IP_LOCATION_URL, timeout=5)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != "success":
        raise ValueError("IP geolocation failed")

    city = data.get("city", "Unknown")
    region = data.get("regionName", "")
    country = data.get("country", "")
    name_parts = [p for p in [city, region, country] if p]

    return ", ".join(name_parts), data["lat"], data["lon"]


def _geocode(location: str) -> tuple[str, float, float]:
    """Convert location name to coordinates. Returns (display_name, lat, lon)."""
    resp = httpx.get(GEOCODING_URL, params={"name": location, "count": 1})
    resp.raise_for_status()
    data = resp.json()

    if not data.get("results"):
        raise ValueError(f"Location '{location}' not found")

    result = data["results"][0]
    name_parts = [result.get("name", location)]
    if admin1 := result.get("admin1"):
        name_parts.append(admin1)
    if country := result.get("country"):
        name_parts.append(country)

    return ", ".join(name_parts), result["latitude"], result["longitude"]


def _get_weather(lat: float, lon: float) -> dict:
    """Fetch current weather for coordinates."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": [
            "temperature_2m",
            "apparent_temperature",
            "relative_humidity_2m",
            "weather_code",
            "wind_speed_10m",
        ],
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
    }
    resp = httpx.get(WEATHER_URL, params=params)
    resp.raise_for_status()
    return resp.json()


def _resolve_location(location: str | None) -> tuple[str, float, float]:
    """Resolve location to (display_name, lat, lon)."""
    if location:
        return _geocode(location)

    try:
        return _get_location_from_ip()
    except Exception:
        name, lat, lon = DEFAULT_LOCATION
        return f"{name}, NJ, United States", lat, lon


class GetWeather(BaseModel):
    """Get the current weather for a location. If no location is provided, uses your current location."""

    location: str | None = Field(
        default=None, description="City name or location (optional, defaults to current location)"
    )


def get_weather(params: GetWeather) -> str:
    """Fetch real weather data from Open-Meteo API."""
    try:
        display_name, lat, lon = _resolve_location(params.location)
        data = _get_weather(lat, lon)
        current = data["current"]

        temp = round(current["temperature_2m"])
        feels_like = round(current["apparent_temperature"])
        humidity = current["relative_humidity_2m"]
        wind = round(current["wind_speed_10m"])
        code = current["weather_code"]
        condition = WEATHER_CODES.get(code, "unknown conditions")

        response = f"In {display_name}, it's currently {temp}°F with {condition}."
        if abs(feels_like - temp) >= 3:
            response += f" Feels like {feels_like}°F."
        response += f" Humidity is {humidity}% with winds at {wind} mph."

        return response

    except ValueError as e:
        return str(e)
    except httpx.HTTPError as e:
        return f"Weather service error: {e}"


# ─── Dual Mode: CLI + Tool ─────────────────────────────────────────────────

def main() -> None:
    """CLI entry point."""
    from tools.base import run
    run(GetWeather, get_weather)


if __name__ == "__main__":
    main()
else:
    from tools.base import tool
    tool(GetWeather)(get_weather)
