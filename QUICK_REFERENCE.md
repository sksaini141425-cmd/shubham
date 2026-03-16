# ⚡ LEVERAGE TRADING - QUICK REFERENCE

## One-Minute Overview

```
$3 Capital + 5x Leverage = $15 Buying Power
Each trade: Risk $0.15, Win $0.45 (3:1 ratio)
10 winning trades = +$4.50 profit = +150% ROI
```

## Position Sizing Formula

```
Position Size = (Capital × Risk% × Leverage) / (Entry - Stop Loss)
Position Value = Position Size × Entry Price
```

## Example Calculation

```
Capital: $3, Leverage: 5x, Risk: 5%

BTC Entry: $68,000
SL: $66,640 (2%)
Expected TP: $72,080 (6%)

Formula:
  Position Size = ($3 × 0.05 × 5) / ($68,000 - $66,640)
  Position Size = $0.75 / $1,360
  Position Size = 0.000551 BTC
  Position Value = 0.000551 × $68,000 = $37.50

Profit if TP hit:
  (0.000551 × $4,080) - $0.03 = $2.22 profit
  ROI: +74% on $3
```

## Leverage Levels

| Leverage | Capital | Buying Power | Risk | Entry Fee | Daily Cost |
|----------|---------|--------------|------|-----------|-----------|
| 1x | $3.00 | $3.00 | $0.15 | $0.0012 | Low |
| 2x | $3.00 | $6.00 | $0.15 | $0.0024 | Low |
| 5x | $3.00 | $15.00 | $0.15 | $0.0060 | Low |
| 10x | $3.00 | $30.00 | $0.15 | $0.0120 | Medium |

## Risk/Reward Scenarios

### Scenario 1: 2% SL Hit (Loss)
```
Entry: $68,000
Exit: $66,640 (SL)
Position: 0.00055 BTC
Loss: -$0.15 (your risk)
Margin Impact: -5% of $3 capital
Margin Level After: Still safe
```

### Scenario 2: 6% TP Hit (Win)  
```
Entry: $68,000
Exit: $72,080 (TP)
Position: 0.00055 BTC
Profit: $2.22 (before fees: $2.25)
Margin Impact: +74% gain
Margin Level After: Even safer
```

### Scenario 3: Bad Exit at 10% Down
```
Entry: $68,000
Exit: $61,200 (no stop!)
Position: 0.00055 BTC
Loss: -$3.76 (5x your risk!)
Margin Impact: -125% ... LIQUIDATED!
Result: ACCOUNT BLOWN UP
```

## Margin Levels

| Level | Status | Action |
|-------|--------|--------|
| 0-10% | Safe | Keep trading |
| 10-20% | Comfortable | OK to trade |
| 20-30% | Caution | No new positions |
| 30-33% | DANGER | Close positions NOW |
| 33%+ | LIQUIDATION | Account blown up |

## Daily Checklist

### Before First Trade:
- [ ] Capital: $3.00
- [ ] Check leverage: 5x
- [ ] Risk per trade: $0.15
- [ ] Min position: $5 notional
- [ ] Margin level: < 20%
- [ ] Internet connection: Stable
- [ ] Orders: Set up SL + TP

### Every Hour:
- [ ] Margin level: Check every trade
- [ ] Unrealized P&L: Monitor
- [ ] Funding costs: Accumulating
- [ ] Close old positions: 4+ hours

### If Margin > 20%:
- [ ] Stop opening new trades
- [ ] Take profits on winners
- [ ] Close half positions

### If Margin > 30%:
- [ ] CLOSE ALL POSITIONS
- [ ] Risk is critical
- [ ] Can lose total capital

## Command Reference

### Import & Initialize:
```python
from leverage_position_sizer import LeveragePositionSizer
from enhanced_paper_exchange import EnhancedPaperExchange

sizer = LeveragePositionSizer(capital=3.0, leverage=5)
exchange = EnhancedPaperExchange(initial_balance=3.0, leverage=5)
```

### Calculate Position Size:
```python
pos = sizer.calculate_position_size(
    entry_price=68000,
    stop_loss_price=66640,
    pair='BTC/USDT'
)
print(f"Size: {pos['position_size']:.8f}")
print(f"Value: ${pos['position_value']:.2f}")
print(f"Meets minimum: {pos['meets_minimum']}")
```

### Open Position:
```python
trade = exchange.open_position(
    symbol='BTC/USDT',
    side='buy',
    entry_price=68000,
    quantity=0.000551
)
```

### Monitor Position:
```python
exchange.update_position_price(trade['id'], current_price=68500)
result = exchange.check_tp_sl(trade['id'], current_price=68500)
if result:
    print(f"Closed: {result['reason']}")
```

### Check Account:
```python
summary = exchange.get_account_summary()
print(f"Balance: ${summary['balance']:.2f}")
print(f"Margin: {summary['margin_level']:.1f}%")
print(summary['margin_warning'])
```

## Decision Tree

```
Ready to trade?
  |
  ├─ Check margin level
  |   └─ > 30%? CLOSE POSITIONS and STOP
  |   └─ 10-30%? Can trade small
  |   └─ < 10%? Can trade normal
  |
  ├─ Calculate position size
  |   └─ Below $5? Can't trade
  |   └─ $5-$100? OK to trade
  |   └─ > Effective balance? TOO BIG
  |
  ├─ Set stop loss
  |   └─ 1% = Scalping (risky)
  |   └─ 2% = Good (use this)
  |   └─ 3% = Wider (less stops)
  |   └─ > 5% = Too wide (risk too much)
  |
  ├─ Set take profit
  |   └─ At 3:1 ratio (usually 6% for 2% SL)
  |         or 4.5% for 1.5% SL
  |
  ├─ Open position
  |   └─ Record entry price
  |   └─ Set alerts for SL/TP
  |   └─ Monitor margin
  |
  ├─ Position management  
  |   └─ Hit take profit? CLOSE (lock profit)
  |   └─ Hit stop loss? CLOSE (cut loss)
  |   └─ 4 hours open? CLOSE (funding cost)
  |   └─ Margin > 20%? CLOSE (risk)
  |
  └─ End of day
      └─ Email report
      └─ Check total P&L
      └─ Plan tomorrow
```

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Position too small | Below $5 min | Use 5x+ leverage |
| Can't open position | Margin too high | Close some positions |
| Got liquidated | Margin hit 33% | Use smaller positions |
| Lost money on stop  | Stop too loose | Use 2% stops |
| Funding cost too high | Holding > 8 hrs | Close old trades |
| Order didn't fill | Slippage | Use limit orders |

## Important Reminders

### 🚨 NEVER:
- Use > 10x leverage
- Trade without stop loss
- Risk > 5% of capital per trade
- Hold position > 8 hours if losing
- Ignore margin warnings
- Trade on illiquid pairs with leverage

### ✅ ALWAYS:
- Check margin before trading
- Use 2% stop loss minimum
- Risk only $0.15 per trade
- Take profits at 3:1 ratio
- Monitor positions every 5 min
- Close at warning level

## Math Cheat Sheet

### Convert Percentage to Dollar
```
Dollar Amount = Capital × Percentage
$0.15 = $3.00 × 0.05
```

### Convert Dollar to Percentage
```
Percentage = Dollar / Capital
0.05 = $0.15 / $3.00
```

### Calculate Position Size
```
Size = Risk / Price Difference
0.000551 = $0.75 / $1,360
```

### Calculate Profit %
```
Profit % = Profit / (Size × Entry) × 100
74% = $2.22 / ($0.000551 × $68,000) × 100
```

### Calculate ROI %
```
ROI % = (Final - Initial) / Initial × 100
+74% = ($3.74 - $3.00) / $3.00 × 100
```

## Emergency Procedures

### Margin Level > 30%:
```
1. STOP all new trades
2. Close half of positions
3. Check margin again
4. Close more if needed
5. Don't trade until < 20%
```

### Position Losing > 10%:
```
1. It's hitting stop loss soon
2. Don't average down!
3. Let stop loss work
4. Move to next trade
```

### Funding Rate Spike:
```
1. Costs jumping 10-100x normal
2. Close positions immediately
3. Wait for rate to normalize
4. Resume trading
```

### Internet Disconnect:
```
1. Can't monitor positions
2. Liquidation risk!
3. Reconnect ASAP
4. Check margin first
5. Close risky positions
```

---

**Print this card!** Keep by your desk while trading. Reference often.
