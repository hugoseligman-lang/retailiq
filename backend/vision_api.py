import base64
import requests
from config import GOOGLE_VISION_API_KEY

VISION_URL = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_API_KEY}"


def detect_people(frame_bytes: bytes) -> dict:
    """
    Sends a JPEG frame to Google Cloud Vision API.
    Returns people_count and zone breakdown (left/center/right thirds of frame).
    """
    b64 = base64.b64encode(frame_bytes).decode("utf-8")

    payload = {
        "requests": [
            {
                "image": {"content": b64},
                "features": [{"type": "OBJECT_LOCALIZATION", "maxResults": 50}],
            }
        ]
    }

    resp = requests.post(VISION_URL, json=payload, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    annotations = (
        data.get("responses", [{}])[0].get("localizedObjectAnnotations", [])
    )

    people = [a for a in annotations if a.get("name", "").lower() == "person"]

    zone_left = zone_center = zone_right = 0

    for person in people:
        verts = person.get("boundingPoly", {}).get("normalizedVertices", [])
        if not verts:
            continue
        xs = [v.get("x", 0) for v in verts]
        center_x = sum(xs) / len(xs)

        if center_x < 0.33:
            zone_left += 1
        elif center_x <= 0.67:
            zone_center += 1
        else:
            zone_right += 1

    return {
        "people_count": len(people),
        "zone_left": zone_left,
        "zone_center": zone_center,
        "zone_right": zone_right,
    }
