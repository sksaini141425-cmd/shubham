import requests
import json
try:
    r = requests.get('http://localhost:5002/api/state')
    data = r.json()
    symbols = data.get('symbols', {})
    print(f"Checking top 5 symbols for signals (Strategy: RSD):")
    for sym, s in list(symbols.items())[:5]:
        rsi = s.get('rsi')
        macd = s.get('macd_hist')
        signal = s.get('signal', 'NONE')
        price = s.get('price')
        atr = s.get('atr')
        if price and atr:
            atr_pct = atr / price
            sl_pct = max(-0.015, -(atr_pct * 1.5))
            print(f"[{sym}] Price: {price} | RSI: {rsi} | ATR: {atr:.6f} ({atr_pct*100:.2f}%) | Calc SL: {sl_pct*100:.2f}% | Signal: {signal}")
        else:
            print(f"[{sym}] Price: {price} | ATR: {atr} | Signal: {signal}")
except Exception as e:
    print(f"Error: {e}")
