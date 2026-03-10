import os
import logging
from bot.data_loader import DataLoader
from bot.strategy import HyperScalper25Strategy

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("SeriousBacktester")

def run_serious_backtest():
    print("🔥 Starting ULTIMATE SERIOUS Backtest (Last 1000 Candles)...")
    print("💰 Initial Capital: $3.00")
    print("🎯 Strategy: HyperScalper25 (50x Leverage)")
    print("⚠️ Rules: Margin Locking + Fees + Real-Time Liquidation")
    print("-" * 70)

    data_loader = DataLoader()
    strategy = HyperScalper25Strategy(leverage=50)
    
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 
               'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'DOTUSDT']
    
    available_cash = 3.0
    total_trades = 0
    wins = 0
    liquidations = 0
    trade_history = []

    # 1. Fetch and Prepare Data
    all_signals = []
    for symbol in symbols:
        candles = data_loader.fetch_ohlcv(symbol, timeframe='5m', limit=1000)
        if not candles: continue
        candles = strategy.calculate_indicators(candles)
        candles = strategy.generate_signals(candles)
        for c in candles[200:]: # Skip warm-up
            c['symbol'] = symbol
            all_signals.append(c)
    
    all_signals.sort(key=lambda x: x['timestamp'])

    # 2. Simulate Trading
    active_trade = None
    
    for c in all_signals:
        if available_cash <= 0.1: # Bankrupt
            break

        signal = c.get('signal', 'NONE')
        symbol = c['symbol']
        price = c['close']

        # --- Check Active Trade ---
        if active_trade and active_trade['symbol'] == symbol:
            entry_price = active_trade['entry_price']
            side = active_trade['side']
            margin = active_trade['margin']
            
            # Calculate PnL (Unrealized)
            pnl = 0
            if side == 'LONG':
                pnl = (price - entry_price) * active_trade['size']
            else:
                pnl = (entry_price - price) * active_trade['size']
            
            # --- LIQUIDATION CHECK (Serious Rule) ---
            if pnl <= -(margin * 0.9):
                liquidations += 1
                liq_fee = (active_trade['size'] * price * 0.001) # High liquidation fee
                available_cash += (margin + pnl - liq_fee)
                
                trade_history.append({'symbol': symbol, 'pnl': pnl - liq_fee, 'capital': available_cash, 'reason': 'LIQUIDATED 🔥'})
                active_trade = None
                continue

            # --- EXIT CONDITIONS ---
            exit_reason = None
            pnl_pct = pnl / (active_trade['size'] * entry_price)
            
            if pnl_pct >= 0.02: exit_reason = "TP 🎯" # 100% gain at 50x
            elif pnl_pct <= -0.01: exit_reason = "SL 🛑" # 50% loss at 50x
            elif (side == 'LONG' and signal == 'SHORT') or (side == 'SHORT' and signal == 'LONG'):
                exit_reason = "REVERSAL 🔄"

            if exit_reason:
                exit_fee = (active_trade['size'] * price * 0.0005)
                # Return Margin + PnL - Fee
                available_cash += (margin + pnl - exit_fee)
                
                total_trades += 1
                if (pnl - exit_fee) > 0: wins += 1
                
                trade_history.append({
                    'symbol': symbol, 'pnl': pnl - exit_fee, 'capital': available_cash, 'reason': exit_reason
                })
                active_trade = None

        # --- OPEN NEW TRADE ---
        if not active_trade and signal in ['LONG', 'SHORT'] and available_cash > 0.5:
            # Sizing: Use 80% of available cash for the next trade (compounding)
            risk_amount = available_cash * 0.8
            leverage = 50
            notional = risk_amount * leverage
            
            # Deduction: Lock Margin + Pay Entry Fee
            entry_fee = notional * 0.0005
            available_cash -= (risk_amount + entry_fee)
            
            active_trade = {
                'symbol': symbol,
                'side': signal,
                'entry_price': price,
                'size': notional / price,
                'margin': risk_amount,
                'timestamp': c['timestamp']
            }

    print("-" * 70)
    print("🏆 ULTIMATE SERIOUS RESULTS")
    print(f"💰 Starting Capital: $3.00")
    print(f"💵 Ending Capital: ${max(0, available_cash):.2f}")
    print(f"📈 Total Growth: {((available_cash - 3.0) / 3.0 * 100):+.1f}%")
    print(f"📊 Total Trades: {total_trades}")
    print(f"🎯 Win Rate: {(wins/total_trades*100) if total_trades > 0 else 0:.1f}%")
    print(f"🔥 Liquidations: {liquidations}")
    print(f"🚀 Peak Capital: ${max([h['capital'] for h in trade_history] + [3.0]):.2f}")
    print("-" * 70)

if __name__ == "__main__":
    run_serious_backtest()
