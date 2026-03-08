import json
import re
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import pytz

import sys
sys.stdout = open('history_output.txt', 'w', encoding='utf-8')
try:
    with open(r'C:\Users\sksai\vip_signals.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
except Exception as e:
    print(f"Error loading JSON: {e}")
    exit()

# Parse signals
parsed_signals = []
for item in data:
    text = item.get('text', '')
    if 'STOP LOSS' not in text.upper(): continue
    
    clean_text = text.replace('*', '').strip()
    direction = 'LONG' if 'buy' in clean_text.lower() else 'SHORT' if 'sell' in clean_text.lower() else None
    if not direction: continue
    
    entry, sl, tp1, tp3 = None, None, None, None
    lines = clean_text.split('\n')
    for line in lines:
        nums = re.findall(r'\d+(?:\.\d+)?', line)
        if not nums: continue
        val = float(nums[0])
        
        up = line.upper()
        if 'NOW' in up or 'BUY' in up or 'SELL' in up:
            if not entry: entry = val
        elif 'STOP LOSS' in up or 'SL' in up:
            sl = val
        elif 'TARGET' in up or 'TP' in up:
            if not tp1: tp1 = val
            tp3 = val
            
    if entry and sl and tp1:
        # Check date filtering
        sig_date = datetime.fromisoformat(item['date'])
        parsed_signals.append({
            'date': sig_date,
            'direction': direction,
            'entry': entry,
            'sl': sl,
            'tp': tp3 or tp1,
            'text': clean_text
        })

print(f"Parsed {len(parsed_signals)} valid signals. Downloading XAUUSD data...")

# Download 7 days of 1-minute data for Gold
gold_ticker = "GC=F" # Gold futures
# Try to get 1m data for the last 7 days
try:
    df = yf.download(tickers=gold_ticker, period="7d", interval="1m", progress=False)
except Exception as e:
    print(f"Error downloading data: {e}")
    exit()

if df.empty:
    print("No data downloaded from Yahoo Finance.")
    exit()

print(f"Downloaded {len(df)} 1-minute candles. Analyzing signals...\n")

wins = 0
losses = 0
unknown = 0

for sig in reversed(parsed_signals):  # Oldest to newest
    sig_time = sig['date']
    # DataFrame index is timezone aware usually, but let's compare UTC
    # yfinance 1m data is usually market hours only, so we might miss some after-hours forex moves
    
    # Filter df to after signal time
    # Make sig_time tz-naive or match df
    if df.index.tz is None:
        sig_time = sig_time.replace(tzinfo=None)
    else:
        sig_time = sig_time.astimezone(df.index.tz)
        
    future_data = df[df.index >= sig_time]
    
    if future_data.empty:
        unknown += 1
        continue
        
    direction = sig['direction']
    entry = sig['entry']
    tp = sig['tp']
    sl = sig['sl']
    
    outcome = "UNKNOWN"
    
    # We will iterate through future 1m candles up to 48 hours after the signal
    # to see which is hit first: TP or SL
    max_duration = sig_time + timedelta(hours=48)
    trade_data = future_data[future_data.index <= max_duration]
    
    for idx, row in trade_data.iterrows():
        high = row['High']
        low = row['Low']
        
        # Determine actual values since yfinance returns Series sometimes
        if isinstance(high, pd.Series): high = high.iloc[0]
        if isinstance(low, pd.Series): low = low.iloc[0]
        
        if direction == 'LONG':
            if low <= sl:
                outcome = "LOSS"
                break
            if high >= tp:
                outcome = "WIN"
                break
        else: # SHORT
            if high >= sl:
                outcome = "LOSS"
                break
            if low <= tp:
                outcome = "WIN"
                break
                
    if outcome == "WIN": wins += 1
    elif outcome == "LOSS": losses += 1
    else: unknown += 1
    
    print(f"[{sig_time.strftime('%b %d %H:%M')}] {direction} XAUUSD @ {entry} | TP {tp} | SL {sl} -> {outcome}")

print("\n==================================")
print(f"WINS: {wins}")
print(f"LOSSES: {losses}")
print(f"UNKNOWN/PENDING: {unknown}")

if wins + losses > 0:
    win_rate = (wins / (wins + losses)) * 100
    print(f"WIN RATE: {win_rate:.1f}%")
else:
    print("Could not evaluate (maybe yfinance data missing or weekend gap).")
print("==================================")
