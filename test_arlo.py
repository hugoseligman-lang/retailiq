"""
Run this to test your Arlo credentials.
Usage:  python test_arlo.py
"""
import getpass, json, sys

def _ensure(pkg, import_name=None):
    try:
        __import__(import_name or pkg)
    except ImportError:
        print(f"Installing {pkg}...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

_ensure("cloudscraper")

import cloudscraper

AUTH = "https://ocapi-app.arlo.com"
API  = "https://myapi.arlo.com"

email    = input("Arlo email: ").strip()
password = getpass.getpass("Arlo password (hidden): ")

sc = cloudscraper.create_scraper()
headers = {
    "User-Agent":    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/120.0.0.0 Safari/537.36",
    "Content-Type":  "application/json",
    "Accept":        "application/json, text/plain, */*",
    "Origin":        "https://my.arlo.com",
    "Referer":       "https://my.arlo.com/",
    "auth-version":  "2",
    "Source":        "arloCamWeb",
    "schemaVersion": "1",
}

print("\nStep 1: Logging in...")
r = sc.post(f"{AUTH}/api/auth",
            json={"email": email, "password": password},
            headers=headers)

print(f"  HTTP status: {r.status_code}  length: {len(r.text)}")
if not r.text.strip():
    print("  ✗ Empty response — Arlo's bot protection blocked the request.")
    print("    Wait a few minutes and try again.")
    input("\nPress Enter to close.")
    sys.exit(1)

try:
    body = r.json()
except Exception:
    print(f"  Raw: {r.text[:300]}")
    input("\nPress Enter to close.")
    sys.exit(1)

meta = body.get("meta", {})
code = meta.get("code")
print(f"  Meta code: {code}  message: {meta.get('message')}")

if code == 401:
    print("\n✗ Wrong password.")
    input("Press Enter to close.")
    sys.exit(1)

if code == 403:
    print("\n✗ Account locked — too many failed attempts.")
    print("  Wait 15–30 minutes, or check your email for an Arlo unlock link.")
    input("Press Enter to close.")
    sys.exit(1)

if code not in (200, 0, None):
    print(f"\n✗ Unexpected error: {meta.get('message')}")
    input("Press Enter to close.")
    sys.exit(1)

data  = body.get("data", {})
token = data.get("token", "")
headers["Authorization"] = token

factors = data.get("factors") or []
if factors:
    print(f"\n  2FA required. Factors: {[f.get('factorType') for f in factors]}")
    factor    = next((f for f in factors if "EMAIL" in str(f.get("factorType","")).upper()), factors[0])
    factor_id = factor.get("factorId","")

    print("\nStep 2: Sending 2FA code to your email...")
    r2 = sc.post(f"{AUTH}/api/startAuth", json={"factorId": factor_id}, headers=headers)
    print(f"  HTTP status: {r2.status_code}")
    try:
        b2 = r2.json()
        fac_auth_code = b2.get("data", {}).get("factorAuthCode","")
        print(f"  factorAuthCode: {'✓ got it' if fac_auth_code else '✗ MISSING — raw: ' + r2.text[:200]}")
    except Exception:
        print(f"  Raw: {r2.text[:300]}")
        input("Press Enter to close.")
        sys.exit(1)

    code_input = input("\nEnter the code from your email: ").strip()

    print("\nStep 3: Verifying code...")
    r3 = sc.post(f"{AUTH}/api/finishAuth",
                 json={"factorAuthCode": fac_auth_code, "otp": code_input},
                 headers=headers)
    print(f"  HTTP status: {r3.status_code}")
    try:
        b3 = r3.json()
        print(f"  Meta: {b3.get('meta')}")
        if b3.get("meta", {}).get("code") not in (200, None, 0):
            print(f"\n✗ 2FA failed: {b3.get('meta',{}).get('message')}")
            input("Press Enter to close.")
            sys.exit(1)
        if b3.get("data", {}).get("token"):
            token = b3["data"]["token"]
            headers["Authorization"] = token
        print("  ✓ 2FA verified!")
    except Exception:
        print(f"  Raw: {r3.text[:300]}")
        input("Press Enter to close.")
        sys.exit(1)
else:
    print("  No 2FA required — logged in directly.")

print("\nStep 4: Getting cameras...")
rd = sc.get(f"{API}/hmsweb/users/devices", headers=headers)
print(f"  HTTP status: {rd.status_code}")
try:
    devices = rd.json().get("data", [])
except Exception:
    print(f"  Raw: {rd.text[:300]}")
    input("Press Enter to close.")
    sys.exit(1)

cameras = [d for d in devices
           if "arlo" in d.get("deviceType","").lower()
           or "camera" in d.get("deviceType","").lower()]

if cameras:
    print(f"\n✓ Connected! Found {len(cameras)} camera(s):")
    for c in cameras:
        print(f"    - {c.get('deviceName')}  (id: {c.get('deviceId')}, type: {c.get('deviceType')})")
else:
    print(f"\n✓ Connected. Device types: {[d.get('deviceType') for d in devices]}")

input("\nPress Enter to close.")
