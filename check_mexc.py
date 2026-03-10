import requests
import json

MEXC_BASE = "https://api.mexc.com/api/v3"
resp = requests.get(f"https://api.mexc.com/api/v3/ticker/24hr")
data = resp.json()

print(f"Total pairs: {len(data)}")
if data:
    print(f"Sample item: {json.dumps(data[0], indent=2)}")

usdt_pairs = [item for item in data if item['symbol'].endswith('USDT')]
print(f"USDT pairs: {len(usdt_pairs)}")

# Filter for quoteVolume
vols = []
for item in usdt_pairs:
    try:
        vol = float(item.get('quoteVolume', 0))
        vols.append(vol)
    except:
        pass

vols.sort(reverse=True)
print(f"Top 5 volumes: {vols[:5]}")
print(f"Pairs with > 1M: {len([v for v in vols if v > 1000000])}")
print(f"Pairs with > 100k: {len([v for v in vols if v > 100000])}")
