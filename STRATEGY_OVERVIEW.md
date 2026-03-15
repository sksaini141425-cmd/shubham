# Strategy Overview: Smart Money Scalper

This document outlines the core logic of the trading strategy implemented in `bot/strategy.py`.

## Approach
The strategy is a **Trend-Following Mean Reversion** system. It assumes that in a strong trend (defined by the 200 EMA), price pullbacks to the Bollinger Band extremes represent high-probability entry points where the trend is likely to resume.

## Technical Indicators
- **Exponential Moving Average (EMA) - 200 Period**: The primary trend filter.
- **Bollinger Bands (20, 2.0)**: Measures price volatility and identifies overextended pullbacks.
- **Relative Strength Index (RSI) - 14 Period**: Confirms that the pullback has sufficient "room" to bounce before becoming overbought/oversold.
- **Average True Range (ATR)**: Used for dynamic stop-loss and take-profit calculations.

## Entry Rules

### LONG (Buy)
1. **Trend Filter**: Current Price > 200 EMA.
2. **Pullback**: Current Price < Lower Bollinger Band.
3. **Confirmation**: RSI < 45 (ensures we aren't buying at the very peak of a move).

### SHORT (Sell)
1. **Trend Filter**: Current Price < 200 EMA.
2. **Pullback**: Current Price > Upper Bollinger Band.
3. **Confirmation**: RSI > 55 (ensures we aren't selling at the very bottom).

## Exit Rules
- **Take Profit (TP)**: Set at 4.0% (Net of fees).
- **Stop Loss (SL)**: Set at 2.5% (Net of fees).
- **Dynamic Exit**: The bot monitors for trend exhaustion and may exit early if indicators suggest a reversal against the position.

## Timeframe
- **1-Minute (1m)**: This strategy is optimized for high-frequency scalping on liquid futures markets (Binance/MEXC).

## Performance Optimization
The bot uses **Dynamic Leverage Calculation** to ensure that even with a tiny balance (e.g., $3.00), it can meet the exchange's "Minimum Notional" requirements (usually $5-$20) by automatically adjusting leverage between 10x and 50x.
