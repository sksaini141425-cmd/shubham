import os
import logging
from bot.data_loader import DataLoader
from bot.strategy import HyperScalper25Strategy

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("HyperBacktester")

def run_hyper_backtest():
    print("🚀 Starting HYPER-GROWTH Backtest (Last 1000 Candles)...")
    print("💰 Initial Capital: $3.00")
    print("🎯 Target: $25.00")
    print("🛠️ Strategy: HyperScalper25 (Compounding + 50x Leverage)")
    print("-" * 60)

    data_loader = DataLoader()
    strategy = HyperScalper25Strategy(leverage=50)
    
    # Use top 10 most liquid pairs
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 
               'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'DOTUSDT']
    
    current_capital = 3.0
    total_trades = 0
    wins = 0
    trade_history = []

    # Combine all signals from all symbols and sort by time to simulate realistic sequential trading
    all_signals = []
    for symbol in symbols:
        candles = data_loader.fetch_ohlcv(symbol, timeframe='5m', limit=1000)
        if not candles: continue
        candles = strategy.calculate_indicators(candles)
        candles = strategy.generate_signals(candles)
        for c in candles[200:]: # Skip warm-up
            c['symbol'] = symbol
            all_signals.append(c)
    
    # Sort by timestamp to trade sequentially
    all_signals.sort(key=lambda x: x['timestamp'])

    active_trade = None
    
    for c in all_signals:
        if current_capital <= 0.1: # Liquidated or out of funds
            break

        signal = c.get('signal', 'NONE')
        symbol = c['symbol']
        price = c['close']

        # 1. Check for Exit
        if active_trade and active_trade['symbol'] == symbol:
            entry_price = active_trade['entry_price']
            side = active_trade['side']
            
            pnl_pct = (price - entry_price) / entry_price if side == 'LONG' else (entry_price - price) / entry_price
            
            # Exit Conditions:
            # 1. TP: 2.5% move (125% gain at 50x)
            # 2. SL: 1.0% move (50% loss at 50x)
            # 3. Opposite signal
            exit_reason = None
            if pnl_pct >= 0.025: exit_reason = "TP 🎯"
            elif pnl_pct <= -0.01: exit_reason = "SL 🛑"
            elif (side == 'LONG' and signal == 'SHORT') or (side == 'SHORT' and signal == 'LONG'):
                exit_reason = "REVERSAL 🔄"

            if exit_reason:
                leverage = 50
                fee = 0.001 # 0.1% round-trip fee
                net_pnl_pct = (pnl_pct * leverage) - fee
                
                trade_pnl = current_capital * net_pnl_pct
                current_capital += trade_pnl
                
                total_trades += 1
                if trade_pnl > 0: wins += 1
                
                trade_history.append({
                    'symbol': symbol,
                    'side': side,
                    'pnl': trade_pnl,
                    'capital': current_capital,
                    'reason': exit_reason
                })
                
                # print(f"  ✅ Closed {side} {symbol} at ${price:.4f} | PnL: ${trade_pnl:+.2f} | Bal: ${current_capital:.2f} ({exit_reason})")
                active_trade = None

        # 2. Check for Entry (Only one trade at a time to maximize compounding)
        if not active_trade and signal in ['LONG', 'SHORT']:
            active_trade = {
                'symbol': symbol,
                'side': signal,
                'entry_price': price,
                'timestamp': c['timestamp']
            }
            # print(f"  🚀 Open {signal} {symbol} at ${price:.4f} (Bal: ${current_capital:.2f})")

    print("-" * 60)
    print("🏆 HYPER-GROWTH FINAL RESULTS")
    print(f"💰 Starting Capital: $3.00")
    print(f"💵 Ending Capital: ${max(0, current_capital):.2f}")
    print(f"📈 Total Growth: {((current_capital - 3.0) / 3.0 * 100):+.1f}%")
    print(f"📊 Total Trades: {total_trades}")
    print(f"🎯 Win Rate: {(wins/total_trades*100) if total_trades > 0 else 0:.1f}%")
    print(f"🚀 Peak Capital: ${max([h['capital'] for h in trade_history] + [3.0]):.2f}")
    print("-" * 60)

if __name__ == "__main__":
    run_hyper_backtest()
