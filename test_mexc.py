import requests
import json
try:
    print("Testing connection to MEXC API...")
    resp = requests.get("https://api.mexc.com/api/v3/ticker/24hr", timeout=10)
    print(f"Status: {resp.status_code}")
    print(f"Sample data: {resp.json()[0]['symbol']}")
except Exception as e:
    print(f"Connection failed: {e}")
    import traceback
    traceback.print_exc()
