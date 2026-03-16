"""
Enhanced Trading Bot Configuration with Leverage Support
Use this config for aggressive trading with leverage
"""

# ==================== LEVERAGE CONFIGURATION ====================
LEVERAGE = 5  # 5x leverage (adjustable: 1-20x depending on exchange)
USE_LEVERAGE = True  # Enable leverage for all trades

# ==================== POSITION SIZING WITH LEVERAGE ====================
STARTING_BALANCE = 3.0  # $3 starting capital
RISK_PER_TRADE = 0.05  # 5% risk per trade

# Dynamic position sizing calculation:
# Effective Buying Power = Starting Capital × Leverage
# Min Trade Size = $5 USDT (Binance minimum)
# With 5x leverage on $3: Can open trades as small as $5 (instead of $15)

# With leverage:
# - $3 capital × 5x = $15 effective buying power
# - Each trade can be $5+ USDT
# - Risk = $3 × 5% = $0.15 per trade

# ==================== TRADING PAIRS ====================
TRADING_PAIRS = [
    'BTC/USDT',
    'ETH/USDT',
    'BNB/USDT',
    'SOL/USDT',
    'XRP/USDT',
    'ADA/USDT',
    'DOGE/USDT',
    'LINK/USDT',
    'AVAX/USDT',
    'ARB/USDT',
]

# ==================== POSITION SIZING ====================
MAX_CONCURRENT_POSITIONS = 5  # Can have 5 open trades with leverage
MIN_POSITION_VALUE_USDT = 5.0  # Binance minimum is ~$5

def calculate_position_size_with_leverage(capital, leverage, risk_percent, entry_price, stop_loss_price):
    """
    Calculate position size considering leverage
    
    With leverage, you can open larger positions with smaller capital:
    - Position Size = (Risk Amount × Leverage) / (Entry - Stop Loss)
    - Risk Amount = Capital × Risk %
    - Effective Capital = Capital × Leverage
    """
    risk_amount = capital * risk_percent
    effective_capital = capital * leverage
    price_diff = abs(entry_price - stop_loss_price)
    
    if price_diff == 0:
        return 0
    
    # Position size considering leverage
    position_size = (risk_amount * leverage) / price_diff
    position_value = position_size * entry_price
    
    # Ensure meets Binance minimum
    if position_value < MIN_POSITION_VALUE_USDT:
        # Adjust to minimum
        position_size = MIN_POSITION_VALUE_USDT / entry_price
        position_value = MIN_POSITION_VALUE_USDT
    
    return {
        'position_size': position_size,
        'position_value': position_value,
        'risk_amount': risk_amount,
        'effective_capital': effective_capital,
        'leverage': leverage
    }

# ==================== STOP LOSS & TAKE PROFIT ====================
STOP_LOSS_PERCENT = 2.0  # 2% stop loss
TAKE_PROFIT_PERCENT = 6.0  # 6% take profit (3:1 risk/reward)

# With leverage, these percentages apply to effective position size
# E.g., 5x leverage on $5 position = $25 effective exposure
# 2% stop loss on $25 = $0.50 loss (10% of $5 capital)

# ==================== TRADING PARAMETERS ====================
TIMEFRAME = '15m'  # 15-minute candles
MAX_TRADE_DURATION_HOURS = 4  # Close positions after 4 hours if not TP/SL
UPDATE_INTERVAL = 60  # Check every 60 seconds

# ==================== MARGIN TRADING FEES ====================
TAKER_FEE = 0.0004  # 0.04% on Binance futures
MAKER_FEE = 0.0002  # 0.02% on Binance futures
FUNDING_RATE = 0.0001  # Approximate daily funding rate (8 hours = 1/3 of funding rate)

# ==================== SAFETY LIMITS ====================
MAX_DAILY_LOSS_PERCENT = 20  # Stop trading if lose 20% in a day with leverage
LIQUIDATION_LEVEL = 0.10  # Close at 10% margin (with 5x leverage, this is critical)
WARNING_LEVEL = 0.30  # Warn at 30% margin usage

# ==================== INDICATOR THRESHOLDS ====================
RSI_OVERSOLD = 25  # Buy signal
RSI_OVERBOUGHT = 75  # Sell signal
MIN_SIGNAL_STRENGTH = 6  # Require strength >= 6
MIN_SIGNAL_COUNT = 2  # Require >= 2 indicators confirming

# ==================== LEVERAGE NOTES ====================
"""
LEVERAGE EXPLAINED:

With 5x Leverage on $3:
- Your buying power becomes $15
- You can open 3 × $5 trades (meeting Binance minimum)
- Each $5 trade is really $25 effective exposure
- If BTC drops 2%, you lose $0.50 (10% of $5 = $0.10 × 5x effect = $0.50)

Risk Management with Leverage:
1. ALWAYS use tight stop losses (2-3%)
2. Monitor margin level constantly
3. Never go below 10% margin (= liquidation)
4. Consider funding costs (interest on borrowed amount)
5. Size positions smaller when using leverage

Example Trade with 5x Leverage on $5:
- Entry: $100 BTC
- Position: 0.05 BTC (= $5 notional, $25 with leverage)
- Stop Loss: $98 (2% below)
- Take Profit: $106 (6% above)
- Risk: $0.10 (2% of $5), but $0.50 on margin account
- Reward: $0.30 (6% of $5), but $1.50 on margin account
- Risk/Reward: 1:3 (excellent)

⚠️ WARNING: Leverage amplifies BOTH gains AND losses!
Only use if you understand the risks.
"""
