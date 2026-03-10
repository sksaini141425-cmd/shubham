import os
import logging
from datetime import datetime
from bot.data_loader import DataLoader
from bot.strategy import Scalper70Strategy
from bot.paper_exchange import PaperAccount

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("Backtester")

def run_backtest():
    print("🧪 Starting Historical Backtest (Last 1000 Candles)...")
    print("💰 Initial Capital: $3.00")
    print("🛠️ Strategy: Scalper70")
    print("-" * 50)

    data_loader = DataLoader()
    strategy = Scalper70Strategy(leverage=20)
    
    # Use top 10 pairs
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 
               'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'DOTUSDT']
    
    global_results = []
    total_net_pnl = 0
    total_trades = 0
    wins = 0

    for symbol in symbols:
        print(f"📊 Analyzing {symbol}...")
        candles = data_loader.fetch_ohlcv(symbol, timeframe='5m', limit=1000)
        if not candles:
            print(f"❌ Failed to fetch data for {symbol}")
            continue

        # Calculate signals for all 1000 candles
        candles = strategy.calculate_indicators(candles)
        candles = strategy.generate_signals(candles)

        # Simulate trading over these candles
        in_position = False
        entry_price = 0
        side = None
        
        symbol_pnl = 0
        symbol_trades = 0
        
        for i in range(200, len(candles)): # Start after indicators warm up
            c = candles[i]
            signal = c.get('signal', 'NONE')

            if not in_position and signal in ['LONG', 'SHORT']:
                # Open position
                in_position = True
                entry_price = c['close']
                side = signal
                symbol_trades += 1
                total_trades += 1
                # print(f"  🚀 {side} Entry at ${entry_price:.4f}")

            elif in_position:
                # Simple Exit Logic for Backtest: 
                # Exit on opposite signal or 3% TP / 1.5% SL
                price = c['close']
                pnl_pct = (price - entry_price) / entry_price if side == 'LONG' else (entry_price - price) / entry_price
                
                # Apply leverage impact (20x)
                exit_reason = None
                if pnl_pct >= 0.03: exit_reason = "TP 🎯"
                elif pnl_pct <= -0.015: exit_reason = "SL 🛑"
                elif (side == 'LONG' and signal == 'SHORT') or (side == 'SHORT' and signal == 'LONG'):
                    exit_reason = "REVERSAL 🔄"

                if exit_reason:
                    fee = 0.001 # 0.1% round-trip fee
                    net_pnl_pct = (pnl_pct * 20) - fee
                    trade_pnl = 3.0 * net_pnl_pct
                    
                    symbol_pnl += trade_pnl
                    total_net_pnl += trade_pnl
                    if trade_pnl > 0: wins += 1
                    
                    # print(f"  ✅ Closed {side} at ${price:.4f} | PnL: ${trade_pnl:.2f} ({exit_reason})")
                    in_position = False

        print(f"  📈 Result: ${symbol_pnl:+.2f} PnL from {symbol_trades} trades.")

    print("-" * 50)
    print("🏆 FINAL BACKTEST RESULTS (Last 1000 Candles)")
    print(f"💰 Ending Capital: ${3.0 + total_net_pnl:.2f}")
    print(f"💵 Total Net PnL: ${total_net_pnl:+.2f}")
    print(f"📊 Total Trades: {total_trades}")
    print(f"🎯 Win Rate: {(wins/total_trades*100) if total_trades > 0 else 0:.1f}%")
    print("-" * 50)

if __name__ == "__main__":
    run_backtest()
