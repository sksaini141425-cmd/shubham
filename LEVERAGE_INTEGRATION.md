# LEVERAGE TRADING INTEGRATION GUIDE

## Overview

Your existing automated trading bot can now use **leverage** to trade with minimum position sizes. This guide explains how to integrate the leverage system.

## Files Added

### 1. `config_leverage.py`
- Configuration for leverage settings
- Position sizing calculations with leverage
- Risk management parameters

### 2. `leverage_position_sizer.py`
- Intelligently calculates position sizes with leverage
- Handles minimum position requirements
- Monitors margin levels and liquidation risk
- Validates positions before trading

### 3. `enhanced_paper_exchange.py`
- Paper trading exchange with leverage support
- Opens and closes positions with margin tracking
- Calculates real P&L including fees and funding costs
- Provides account summary with margin warnings

### 4. `example_leverage_trading.py`
- Example script showing how to use leverage
- Demonstrates trading scenarios
- Shows P&L calculations
- **RUN THIS FIRST** to understand how it works:
  ```bash
  python example_leverage_trading.py
  ```

## Quick Start

### Step 1: Run the Example
```bash
python example_leverage_trading.py
```
This shows you exactly how leverage works with $3 capital.

### Step 2: Edit `config_leverage.py` for Your Settings

```python
LEVERAGE = 5  # Change leverage (1-20x)
STARTING_BALANCE = 3.0  # Your capital
RISK_PER_TRADE = 0.05  # 5% per trade
MAX_CONCURRENT_POSITIONS = 5  # Max open trades
```

### Step 3: Use in Your Bot Code

### For the Existing `main.py`:

Add these imports:
```python
from leverage_position_sizer import LeveragePositionSizer
from enhanced_paper_exchange import EnhancedPaperExchange
from config_leverage import LEVERAGE, STARTING_BALANCE
```

Replace position sizing code with:
```python
# Initialize leverage position sizer
position_sizer = LeveragePositionSizer(
    account_balance=current_balance,
    leverage=LEVERAGE
)

# Calculate position size with leverage
position_info = position_sizer.calculate_position_size(
    entry_price=current_price,
    stop_loss_price=stop_loss,
    pair=symbol
)

# Check if position is valid
if position_info['meets_minimum']:
    position_size = position_info['position_size']
    print(f"Opening {symbol} with {LEVERAGE}x leverage")
    # Place order
else:
    logger.warning(f"Position too small for {symbol}")
```

### For Paper Trading:

```python
# Create enhanced paper exchange
exchange = EnhancedPaperExchange(
    initial_balance=STARTING_BALANCE,
    leverage=LEVERAGE
)

# Open a position
position = exchange.open_position(
    symbol='BTC/USDT',
    side='buy',
    entry_price=68000,
    quantity=0.0000735,  # Calculated by position sizer
    leverage=LEVERAGE
)

# Monitor position
exchange.update_position_price(position['id'], current_price)

# Check stop loss / take profit
result = exchange.check_tp_sl(position['id'], current_price)
if result:
    logger.info(f"Position closed: {result['reason']}")

# Get account summary
summary = exchange.get_account_summary()
print(f"Balance: ${summary['balance']:.2f}")
print(f"ROI: {summary['roi_percent']:+.2f}%")
```

## Understanding the Calculations

### With $3 and 5x Leverage:

**Math:**
- Starting Capital: $3
- Effective Buying Power: $3 × 5 = $15
- Risk per Trade: $3 × 5% = $0.15

**Opening a Trade:**
1. Entry Price: $68,000 (BTC)
2. Stop Loss: $66,640 (2% below)
3. Risk Amount: $0.15
4. Position Size = Risk / (Entry - SL) = 0.15 / 1,360 = **0.0001103 BTC**
5. Position Value = 0.0001103 × 68,000 = **$7.50**
6. **Meets $5 minimum? YES ✓**
7. **Effective Exposure = $7.50 × 5 = $37.50**

**If trade wins (3% take profit):**
- Profit = 0.0001103 × 2,040 (3% of $68k) = $0.225
- Minus fees = ~$0.22
- **Result: +$0.22 profit!**

**If trade loses (2% stop loss):**
- Loss = $0.15 (exactly your risk)
- Effective loss with leverage = -$0.15

## Key Differences with Leverage

### ✓ Advantages:
1. **Smaller positions allowed** - Meet $5 minimum with 5x leverage
2. **Better capital efficiency** - Use less capital per trade
3. **More trades possible** - Open multiple positions simultaneously
4. **Higher profit potential** - 5x return on winning trades

### ✗ Disadvantages:
1. **5x losses** - 2% loss = -10% of capital
2. **Funding costs** - Interest on borrowed margin
3. **Liquidation risk** - Account can be liquidated if margin drops too low
4. **Complexity** - More parameters to monitor

## Important Settings

### Risk Management with Leverage:

```python
# config_leverage.py

MAX_DAILY_LOSS_PERCENT = 20  # Stop at -20% in a day
LIQUIDATION_LEVEL = 0.10  # Close when 10% margin (critical!)
WARNING_LEVEL = 0.30  # Warn at 30% margin usage
```

**With 5x leverage:**
- Your "safe" margin is ~20% (5x leverage = 1/5 = 20%)
- Below 15% = Liquidation risk
- Below 30% = Warning level

### Position Sizing:

```python
STOP_LOSS_PERCENT = 2.0  # 2% SL
TAKE_PROFIT_PERCENT = 6.0  # 6% TP (3:1 reward/risk)
```

This maintains 3:1 reward-to-risk ratio:
- Risk $0.15 to win $0.45

## Important: Binance Limits

Binance Futures has rules:
- **Minimum order**: ~$5 USDT
- **Maximum leverage**: Up to 125x (not recommended)
- **Funding rate**: Every 8 hours
  - Cost = Position Value × Funding Rate / 8
  - Ranges from 0.01% to 0.10% per day
  - If BTC holding 4 days = ~0.2-0.4% cost

## Monitoring & Alerts

### Check Margin Level:
```python
is_risky, margin_level = position_sizer.is_liquidation_risk()
if is_risky:
    logger.warning(f"Liquidation risk! Margin: {margin_level:.1f}%")
```

### Get Margin Status:
```python
warning = position_sizer.get_margin_warning()
# Output: "✓ Safe margin level: 45.2%"
#    or  "⚠️  HIGH MARGIN USAGE: 65.0%"
#    or  "🚨 LIQUIDATION RISK! Margin: 95.0%"
```

### Real-Time Summary:
```python
summary = exchange.get_account_summary()
for key, value in summary.items():
    print(f"{key}: {value}")
```

## Troubleshooting

### "Position too small for minimum"
- **Cause**: Even with leverage, position < $5
- **Solution**: Increase leverage or starting capital

### "Liquidation Risk Warning"
- **Cause**: Too many open positions using too much margin
- **Solution**: Close some positions immediately

### "Margin usage too high"
- **Cause**: Can't open more positions
- **Solution**: Close an existing position or use smaller position size

## Testing

### Before using live:

1. **Run example:**
   ```bash
   python example_leverage_trading.py
   ```

2. **Test with paper trading:**
   ```bash
   # Use EnhancedPaperExchange to SimulateTrades
   ```

3. **Backtest on historical data:**
   ```bash
   python run_serious_backtest.py --leverage 5
   ```

4. **Start with 1x leverage** before increasing

## Best Practices

### ✓ DO:
- Start with 2x leverage
- Use tight stop losses (1-2%)
- Monitor margin constantly
- Diversify across many pairs
- Take profits regularly
- Have exit plan BEFORE entering

### ✗ DON'T:
- Use maximum leverage (too risky)
- Trade illiquid pairs with leverage
- Ignore funding costs
- Let losing positions run
- Use leverage if you can't monitor

## Integration Checklist

- [ ] Read this entire guide
- [ ] Run `python example_leverage_trading.py`
- [ ] Edit `config_leverage.py` with your settings
- [ ] Test with paper trading (EnhancedPaperExchange)
- [ ] Backtest with leverage on historical data
- [ ] Start live trading with 1x leverage
- [ ] Gradually increase leverage (max 5-10x)
- [ ] Monitor margin levels every day

## Support & Debugging

### Enable logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check position details:
```python
summary = exchange.get_position_summary()
for pos in summary['positions']:
    print(f"{pos['symbol']}: ${pos['unrealized_pnl']:+.2f} ({pos['unrealized_pnl_pct']:+.1f}%)")
```

### View account health:
```python
summary = exchange.get_account_summary()
print(summary['margin_warning'])
```

---

**Questions?** Check the example: `python example_leverage_trading.py`
