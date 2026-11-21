"""
Start from right now (frankenstein spec 14, requirement 6.7): the person's time of day and weather (Open-Meteo,
free, no key, CC BY 4.0) as feeling words. "It's 2 at night, raining and cold" is a song direction a non-musician
recognises at once. Only the coarse location the browser shares is used, and it is not stored.
"""
from __future__ import annotations

from typing import Optional

import httpx

URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather codes (Open-Meteo docs) to plain words.
WEATHER = {
    0: "clear", 1: "mostly clear", 2: "a little cloudy", 3: "grey and overcast", 45: "foggy", 48: "foggy",
    51: "drizzling", 53: "drizzling", 55: "drizzling", 61: "raining softly", 63: "raining", 65: "pouring",
    66: "freezing rain", 67: "freezing rain", 71: "snowing lightly", 73: "snowing", 75: "snowing hard",
    77: "snowing", 80: "showery", 81: "showery", 82: "storming with rain", 85: "snow showers", 86: "snow showers",
    95: "thundering", 96: "thundering", 99: "thundering",
}


def time_words(hour: int) -> str:
    if hour < 4 or hour >= 23:
        return "the middle of the night"
    if hour < 7:
        return "just before dawn"
    if hour < 11:
        return "morning"
    if hour < 14:
        return "the middle of the day"
    if hour < 18:
        return "afternoon"
    if hour < 21:
        return "evening"
    return "late at night"


def temp_words(c: Optional[float]) -> Optional[str]:
    if c is None:
        return None
    return "freezing" if c < 2 else "cold" if c < 10 else "mild" if c < 20 else "warm" if c < 28 else "hot"


def describe(hour: int, code: Optional[int], temp_c: Optional[float], is_day: Optional[bool]) -> str:
    bits = [f"It's {time_words(hour)}"]
    w = WEATHER.get(code) if code is not None else None
    t = temp_words(temp_c)
    tail = [x for x in (w, t) if x]
    if tail:
        bits.append(", " + " and ".join(tail))
    return "".join(bits) + " where I am right now, and the song should feel like this moment."


def hints(hour: int, code: Optional[int]) -> dict:
    """Coarse, confident hints only: night is darker and slower to feel; storms and pouring rain have energy."""
    out: dict = {}
    if hour < 5 or hour >= 22:
        out["brightness"] = 0.25
    elif 10 <= hour < 17 and code in (0, 1):
        out["brightness"] = 0.7
    if code in (82, 95, 96, 99, 65):
        out["energy_level"] = 0.7
    return out


def weather(lat: float, lon: float) -> dict:
    r = httpx.get(URL, params={"latitude": round(lat, 2), "longitude": round(lon, 2),
                               "current": "temperature_2m,weather_code,is_day", "timezone": "auto"}, timeout=10.0)
    r.raise_for_status()
    cur = r.json().get("current") or {}
    return {"code": cur.get("weather_code"), "temp_c": cur.get("temperature_2m"), "is_day": cur.get("is_day"),
            "local_time": cur.get("time")}
