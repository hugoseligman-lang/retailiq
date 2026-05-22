from supabase import create_client
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def insert_detection(people_count: int, zone_left: int, zone_center: int, zone_right: int):
    _client.table("detections").insert({
        "people_count": people_count,
        "zone_left":    zone_left,
        "zone_center":  zone_center,
        "zone_right":   zone_right,
    }).execute()
