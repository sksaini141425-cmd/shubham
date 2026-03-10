import requests
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
try:
    print("Testing INSECURE connection to MEXC API...")
    resp = requests.get("https://api.mexc.com/api/v3/ticker/24hr", timeout=10, verify=False)
    print(f"Status: {resp.status_code}")
    print(f"Sample data: {resp.json()[0]['symbol']}")
except Exception as e:
    print(f"Insecure connection also failed: {e}")
    import traceback
    traceback.print_exc()
