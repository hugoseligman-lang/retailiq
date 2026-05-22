"""
RetailIQ — camera detection entry point.
Run this on the machine connected to the camera.
It captures frames, calls Google Vision, and writes results to Supabase.
"""
import signal
import sys
import detector


def handle_shutdown(sig, frame):
    print("\n[main] Shutting down…")
    detector.stop()
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT,  handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    print("[main] RetailIQ camera daemon starting…")
    t = detector.start(daemon=False)
    t.join()
