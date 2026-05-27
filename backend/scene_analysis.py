"""
scene_analysis.py — Claude Vision API calls for zone detection and
multi-camera spatial cross-referencing.
"""

import json
import anthropic
from config import ANTHROPIC_API_KEY

VISION_MODEL = "claude-sonnet-4-20250514"

SCENE_PROMPT = """Analyse this retail/café space camera frame and identify the following.
Return your response as JSON only — no markdown, no explanation, no code fences.

{
  "entrance_zone": { "x1": 0.0, "y1": 0.0, "x2": 100.0, "y2": 100.0, "confidence": 0.0, "description": "" },
  "counter_queue_zone": { "x1": 0.0, "y1": 0.0, "x2": 100.0, "y2": 100.0, "confidence": 0.0, "description": "" },
  "seating_zones": [{ "x1": 0.0, "y1": 0.0, "x2": 100.0, "y2": 100.0, "label": "", "confidence": 0.0 }],
  "camera_height_estimate": "floor_level",
  "camera_angle_estimate": "eye_level",
  "entrance_line": { "x1": 0.0, "y1": 0.0, "x2": 100.0, "y2": 100.0, "entry_direction": "left_to_right" },
  "recommended_counting_line": { "x1": 0.0, "y1": 0.0, "x2": 100.0, "y2": 100.0 },
  "lighting_quality": "adequate",
  "occlusion_issues": [],
  "suggested_zones": [{ "x1": 0.0, "y1": 0.0, "x2": 100.0, "y2": 100.0, "label": "", "zone_type": "" }]
}

Rules:
- All coordinates are PERCENTAGES 0–100 of frame width/height. (0,0) = top-left.
- x1,y1 = top-left corner of zone; x2,y2 = bottom-right corner.
- camera_height_estimate: "floor_level" | "mid_height" | "overhead"
- camera_angle_estimate: "eye_level" | "45_degree" | "overhead"
- entry_direction: "left_to_right" | "right_to_left" | "bottom_to_top" | "top_to_bottom"
- lighting_quality: "poor" | "adequate" | "good"
- confidence: 0.0–1.0
- If a zone cannot be confidently identified, set confidence to 0.0 and use full-frame coords.
- occlusion_issues: list any visual problems (shelves blocking view, glare, etc.)
- suggested_zones: up to 4 named zones relevant to the specific space type."""

MULTI_CAMERA_PROMPT = """Two camera frames from the same retail space are attached (first image = Camera 1, second = Camera 2).
Identify any spatial overlap — look for shared furniture, walls, doorways, or fixtures visible in both.
Return JSON only — no markdown, no explanation:

{
  "overlap_detected": false,
  "overlap_confidence": 0.0,
  "shared_landmarks": [
    { "description": "", "camera1_coords": {"x": 50.0, "y": 50.0}, "camera2_coords": {"x": 50.0, "y": 50.0} }
  ],
  "spatial_relationship": "",
  "camera1_coverage": "",
  "camera2_coverage": "",
  "handoff_zone_camera1": { "x1": 0.0, "y1": 0.0, "x2": 100.0, "y2": 100.0 },
  "handoff_zone_camera2": { "x1": 0.0, "y1": 0.0, "x2": 100.0, "y2": 100.0 }
}

Coordinates are percentages of each respective frame."""


def _extract_json(text: str) -> dict:
    """Parse JSON from Claude response, stripping any markdown fences."""
    text = text.strip()
    if "```" in text:
        for part in text.split("```"):
            part = part.strip().lstrip("json").strip()
            try:
                return json.loads(part)
            except Exception:
                continue
    return json.loads(text)


def analyse_scene(frame_b64: str) -> dict:
    """
    Send a base64 JPEG frame to Claude Vision and return zone analysis JSON.
    Returns dict with zone data, or {"error": msg} on failure.
    """
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model=VISION_MODEL,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": frame_b64},
                    },
                    {"type": "text", "text": SCENE_PROMPT},
                ],
            }],
        )
        return _extract_json(resp.content[0].text)
    except json.JSONDecodeError as e:
        raw = locals().get("resp", {})
        return {"error": f"JSON parse failed: {e}"}
    except Exception as e:
        return {"error": str(e)}


def cross_reference(frame1_b64: str, frame2_b64: str) -> dict:
    """
    Send two frames to Claude Vision to detect spatial overlap.
    Returns dict with overlap data, or {"error": msg} on failure.
    """
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model=VISION_MODEL,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": frame1_b64}},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": frame2_b64}},
                    {"type": "text", "text": MULTI_CAMERA_PROMPT},
                ],
            }],
        )
        return _extract_json(resp.content[0].text)
    except Exception as e:
        return {"error": str(e)}
