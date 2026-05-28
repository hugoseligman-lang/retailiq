import os
from dotenv import load_dotenv

load_dotenv(override=True)

STORE_NAME      = os.getenv("STORE_NAME", "My Retail Store")
STORE_LAT       = float(os.getenv("STORE_LAT", "-33.8688"))
STORE_LON       = float(os.getenv("STORE_LON", "151.2093"))
STORE_TIMEZONE  = os.getenv("STORE_TIMEZONE", "Australia/Sydney")
STORE_STATE     = os.getenv("STORE_STATE", "NSW")

GOOGLE_VISION_API_KEY = os.environ["GOOGLE_VISION_API_KEY"]
ANTHROPIC_API_KEY     = os.environ["ANTHROPIC_API_KEY"]
CLAUDE_MODEL          = "claude-sonnet-4-5"

CAMERA_MODE   = os.getenv("CAMERA_MODE", "webcam")
_cam          = os.getenv("CAMERA_SOURCE", "0")
CAMERA_SOURCE = int(_cam) if _cam.isdigit() else _cam
ARLO_EMAIL    = os.getenv("ARLO_EMAIL", "")
ARLO_PASSWORD = os.getenv("ARLO_PASSWORD", "")
ARLO_DEVICE   = os.getenv("ARLO_DEVICE_NAME", "")

CAPTURE_INTERVAL = int(os.getenv("CAPTURE_INTERVAL", "3"))
QUEUE_THRESHOLD  = int(os.getenv("QUEUE_THRESHOLD", "2"))
PASSERBY_EDGE    = float(os.getenv("PASSERBY_EDGE", "0.15"))

DAY_END_TIME = os.getenv("DAY_END_TIME", "18:00")

FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5050"))

BRIDGE_SECRET = os.getenv("BRIDGE_SECRET", "")

DB_PATH = os.path.join(os.path.dirname(__file__), "retailiq.db")
