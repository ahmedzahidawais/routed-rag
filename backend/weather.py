from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple
import requests

from .logger import setup_logger
from config import OPENWEATHERMAP_API_KEY


logger = setup_logger(__name__)


@dataclass
class WeatherData:
    city: str
    country: Optional[str]
    lat: float
    lon: float
    temp_c: float
    conditions: str
    humidity: int
    wind_speed_ms: float


class WeatherClient:
    def __init__(self) -> None:
        self.api_key = OPENWEATHERMAP_API_KEY

    def _require_key(self) -> None:
        if not self.api_key:
            raise RuntimeError("OPENWEATHERMAP_API_KEY is not set")

    def _extract_city(self, query: str) -> Optional[str]:
        text = query.lower()
        for marker in [" in ", " at ", " for "]:
            if marker in text:
                candidate = query[text.index(marker) + len(marker):].strip().strip("?!. ,")
                return candidate
        return query.strip().strip("?!. ,") or None

    def _geocode(self, place: str) -> Tuple[float, float, str, Optional[str]]:
        self._require_key()
        url = "https://api.openweathermap.org/geo/1.0/direct"
        params = {"q": place, "limit": 1, "appid": self.api_key}
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        if not data:
            raise ValueError(f"No geocoding results for '{place}'")
        item = data[0]
        return float(item["lat"]), float(item["lon"]), item.get("name", place), item.get("country")

    def _current_weather(self, lat: float, lon: float) -> Dict[str, Any]:
        self._require_key()
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {"lat": lat, "lon": lon, "units": "metric", "appid": self.api_key}
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        return r.json()

    async def get_weather_answer(self, query: str) -> Tuple[str, Dict[str, str]]:
        loop = asyncio.get_event_loop()
        city = self._extract_city(query) or ""
        lat, lon, name, country = await loop.run_in_executor(None, self._geocode, city)
        current = await loop.run_in_executor(None, self._current_weather, lat, lon)

        temp = current.get("main", {}).get("temp")
        humidity = current.get("main", {}).get("humidity")
        wind = current.get("wind", {}).get("speed")
        cond_list = current.get("weather", [])
        condition = cond_list[0].get("description", "") if cond_list else ""

        answer = (
            f"Aktuelles Wetter in {name}{', ' + country if country else ''}: "
            f"{condition}, {temp:.1f}°C, Luftfeuchtigkeit {humidity}%, Wind {wind:.1f} m/s."
        )

        citations = {
            "1": f"OpenWeatherMap Current Weather API for lat={lat}, lon={lon}",
            "2": "OpenWeatherMap Geocoding API"
        }
        return answer, citations

    async def get_weather_for_city(self, place: str) -> str:
        """Get a concise weather line for a specific place name."""
        loop = asyncio.get_event_loop()
        lat, lon, name, country = await loop.run_in_executor(None, self._geocode, place)
        current = await loop.run_in_executor(None, self._current_weather, lat, lon)

        temp = current.get("main", {}).get("temp")
        humidity = current.get("main", {}).get("humidity")
        wind = current.get("wind", {}).get("speed")
        cond_list = current.get("weather", [])
        condition = cond_list[0].get("description", "") if cond_list else ""

        return (
            f"{name}{', ' + country if country else ''}: {condition}, {temp:.1f}°C, humidity {humidity}%, wind {wind:.1f} m/s"
        )


