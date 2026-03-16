# 💎 Scalper70 Strategy: Deep Dive & Technical Specs

This document contains the complete source code, mathematical logic, and configuration for the **Scalper70** strategy—your bot's top-performing algorithm.

---

## 1. Core Mathematical Logic
`Scalper70` is a high-win-rate scalping strategy (Targeting 70%+) that uses four independent filters to ensure only high-probability trades are taken.

### **The Four Filters:**
1.  **Trend Filter (EMA 200)**: Only takes LONGs when the price is above the 200 EMA (Uptrend) and SHORTs when below (Downtrend).
2.  **Over-Extended Filter (RSI)**: Only takes LONGs when the RSI is below 35 (Oversold) and SHORTs when above 65 (Overbought).
3.  **Momentum Filter (MACD)**: Requires the MACD Histogram to be turning in the direction of the trade (Increasing for LONG, Decreasing for SHORT).
4.  **Volume Confirmation**: Only enters if the current volume is at least **1.2x higher** than the 10-period average volume SMA.

---

## 2. Complete Python Source Code
This is the exact code from `bot/strategy.py` that runs when you select `scalper70`:

```python
class Scalper70Strategy(BaseStrategy):
    """
    High-winrate Scalping Strategy (Targeting 70%+).
    Uses EMA 200 for trend, RSI for oversold/overbought, and MACD for momentum confirmation.
    """
    def __init__(self, leverage=20):
        super().__init__(leverage=leverage)

    def calculate_indicators(self, data_list):
        if not data_list: return data_list
        closes = [d['close'] for d in data_list]
        volumes = [d['volume'] for d in data_list]
        emas_200 = calculate_ema(closes, 200)
        emas_50 = calculate_ema(closes, 50)
        rsi = calculate_rsi(data_list, 14)
        macd, signal, hist = calculate_macd(data_list)
        atrs = calculate_atr(data_list, 14)
        vol_sma = calculate_sma(volumes, 10)
        
        for i, d in enumerate(data_list):
            d['EMA_200'] = emas_200[i]
            d['EMA_50'] = emas_50[i]
            d['RSI'] = rsi[i]
            d['MACD_Hist'] = hist[i]
            d['ATR'] = atrs[i]
            d['VOL_SMA'] = vol_sma[i]
        return data_list

    def generate_signals(self, data_list):
        if len(data_list) < 200: return data_list
        for i in range(1, len(data_list)):
            d, prev_d = data_list[i], data_list[i-1]
            price, vol = d['close'], d['volume']
            rsi, macd_hist = d.get('RSI'), d.get('MACD_Hist')
            prev_macd_hist = prev_d.get('MACD_Hist')
            ema200, ema50, vol_sma = d.get('EMA_200'), d.get('EMA_50'), d.get('VOL_SMA')
            
            d['signal'] = 'NONE'
            if None in [rsi, macd_hist, prev_macd_hist, ema200, ema50, vol_sma]: continue
            
            # LONG Condition (Professional Growth Optimized): 
            # 1. Price above EMA 200 (Uptrend)
            # 2. RSI oversold (< 35) or dipping below EMA 50
            # 3. MACD histogram starting to turn up (momentum shift)
            # 4. Volume Spike (> 1.2x SMA) to confirm move
            if price > ema200 and rsi < 35 and macd_hist > prev_macd_hist and vol > (vol_sma * 1.2):
                d['signal'] = 'LONG'
            
            # SHORT Condition:
            # 1. Price below EMA 200 (Downtrend)
            # 2. RSI overbought (> 65) or jumping above EMA 50
            # 3. MACD histogram starting to turn down
            # 4. Volume Spike (> 1.2x SMA)
            elif price < ema200 and rsi > 65 and macd_hist < prev_macd_hist and vol > (vol_sma * 1.2):
                d['signal'] = 'SHORT'
                
        return data_list
```

---

## 3. How to Run Locally (Step-by-Step)

1.  **Open the project folder**: `C:\Users\sksai\OneDrive\Desktop\automated-trading-bot`
2.  **Double-click `Run_Scalper70.bat`**: This will automatically install dependencies and start the bot.
3.  **Wait 5-10 seconds**: A browser window will open automatically at `http://localhost:5000`.
4.  **Monitor Progress**: The dashboard will show real-time scans and simulated trades.

---
*Created on 2026-03-17*
