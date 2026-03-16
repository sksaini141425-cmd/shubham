# ProfitBot Pro: Manual Review & Strategy Guide

This document provides a comprehensive overview of your trading bot's configuration, available strategies, and recent performance history.

## 1. Current Configuration Summary
*Based on your .env file:*
- **Exchange**: Bybit (Testnet: True)
- **Initial Capital**: $3.00
- **Current Strategy**: `elite`
- **Leverage**: 50x
- **Max Concurrent Trades**: 10
- **Scanning**: Top 15 symbols

---

## 2. Trading Strategy Logic
Here are the core strategies available in `bot/strategy.py`:

### **Scalper70 (Your Simulation Strategy)**
- **Target**: 70%+ Win Rate.
- **Indicators**: EMA 200 (Trend), RSI (Oversold/Overbought), MACD (Momentum), Volume.
- **Logic**:
  - **LONG**: Price > EMA 200 AND RSI < 35 AND MACD Histogram turning up AND Volume Spike.
  - **SHORT**: Price < EMA 200 AND RSI > 65 AND MACD Histogram turning down AND Volume Spike.

### **Elite Scalper**
- **Indicators**: EMA 50, RSI, MACD.
- **Logic**: Focuses on "RSI Pullbacks" within a trend. Enters LONG when price is above EMA 50 and RSI dips below 40.

### **Diamond Sniper**
- **Target**: Explosive Breakouts.
- **Logic**: Waits for a "Bollinger Band Squeeze" (low volatility) and enters when price breaks out with 1.5x average volume. Uses 50x leverage to catch 5-10% moves.

### **Smart Money Pro**
- **Indicators**: Dual EMA (50/200), ADX (Trend Strength), Bollinger Bands.
- **Logic**: Only enters during strong trends (ADX > 25) when price touches the outer Bollinger Bands as a pullback.

---

## 3. Recent Performance History (Last Session)
*Analyzed from `trade_log_local_test.json`:*

- **Start Balance**: $3.00
- **Final Balance**: **$7.51**
- **Total Profit**: **$4.51 (150.3% Gain)**

### **Top Performers**
- **TONIXAIUSDT**: Multiple successful short scalps (Profits of $0.67, $0.18, $0.16).
- **TAOUSDT**: Strong long run (+$0.15).
- **THEUSDT**: Recent morning win (+$0.11).

### **Key Takeaways**
- The bot is highly effective at catching quick reversals on high-volatility symbols.
- The "Scalper70" strategy's volume filter successfully avoided many fakeouts during the session.

---

## 4. How to Run Manually
1. **Open Terminal** in the project folder.
2. **Install requirements**: `pip install -r requirements.txt`
3. **Run Simulation**: `python run_local_sim.py`
4. **View Dashboard**: Open `http://localhost:5000` in your browser.

---
*Generated on 2026-03-17*
