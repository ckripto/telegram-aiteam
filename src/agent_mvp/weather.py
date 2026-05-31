from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class WeatherForecast:
    location_name: str
    current_temperature: float | None
    current_wind_speed: float | None
    daily_min: float | None
    daily_max: float | None
    precipitation_probability: int | None
    summary: str


class WeatherService:
    """Small Open-Meteo client. It does not require an API key."""

    def forecast(self, location: str) -> WeatherForecast:
        place = self._geocode(location)
        latitude = place["latitude"]
        longitude = place["longitude"]
        display_name = self._display_name(place)

        params = urllib.parse.urlencode(
            {
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,wind_speed_10m",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "forecast_days": 1,
                "timezone": "auto",
            }
        )
        with urllib.request.urlopen(f"https://api.open-meteo.com/v1/forecast?{params}", timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))

        current = data.get("current", {})
        daily = data.get("daily", {})
        daily_max = self._first(daily.get("temperature_2m_max"))
        daily_min = self._first(daily.get("temperature_2m_min"))
        precipitation = self._first(daily.get("precipitation_probability_max"))
        current_temp = current.get("temperature_2m")
        wind_speed = current.get("wind_speed_10m")

        summary = (
            f"Сейчас {current_temp}°C, ветер {wind_speed} км/ч. "
            f"Сегодня ожидается от {daily_min}°C до {daily_max}°C, "
            f"вероятность осадков до {precipitation}%."
        )
        return WeatherForecast(
            location_name=display_name,
            current_temperature=current_temp,
            current_wind_speed=wind_speed,
            daily_min=daily_min,
            daily_max=daily_max,
            precipitation_probability=precipitation,
            summary=summary,
        )

    def _geocode(self, location: str) -> dict:
        params = urllib.parse.urlencode(
            {
                "name": location,
                "count": 1,
                "language": "ru",
                "format": "json",
            }
        )
        with urllib.request.urlopen(f"https://geocoding-api.open-meteo.com/v1/search?{params}", timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))

        results = data.get("results") or []
        if not results:
            raise ValueError(f"Не нашёл город или место: {location}")
        return results[0]

    def _display_name(self, place: dict) -> str:
        parts = [
            place.get("name"),
            place.get("admin1"),
            place.get("country"),
        ]
        return ", ".join(part for part in parts if part)

    def _first(self, value: list | None) -> float | int | None:
        if not value:
            return None
        return value[0]

