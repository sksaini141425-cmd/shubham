import os
import logging
import math
from datetime import datetime, timedelta
from bot.data_loader import DataLoader
from bot.strategy import SmartMoneyStrategy, SmartMoneyDynamicStrategy
from bot.paper_exchange import PaperAccount, PaperExchange

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("Backtester")

def run_backtest():
    print("🧪 Starting Historical Backtest for Smart Money DYNAMIC...")
    print("💰 Initial Capital: $3.00")
    print("🛠️ Timeframe: 5m (Last 2000 Candles)")
    print("-" * 60)

    data_loader = DataLoader()
    strategy = SmartMoneyDynamicStrategy(leverage=20)
    
    # Use top 10 most liquid pairs
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT', 
               'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'DOTUSDT']
    
    total_trades = 0
    wins = 0
    total_net_pnl = 0
    initial_cap = 3.00
    leverage = 20
    tp_pct = 0.04  # 4% Net
    sl_pct_limit = -0.03 # 3% Net Max
    round_trip_fee = 0.001 # 0.1% total fees

    for symbol in symbols:
        print(f"📊 Analyzing {symbol}...")
        candles = data_loader.fetch_ohlcv(symbol, timeframe='5m', limit=2000)
        if not candles:
            print(f"❌ Failed to fetch data for {symbol}")
            continue

        # Calculate indicators and signals
        candles = strategy.calculate_indicators(candles)
        candles = strategy.generate_signals(candles)

        in_position = False
        entry_price = 0
        side = None
        entry_time = None
        symbol_trades = 0
        symbol_pnl = 0
        capital_per_trade = 1.50 
        
        for i in range(200, len(candles)):
            c, prev = candles[i], candles[i-1]
            signal = c.get('signal', 'NONE')
            price = c['close']
            
            # DYNAMIC EXIT RULES
            ema9, ema21 = c.get('EMA_9'), c.get('EMA_21')

            if not in_position:
                if signal in ['LONG', 'SHORT']:
                    in_position = True
                    side = signal
                    entry_price = price
                    entry_time = c['timestamp']
                    symbol_trades += 1
                    total_trades += 1
            else:
                raw_pnl_pct = (price - entry_price) / entry_price if side == 'LONG' else (entry_price - price) / entry_price
                net_pnl_pct = (raw_pnl_pct * leverage) - round_trip_fee
                
                exit_reason = None
                
                # 1. Take Profit / Stop Loss
                if net_pnl_pct >= tp_pct: exit_reason = "TP 🎯"
                elif net_pnl_pct <= sl_pct_limit: exit_reason = "SL 🛑"
                
                # 2. DYNAMIC EXIT: EMA Re-cross
                elif side == 'LONG' and ema9 < ema21: exit_reason = "EMA CROSS 🔄"
                elif side == 'SHORT' and ema9 > ema21: exit_reason = "EMA CROSS 🔄"

                if exit_reason:
                    trade_pnl = capital_per_trade * net_pnl_pct
                    symbol_pnl += trade_pnl
                    total_net_pnl += trade_pnl
                    if trade_pnl > 0: wins += 1
                    in_position = False

        print(f"  📈 Result: ${symbol_pnl:+.2f} PnL from {symbol_trades} trades.")

    print("-" * 60)
    print("🏆 BACKTEST SUMMARY: SMART MONEY SCALPER")
    print(f"💰 Ending Balance: ${initial_cap + total_net_pnl:.2f}")
    print(f"💵 Total Profit: ${total_net_pnl:+.2f}")
    print(f"📊 Total Trades: {total_trades}")
    print(f"🎯 Win Rate: {(wins/total_trades*100) if total_trades > 0 else 0:.1f}%")
    
    if total_trades > 0:
        avg_trade = (total_net_pnl / total_trades) / capital_per_trade * 100
        print(f"⚡ Avg Trade: {avg_trade:+.2f}% (Net per trade)")
    
    print("-" * 60)

if __name__ == "__main__":
    run_backtest()
