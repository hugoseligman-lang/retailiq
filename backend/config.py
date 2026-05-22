import os
from dotenv import load_dotenv

load_dotenv(override=True)

GOOGLE_VISION_API_KEY = os.environ["GOOGLE_VISION_API_KEY"]
SUPABASE_URL          = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY  = os.environ["SUPABASE_SERVICE_KEY"]

_cam = os.getenv("CAMERA_SOURCE", "0")
CAMERA_SOURCE = int(_cam) if _cam.isdigit() else _cam

CAPTURE_INTERVAL = int(os.getenv("CAPTURE_INTERVAL", "3"))
