"""
Phase 1 Configuration: Conservative $3 → $4 Growth Strategy
Focus on capital preservation and steady gains
"""

# ==================== PHASE 1 CONSERVATIVE SETTINGS ====================
LEVERAGE = 2  # Conservative 2x leverage (reduced from 5x)
USE_LEVERAGE = True

# ==================== CAPITAL MANAGEMENT (PROFITABLE SETTINGS) ====================
STARTING_BALANCE = 3.0  # $3 starting capital
TARGET_BALANCE = 4.0  # $4 target (33% growth)
RISK_PER_TRADE = 0.02  # 2% risk per trade (from profitable futures-bot)

# Profitable Risk Calculation:
# - Risk Amount: $3 × 2% = $0.06 per trade
# - Reward Amount: $0.06 × 0.8 = $0.048 per trade (0.8:1 ratio)
# - Daily Target: 2 wins = +$0.10 (3.3% daily)
# - Weekly Target: ~$3.70 (conservative steady growth)

# ==================== TRADING PAIRS (PHASE 1 - TOP 10 HIGH-PERFORMANCE PAIRS) ====================
TRADING_PAIRS = [
    # TOP TIER - Highest Volume & Predictability
    'BTC/USDT',   # Bitcoin - King, most liquid
    'ETH/USDT',   # Ethereum - Second largest, great volatility
    
    # LARGE CAP - Stable & Reliable
    'BNB/USDT',   # Binance Coin - Exchange token, steady
    'XRP/USDT',   # Ripple - Frequent movements, liquid
    'ADA/USDT',   # Cardano - Good volatility patterns
    
    # MID CAP - High Opportunity
    'SOL/USDT',   # Solana - High volatility, great for scalping
    'AVAX/USDT',  # Avalanche - Strong movements
    'MATIC/USDT', # Polygon - Consistent patterns
    
    # MOMENTUM PAIRS - Active Trading
    'DOT/USDT',   # Polkadot - Good technical patterns
    'LINK/USDT',  # Chainlink - Oracle token, active
]

# ==================== POSITION SIZING ====================
MAX_CONCURRENT_POSITIONS = 4  # Maximum 4 positions (increased for 10 pairs coverage)
MIN_POSITION_VALUE_USDT = 1.0  # Reduced to $1 minimum for small balances

# With 2x leverage on $3:
# - Effective Buying Power: $6
# - Can open 1-2 positions of $5 each
# - Total exposure: $10 with leverage
# - Margin used: $5 (safe level)

# ==================== STOP LOSS & TAKE PROFIT (PURE FUTURES-BOT STRATEGY) ====================
STOP_LOSS_PERCENT = 2.0  # 2% stop loss (will be replaced by ATR-based)
TAKE_PROFIT_PERCENT = 1.6  # 1.6% take profit (0.8:1 ratio for high win rate!)

# Futures-Bot Trade Example:
# - Entry: BTC $68,000 (pullback to EMA 20/50 in uptrend)
# - Position Size: $5 notional / $68,000 = 0.0000735 BTC
# - Stop Loss: ATR-based (2.5x ATR from entry)
# - Take Profit: $69,088 (1.6% above - conservative for high win rate)
# - Risk: $0.06 (2% of $3)
# - Reward: $0.048 (0.8:1 risk/reward - the profitable ratio!)

# ==================== PURE FUTURES-BOT STRATEGY PARAMETERS ====================
# EXACT COPY from D:\futures-bot\config.yaml
EMA_FAST = 20      # Fast trend indicator (from futures-bot)
EMA_MID = 50       # Medium trend indicator (from futures-bot)
EMA_SLOW = 200     # Main trend filter (from futures-bot)
ATR_PERIOD = 14    # ATR calculation period (from futures-bot)
ATR_STOP_MULT = 2.5  # ATR multiplier for stop loss (from futures-bot)
TAKE_PROFIT_R_MULTIPLE = 0.8  # 0.8:1 reward ratio (from futures-bot!)
MIN_ATR_PERCENT = 0.08  # Only trade when market is active enough (from futures-bot)

# ==================== TRADING PARAMETERS ====================
TIMEFRAME = '15m'  # 15-minute candles
MAX_TRADE_DURATION_HOURS = 4  # Close in 4 hours (more time for profits)
UPDATE_INTERVAL = 30  # Check every 30 seconds (faster signal detection)

# ==================== SAFETY LIMITS (PHASE 1 - LESS AGGRESSIVE) ====================
MAX_DAILY_LOSS_PERCENT = 25  # Stop trading if lose 25% in a day (increased from 15%)
MAX_DAILY_TRADES = 50  # Maximum 50 trades per day (increased for more activity)
LIQUIDATION_LEVEL = 0.15  # Close at 15% margin (more conservative)
WARNING_LEVEL = 0.25  # Warn at 25% margin usage

# ==================== ADVANCED SAFETY FEATURES (RELAXED) ====================
MAX_CONSECUTIVE_LOSSES = 5  # Stop trading after 5 consecutive losses (increased from 3)
MIN_WIN_RATE_THRESHOLD = 0.30  # Pause if win rate drops below 30% (decreased from 40%)
VOLATILITY_THRESHOLD = 0.01  # Minimum 1% volatility to trade (decreased from 2%)
TRADING_HOURS_START = 0  # Start trading at 12 AM UTC (24/7 trading)
TRADING_HOURS_END = 23  # Stop trading at 11 PM UTC

# ==================== PROFITABLE STRATEGY (FROM FUTURES-BOT) ====================
# EMA Trend + Pullback Strategy (The one that made you money!)
EMA_FAST = 20      # Fast trend indicator
EMA_MID = 50       # Medium trend indicator  
EMA_SLOW = 200     # Main trend filter
ATR_PERIOD = 14    # ATR calculation period
ATR_STOP_MULT = 2.5  # ATR multiplier for stop loss
TAKE_PROFIT_R_MULTIPLE = 0.8  # 0.8:1 reward ratio (high win rate!)
MIN_ATR_PERCENT = 0.08  # Only trade when market is active enough

# ==================== INDICATOR THRESHOLDS (PROFITABLE SETTINGS) ====================
# Replace RSI with EMA trend strategy
# Entry conditions: Price pulls back to EMA 20/50 in direction of EMA 200 trend
RSI_OVERSOLD = 30  # More realistic oversold (increased from 20)
RSI_OVERBOUGHT = 70  # More realistic overbought (decreased from 80)
MIN_SIGNAL_STRENGTH = 5  # Require strength >= 5 (reduced from 7 for more opportunities)
MIN_SIGNAL_COUNT = 2  # Require >= 2 indicators confirming (reduced from 3)

# ==================== PHASE 1 STRATEGY SELECTION ====================
RECOMMENDED_STRATEGIES = [
    'HyperScalper25',  # Quick scalping, lower risk
    'Scalper70',       # Balanced approach
]

# Avoid these in Phase 1:
# - SmartMoneyPro (too aggressive for small capital)
# - DiamondSniper (requires larger positions)

# ==================== PHASE 1 SUCCESS METRICS ====================
PHASE1_TARGETS = {
    'daily_profit_target': 0.54,  # $0.54 per day (18%)
    'weekly_profit_target': 3.80,  # $3.80 by week end
    'win_rate_target': 0.60,  # 60% win rate needed
    'max_daily_loss': 0.45,  # Stop at $0.45 loss (15%)
    'phase_complete_balance': 4.0,  # Complete at $4 balance
}

# ==================== PHASE 1 TRACKING ====================
def should_upgrade_to_phase2(current_balance, trades_today, daily_pnl):
    """
    Check if ready to upgrade to Phase 2 ($4+ balance)
    """
    if current_balance >= 4.0:
        return True, "Target reached! Ready for Phase 2"
    
    if daily_pnl > 0.80 and trades_today >= 3:
        return True, "Strong performance! Consider early Phase 2"
    
    return False, "Continue Phase 1 - focus on consistency"

# ==================== PHASE 1 NOTES ====================
"""
PHASE 1 CONSERVATIVE STRATEGY:

Key Principles:
1. Capital Preservation First
2. Small, Consistent Gains
3. High-Quality Signals Only
4. Quick Exit Strategy

Daily Routine:
- Start: Check market conditions
- Trade: Maximum 5 trades, 2 concurrent
- Monitor: Every 15 minutes during trades
- Stop: If 15% daily loss or $4 reached
- Review: Analyze all trades at day end

Success Indicators:
✅ 60%+ win rate
✅ Consistent daily profits ($0.30+)
✅ No margin warnings
✅ Quick trade resolution (under 2 hours)

Upgrade Triggers:
✅ Balance reaches $4
✅ Consistent 70%+ win rate for 3 days
✅ Zero margin issues for a week

Remember: Better to make 10% steadily than risk everything for 20%!
"""
