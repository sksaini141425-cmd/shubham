import json
import re
import yfinance as yf
from datetime import datetime, timedelta, timezone
import pytz
import sys

sys.stdout = open('obrien_history.txt', 'w', encoding='utf-8')

try:
    with open(r'C:\Users\sksai\vip_signals.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
except Exception as e:
    print(f"Error loading JSON: {e}")
    exit()

signals = []
for item in data:
    if "O'Brien Crypto" in item.get('group', ''):
        text = item.get('text', '')
        if not text: continue
        
        # Simple extraction
        clean = text.replace('*', '').replace('-', ' ')
        up = clean.upper()
        if 'BUY' not in up and 'ENTRY' not in up: continue
        if 'TP' not in up and 'TAKE PROFIT' not in up and 'TARGET' not in up: continue
        if 'SL' not in up and 'STOP LOSS' not in up: continue
        
        # 1. Find symbol
        # Look for things like APT/USDT or AVAXUSDT
        sym_match = re.search(r'([A-Z]{3,5})/?USDT', up)
        if not sym_match: continue
        symbol = sym_match.group(1) + "-USD" # Yahoo finance format
        
        # 2. Find direction
        direction = 'SHORT' if 'SHORT' in up or 'SELL' in up else 'LONG'
        
        # 3. Find nums
        entry, sl, tp = None, None, None
        for line in clean.split('\n'):
            line_up = line.upper()
            nums = re.findall(r'\d+(?:\.\d+)?', line)
            if not nums: continue
            val = float(nums[0])
            
            if 'BUY' in line_up or 'ENTRY' in line_up: entry = val
            elif 'STOP' in line_up or 'SL' in line_up: sl = val
            elif 'PROFIT' in line_up or 'TARGET' in line_up or 'TP' in line_up: tp = val
            
        if entry and sl and tp:
            # Get date
            date_str = item.get('date', '')
            if not date_str: continue
            dt = datetime.fromisoformat(date_str)
            signals.append({'symbol': symbol, 'dir': direction, 'entry': entry, 'tp': tp, 'sl': sl, 'dt': dt})

print(f"Parsed {len(signals)} valid O'Brien crypto signals.")

results = {'WIN': 0, 'LOSS': 0, 'UNKNOWN': 0}
for s in signals:
    # download data from signal time to now
    start_str = (s['dt']).strftime('%Y-%m-%d')
    end_str = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    print(f"Downloading {s['symbol']} from {start_str}...")
    try:
        df = yf.download(s['symbol'], period="7d", interval="1m", progress=False)
        if df.empty:
            print(f"No data for {s['symbol']}")
            continue
            
        # filter to after signal
        # yfinance index is tz-aware usually
        df = df[df.index >= s['dt']]
        
        outcome = "UNKNOWN"
        for idx, row in df.iterrows():
            high = float(row['High'].iloc[0]) if hasattr(row['High'], 'iloc') else float(row['High'])
            low = float(row['Low'].iloc[0]) if hasattr(row['Low'], 'iloc') else float(row['Low'])
            
            if s['dir'] == 'LONG':
                if low <= s['sl']: outcome = 'LOSS'; break
                if high >= s['tp']: outcome = 'WIN'; break
            else:
                if high >= s['sl']: outcome = 'LOSS'; break
                if low <= s['tp']: outcome = 'WIN'; break
        
        results[outcome] += 1
        print(f"Signal: {s['dir']} {s['symbol']} Entry {s['entry']} TP {s['tp']} SL {s['sl']} -> {outcome}")
        
    except Exception as e:
        print(f"Error checking {s['symbol']}: {e}")

print(f"\nFINAL OBRIEN RESULTS: {results}")
