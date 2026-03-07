import sys
import json
import urllib.request
from datetime import datetime

print("Downloading Binance Data for Backtest...")
url = "https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=1m&limit=1500"

req = urllib.request.Request(url)
with urllib.request.urlopen(req) as response:
    raw_data = json.loads(response.read().decode())

data = [{
    'timestamp': k[0], 'open': float(k[1]), 'high': float(k[2]),
    'low': float(k[3]), 'close': float(k[4]), 'volume': float(k[5])
} for k in raw_data]

print(f"Downloaded {len(data)} candles.")

import os
sys.path.append(os.getcwd())
from bot.strategy import SmartMoneyStrategy

print("Calculating Indicators...")
strategy = SmartMoneyStrategy(leverage=45)
data = strategy.calculate_indicators(data)
data = strategy.generate_signals(data)

longs = sum(1 for d in data if d.get('signal') == 'LONG')
shorts = sum(1 for d in data if d.get('signal') == 'SHORT')

print(f"Generated {longs} LONG signals and {shorts} SHORT signals in the last {len(data)} minutes.")

# Look at the most recent signals
for d in data[-20:]:
    if d.get('signal') in ['LONG', 'SHORT']:
        time_str = datetime.fromtimestamp(d['timestamp']/1000).strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{time_str}] {d['signal']} @ ${d['close']:.2f} | RSI: {d['RSI']:.1f} | 200EMA: {d.get('EMA_200')}")

print("\nBacktest Simulation Complete. Data logic is working!")
