import base64
import requests
from config import GOOGLE_VISION_API_KEY, QUEUE_THRESHOLD, PASSERBY_EDGE

VISION_URL = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_API_KEY}"


def detect_people(frame_bytes: bytes, weather: dict | None = None) -> dict:
    b64 = base64.b64encode(frame_bytes).decode()
    payload = {"requests": [{"image": {"content": b64},
                              "features": [{"type": "OBJECT_LOCALIZATION", "maxResults": 60}]}]}
    resp = requests.post(VISION_URL, json=payload, timeout=12)
    resp.raise_for_status()

    annotations = resp.json().get("responses", [{}])[0].get("localizedObjectAnnotations", [])
    people = [a for a in annotations if a.get("name", "").lower() == "person"]

    in_store, passersby = [], []
    for p in people:
        verts = p.get("boundingPoly", {}).get("normalizedVertices", [])
        if not verts:
            continue
        xs = [v.get("x", 0.5) for v in verts]
        center_x = sum(xs) / len(xs)
        min_x, max_x = min(xs), max(xs)

        # Passerby: bounding box clips the edge of the frame
        if min_x < PASSERBY_EDGE or max_x > (1 - PASSERBY_EDGE):
            passersby.append(center_x)
        else:
            in_store.append(center_x)

    zone_left = zone_center = zone_right = 0
    for cx in in_store:
        if cx < 0.33:
            zone_left += 1
        elif cx <= 0.67:
            zone_center += 1
        else:
            zone_right += 1

    zones = {"left": zone_left, "center": zone_center, "right": zone_right}
    busiest_zone = max(zones, key=zones.get) if any(zones.values()) else "none"

    # Queue: people in a single zone above threshold counts as a queue
    queue_length = max(
        max(zone_left  - (QUEUE_THRESHOLD - 1), 0),
        max(zone_right - (QUEUE_THRESHOLD - 1), 0),
    )

    result = {
        "people_count":   len(in_store),
        "passerby_count": len(passersby),
        "zone_left":      zone_left,
        "zone_center":    zone_center,
        "zone_right":     zone_right,
        "queue_length":   queue_length,
        "busiest_zone":   busiest_zone,
    }
    if weather:
        result["weather_temp"] = weather.get("temperature")
        result["weather_code"] = weather.get("code")
    return result
