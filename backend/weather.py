import requests
from config import STORE_LAT, STORE_LON, STORE_TIMEZONE

WMO_CONDITIONS = {
    0: ("Clear", "☀️"), 1: ("Mainly Clear", "🌤️"), 2: ("Partly Cloudy", "⛅"),
    3: ("Overcast", "☁️"), 45: ("Fog", "🌫️"), 48: ("Icy Fog", "🌫️"),
    51: ("Light Drizzle", "🌦️"), 53: ("Drizzle", "🌦️"), 55: ("Heavy Drizzle", "🌧️"),
    61: ("Light Rain", "🌧️"), 63: ("Rain", "🌧️"), 65: ("Heavy Rain", "🌧️"),
    71: ("Light Snow", "❄️"), 73: ("Snow", "❄️"), 75: ("Heavy Snow", "❄️"),
    80: ("Rain Showers", "🌦️"), 81: ("Rain Showers", "🌧️"), 82: ("Violent Showers", "⛈️"),
    95: ("Thunderstorm", "⛈️"), 96: ("Thunderstorm+Hail", "⛈️"), 99: ("Heavy Thunderstorm", "⛈️"),
}


def _decode(code: int) -> tuple[str, str]:
    return WMO_CONDITIONS.get(code, ("Unknown", "🌡️"))


def fetch_current() -> dict:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": STORE_LAT,
        "longitude": STORE_LON,
        "current": "temperature_2m,weather_code,wind_speed_10m,precipitation,relative_humidity_2m",
        "timezone": STORE_TIMEZONE,
    }
    try:
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        cur = r.json().get("current", {})
        code = cur.get("weather_code", 0)
        condition, icon = _decode(code)
        return {
            "temperature": cur.get("temperature_2m"),
            "code": code,
            "condition": condition,
            "icon": icon,
            "wind_speed": cur.get("wind_speed_10m"),
            "precipitation": cur.get("precipitation"),
            "humidity": cur.get("relative_humidity_2m"),
        }
    except Exception as e:
        print(f"[weather] fetch error: {e}")
        return {}


def condition_label(code: int) -> str:
    return _decode(code)[0]


def condition_icon(code: int) -> str:
    return _decode(code)[1]
