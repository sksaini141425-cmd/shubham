import os
import logging
from datetime import datetime
from bot.data_loader import DataLoader
from bot.strategy import Scalper70Strategy, DiamondSniperStrategy

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("Backtester")

def simulate_trades(symbol, candles, strategy, leverage=20, initial_capital=3.0):
    # Calculate signals
    candles = strategy.calculate_indicators(candles)
    candles = strategy.generate_signals(candles)

    # Simulation state
    in_position = False
    entry_price = 0
    side = None
    capital = initial_capital
    trades = 0
    wins = 0
    total_pnl = 0
    
    # Simple trailing SL logic for backtest
    trailing_sl_pct = -0.015 # 1.5% base SL
    
    for i in range(200, len(candles)):
        if capital <= 0.1: break # Bankrupt
        
        c = candles[i]
        price = c['close']
        signal = c.get('signal', 'NONE')

        if not in_position:
            if signal in ['LONG', 'SHORT']:
                in_position = True
                entry_price = price
                side = signal
                trades += 1
                trailing_sl_pct = -0.015 # Reset SL
        else:
            # Calculate PnL %
            pnl_pct = (price - entry_price) / entry_price if side == 'LONG' else (entry_price - price) / entry_price
            
            # Professional Trailing SL (from main.py logic)
            if pnl_pct >= 0.004 and trailing_sl_pct < 0.001:
                trailing_sl_pct = 0.001
            if pnl_pct >= 0.008:
                potential_sl = pnl_pct * 0.5
                if potential_sl > trailing_sl_pct: trailing_sl_pct = potential_sl
            if pnl_pct >= 0.012:
                potential_sl = pnl_pct * 0.7
                if potential_sl > trailing_sl_pct: trailing_sl_pct = potential_sl

            # Exit Conditions
            exit_reason = None
            if pnl_pct >= 0.03: exit_reason = "TP 🎯"
            elif pnl_pct <= trailing_sl_pct: exit_reason = "SL/Trailing 🛑"
            elif (side == 'LONG' and signal == 'SHORT') or (side == 'SHORT' and signal == 'LONG'):
                exit_reason = "REVERSAL 🔄"

            if exit_reason:
                # Calculate final trade PnL with leverage
                fee = 0.001 # 0.1% round-trip fee
                net_trade_pnl_pct = (pnl_pct * leverage) - fee
                
                trade_pnl = capital * net_trade_pnl_pct
                capital += trade_pnl
                total_pnl += trade_pnl
                if trade_pnl > 0: wins += 1
                
                in_position = False

    return {
        'symbol': symbol,
        'final_capital': round(capital, 2),
        'total_pnl': round(total_pnl, 2),
        'trades': trades,
        'win_rate': round((wins/trades*100) if trades > 0 else 0, 1)
    }

def run_comparison():
    print("🚀 STARTING STRATEGY COMPARISON (2000 CANDLES / 10 PAIRS)")
    print("💰 Initial Capital: $3.00")
    print("-" * 60)

    data_loader = DataLoader()
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 
               'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'DOTUSDT']
    
    # Strategies to test
    strategies = {
        "Scalper70 (Current)": Scalper70Strategy(leverage=20),
        "DiamondSniper (Squeeze)": DiamondSniperStrategy(leverage=20)
    }

    all_results = {}

    for name, strat in strategies.items():
        print(f"\n📊 Testing {name}...")
        results = []
        for symbol in symbols:
            # print(f"  Fetching {symbol} data...")
            candles = data_loader.fetch_ohlcv(symbol, timeframe='5m', limit=2000)
            if not candles: continue
            
            res = simulate_trades(symbol, candles, strat)
            results.append(res)
            # print(f"    {symbol}: ${res['total_pnl']:+.2f} PnL ({res['trades']} trades)")

        # Aggregate Results
        total_pnl = sum(r['total_pnl'] for r in results)
        total_trades = sum(r['trades'] for r in results)
        total_wins = sum( (r['win_rate']/100 * r['trades']) for r in results )
        avg_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
        
        all_results[name] = {
            'pnl': total_pnl,
            'trades': total_trades,
            'win_rate': avg_win_rate
        }

    print("\n" + "=" * 60)
    print("🏆 FINAL COMPARISON RESULTS (PAST 2000 CANDLES)")
    print("=" * 60)
    
    # Sort by PnL
    sorted_results = sorted(all_results.items(), key=lambda x: x[1]['pnl'], reverse=True)
    
    for i, (name, data) in enumerate(sorted_results):
        rank = "🥇" if i == 0 else "🥈"
        print(f"{rank} {name}")
        print(f"   💰 Total PnL: ${data['pnl']:+.2f}")
        print(f"   🎯 Win Rate: {data['win_rate']:.1f}%")
        print(f"   📊 Total Trades: {data['trades']}")
        print("-" * 30)

    print("\n💡 RECOMMENDATION:")
    winner = sorted_results[0][0]
    if winner == "Scalper70 (Current)":
        print("Our current strategy is performing best! Keep it active.")
    else:
        print(f"The {winner} strategy is performing better. We should consider switching.")
    print("=" * 60)

if __name__ == "__main__":
    run_comparison()
