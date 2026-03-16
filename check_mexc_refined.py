import requests
import json

MEXC_BASE = "https://api.mexc.com/api/v3"
resp = requests.get(f"https://api.mexc.com/api/v3/ticker/24hr")
data = resp.json()

valid_pairs = []
for item in data:
    if not item['symbol'].endswith('USDT'):
        continue
        
    symbol = item['symbol']
    if 'UPUSDT' in symbol or 'DOWNUSDT' in symbol or 'BEAR' in symbol or 'BULL' in symbol:
        continue
        
    vol = float(item.get('quoteVolume', 0))
    if vol >= 1000000:
        valid_pairs.append({'symbol': symbol, 'vol': vol})

print(f"Valid pairs with > 1M: {len(valid_pairs)}")
valid_pairs.sort(key=lambda x: x['vol'], reverse=True)
print("Top 10 valid pairs:")
for p in valid_pairs[:10]:
    print(f" {p['symbol']}: {p['vol']}")
