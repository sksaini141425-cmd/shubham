import os
import logging
from bot.data_loader import DataLoader
from bot.strategy import DiamondSniperStrategy

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("DiamondBacktester")

def run_diamond_backtest():
    print("💎 Starting DIAMOND SNIPER Backtest (Last 1000 Candles)...")
    print("💰 Initial Capital: $3.00")
    print("🎯 Target: Massive Explosive Profits")
    print("🛠️ Strategy: Diamond Sniper (BB Squeeze + Vol Breakout + 50x)")
    print("-" * 65)

    data_loader = DataLoader()
    strategy = DiamondSniperStrategy(leverage=50)
    
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 
               'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'DOTUSDT']
    
    current_capital = 3.0
    total_trades = 0
    wins = 0
    trade_history = []

    all_signals = []
    for symbol in symbols:
        candles = data_loader.fetch_ohlcv(symbol, timeframe='5m', limit=1000)
        if not candles: continue
        candles = strategy.calculate_indicators(candles)
        candles = strategy.generate_signals(candles)
        for c in candles[50:]: # Skip warm-up
            c['symbol'] = symbol
            all_signals.append(c)
    
    all_signals.sort(key=lambda x: x['timestamp'])

    active_trade = None
    
    for c in all_signals:
        if current_capital <= 0.1: break

        signal = c.get('signal', 'NONE')
        symbol = c['symbol']
        price = c['close']

        if active_trade and active_trade['symbol'] == symbol:
            entry_price = active_trade['entry_price']
            side = active_trade['side']
            
            pnl_pct = (price - entry_price) / entry_price if side == 'LONG' else (entry_price - price) / entry_price
            
            # Exit Conditions:
            # 1. TP: 5% move (250% gain at 50x) - Looking for bigger "explosions"
            # 2. SL: 1.0% move (50% loss at 50x)
            # 3. Reversal signal
            exit_reason = None
            if pnl_pct >= 0.05: exit_reason = "EXPLOSION 🌋"
            elif pnl_pct <= -0.01: exit_reason = "STOP 🛑"
            elif (side == 'LONG' and signal == 'SHORT') or (side == 'SHORT' and signal == 'LONG'):
                exit_reason = "REVERSAL 🔄"

            if exit_reason:
                leverage = 50
                fee = 0.001
                net_pnl_pct = (pnl_pct * leverage) - fee
                
                trade_pnl = current_capital * net_pnl_pct
                current_capital += trade_pnl
                
                total_trades += 1
                if trade_pnl > 0: wins += 1
                
                trade_history.append({
                    'symbol': symbol, 'side': side, 'pnl': trade_pnl, 'capital': current_capital, 'reason': exit_reason
                })
                active_trade = None

        if not active_trade and signal in ['LONG', 'SHORT']:
            active_trade = {'symbol': symbol, 'side': signal, 'entry_price': price, 'timestamp': c['timestamp']}

    print("-" * 65)
    print("🏆 DIAMOND SNIPER FINAL RESULTS")
    print(f"💰 Starting Capital: $3.00")
    print(f"💵 Ending Capital: ${max(0, current_capital):.2f}")
    print(f"📈 Total Growth: {((current_capital - 3.0) / 3.0 * 100):+.1f}%")
    print(f"📊 Total Trades: {total_trades}")
    print(f"🎯 Win Rate: {(wins/total_trades*100) if total_trades > 0 else 0:.1f}%")
    print(f"💎 Peak Capital: ${max([h['capital'] for h in trade_history] + [3.0]):.2f}")
    print("-" * 65)

if __name__ == "__main__":
    run_diamond_backtest()
