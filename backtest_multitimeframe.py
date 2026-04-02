#!/usr/bin/env python3
"""
Comprehensive Backtest for Multi-Timeframe Scalper Strategy
Compares performance against Scalper30 strategy over 6 months of BTC data.
"""
import os
import sys
import json
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from bot.data_loader import DataLoader
from bot.strategy_optimized import Scalper30Strategy
from bot.strategy_multitimeframe import MultiTimeframeScalperStrategy
from bot.paper_exchange import PaperExchange, PaperAccount

def fetch_historical_data(symbol="BTCUSDT", months=6):
    """Fetch 6 months of historical data for backtesting"""
    print(f"📊 Fetching {months} months of {symbol} data...")
    
    # Use DataLoader to get historical data
    data_loader = DataLoader(exchange_id='mexc', testnet=False)
    
    # For backtesting, we'll use 1-minute candles
    # Calculate start date
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=months*30)
    
    print(f"📅 Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    try:
        # Get historical data (this is a simplified approach)
        # In reality, you'd need to implement proper historical data fetching
        data = data_loader.get_historical_data(symbol, timeframe='1m', limit=100000)
        
        if not data:
            print("❌ No data fetched. Using simulated data for demonstration.")
            return generate_simulated_data(months)
            
        print(f"✅ Fetched {len(data)} candles")
        return data
        
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        print("📊 Using simulated data for demonstration.")
        return generate_simulated_data(months)

def generate_simulated_data(months=6):
    """Generate realistic simulated BTC data for backtesting"""
    print("🎲 Generating simulated BTC data...")
    
    # Generate 6 months of 1-minute data
    minutes_per_day = 24 * 60
    total_minutes = minutes_per_day * 30 * months
    
    data = []
    base_price = 40000  # Starting price
    
    for i in range(total_minutes):
        # Simulate realistic price movement
        if i % (24 * 60) == 0:  # Daily reset
            daily_change = (hash(i) % 100 - 50) / 10000  # -0.5% to +0.5% daily
            base_price *= (1 + daily_change)
        
        # Intraday volatility
        minute_change = (hash(i * 2) % 200 - 100) / 100000  # -0.1% to +0.1%
        price = base_price * (1 + minute_change)
        
        # Generate OHLC
        high = price * (1 + abs(hash(i * 3) % 100) / 10000)
        low = price * (1 - abs(hash(i * 4) % 100) / 10000)
        open_price = low + (high - low) * (hash(i * 5) % 100) / 100
        close = price
        
        # Volume simulation
        volume = 1000000 + (hash(i * 6) % 500000)
        
        data.append({
            'timestamp': datetime.utcnow() - timedelta(minutes=total_minutes - i),
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })
    
    print(f"✅ Generated {len(data)} simulated candles")
    return data

def backtest_strategy(strategy, data, initial_capital=5.0, strategy_name="Strategy"):
    """Backtest a strategy on historical data"""
    print(f"🔄 Backtesting {strategy_name}...")
    
    # Initialize paper account
    account = PaperAccount(initial_capital=initial_capital, log_file=f"backtest_{strategy_name.lower().replace('-', '_')}.json")
    exchange = PaperExchange(initial_capital=initial_capital)
    exchange.leverage = strategy.leverage
    
    # Track performance
    trades = []
    equity_curve = [initial_capital]
    current_equity = initial_capital
    
    # Process data
    for i in range(100, len(data)):  # Start after enough data for indicators
        current_data = data[:i+1]
        current_candle = data[i]
        
        # Calculate indicators
        current_data = strategy.calculate_indicators(current_data)
        
        # Generate signals
        current_data = strategy.generate_signals(current_data)
        
        # Check for signals
        signal = current_data[-1].get('signal', 'NONE')
        current_price = current_candle['close']
        current_time = current_candle['timestamp']
        
        # Entry logic
        if signal in ['LONG', 'SHORT'] and not exchange.is_in_position:
            # Calculate position size
            stop_loss = strategy.calculate_stop_loss(current_price, signal, current_data[-1].get('ATR'))
            take_profit = strategy.calculate_take_profit(current_price, signal, current_data[-1].get('ATR'))
            
            position_size = strategy.calculate_position_size(
                current_equity, current_price, stop_loss
            )
            
            if position_size > 0:
                # Execute trade
                success = exchange.execute_market_order(signal, position_size, current_price, current_time)
                
                if success:
                    trade = {
                        'entry_time': current_time,
                        'entry_price': current_price,
                        'side': signal,
                        'size': position_size,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'strategy': strategy_name
                    }
                    trades.append(trade)
        
        # Exit logic
        elif exchange.is_in_position:
            position = {
                'side': exchange.position_direction,
                'entry_price': exchange.entry_price,
                'stop_loss': exchange.stop_loss,
                'take_profit': exchange.take_profit
            }
            
            should_exit, reason = strategy.should_exit_position(
                position, current_data[-1], exchange.entry_time, current_time
            )
            
            if should_exit:
                # Close position
                success = exchange.close_position(current_price, current_time)
                
                if success:
                    # Update trade record
                    if trades:
                        last_trade = trades[-1]
                        last_trade.update({
                            'exit_time': current_time,
                            'exit_price': current_price,
                            'exit_reason': reason,
                            'pnl': exchange.get_unrealized_pnl(current_price),
                            'pnl_pct': ((current_price - last_trade['entry_price']) / last_trade['entry_price'] * 100) if last_trade['side'] == 'LONG' else ((last_trade['entry_price'] - current_price) / last_trade['entry_price'] * 100)
                        })
        
        # Update equity curve
        if exchange.is_in_position:
            unrealized_pnl = exchange.get_unrealized_pnl(current_price)
            current_equity = account.get_cash() + unrealized_pnl
        else:
            current_equity = account.get_cash()
        
        equity_curve.append(current_equity)
    
    # Calculate performance metrics
    total_trades = len(trades)
    winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
    losing_trades = [t for t in trades if t.get('pnl', 0) < 0]
    
    win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
    total_pnl = sum(t.get('pnl', 0) for t in trades)
    avg_win = sum(t.get('pnl', 0) for t in winning_trades) / len(winning_trades) if winning_trades else 0
    avg_loss = sum(t.get('pnl', 0) for t in losing_trades) / len(losing_trades) if losing_trades else 0
    
    max_drawdown = 0
    peak = initial_capital
    for equity in equity_curve:
        if equity > peak:
            peak = equity
        drawdown = (peak - equity) / peak * 100
        max_drawdown = max(max_drawdown, drawdown)
    
    final_equity = equity_curve[-1] if equity_curve else initial_capital
    total_return = (final_equity - initial_capital) / initial_capital * 100
    
    return {
        'strategy_name': strategy_name,
        'total_trades': total_trades,
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'total_return': total_return,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'max_drawdown': max_drawdown,
        'final_equity': final_equity,
        'equity_curve': equity_curve,
        'trades': trades
    }

def compare_strategies(results, months=6):
    """Compare backtest results and generate report"""
    print("\n" + "="*80)
    print("📊 STRATEGY COMPARISON REPORT")
    print("="*80)
    
    for result in results:
        print(f"\n🎯 {result['strategy_name']}")
        print("-" * 40)
        print(f"Total Trades: {result['total_trades']}")
        print(f"Win Rate: {result['win_rate']:.1f}%")
        print(f"Total Return: {result['total_return']:.2f}%")
        print(f"Total P&L: ${result['total_pnl']:.2f}")
        print(f"Final Equity: ${result['final_equity']:.2f}")
        print(f"Average Win: ${result['avg_win']:.3f}")
        print(f"Average Loss: ${result['avg_loss']:.3f}")
        print(f"Max Drawdown: {result['max_drawdown']:.2f}%")
    
    # Determine winner
    best_strategy = max(results, key=lambda x: x['total_return'])
    print(f"\n🏆 BEST PERFORMER: {best_strategy['strategy_name']}")
    print(f"   Total Return: {best_strategy['total_return']:.2f}%")
    print(f"   Win Rate: {best_strategy['win_rate']:.1f}%")
    
    return best_strategy

def create_visualization(results, months=6):
    """Create comparison charts"""
    print("\n📈 Generating comparison charts...")
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle(f'Strategy Comparison - {months} Months Backtest', fontsize=16)
    
    # Equity Curve
    ax1 = axes[0, 0]
    for result in results:
        equity = result['equity_curve']
        ax1.plot(equity, label=result['strategy_name'], linewidth=2)
    ax1.set_title('Equity Curve')
    ax1.set_xlabel('Time (candles)')
    ax1.set_ylabel('Equity ($)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Win Rate Comparison
    ax2 = axes[0, 1]
    strategies = [r['strategy_name'] for r in results]
    win_rates = [r['win_rate'] for r in results]
    colors = ['#2ecc71' if wr >= 50 else '#e74c3c' for wr in win_rates]
    ax2.bar(strategies, win_rates, color=colors)
    ax2.set_title('Win Rate Comparison')
    ax2.set_ylabel('Win Rate (%)')
    ax2.axhline(y=50, color='black', linestyle='--', alpha=0.5, label='50% Break-even')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Total Return Comparison
    ax3 = axes[1, 0]
    total_returns = [r['total_return'] for r in results]
    colors = ['#2ecc71' if tr >= 0 else '#e74c3c' for tr in total_returns]
    ax3.bar(strategies, total_returns, color=colors)
    ax3.set_title('Total Return Comparison')
    ax3.set_ylabel('Return (%)')
    ax3.axhline(y=0, color='black', linestyle='-', alpha=0.5)
    ax3.grid(True, alpha=0.3)
    
    # Max Drawdown Comparison
    ax4 = axes[1, 1]
    max_drawdowns = [r['max_drawdown'] for r in results]
    ax4.bar(strategies, max_drawdowns, color='#e74c3c')
    ax4.set_title('Max Drawdown Comparison')
    ax4.set_ylabel('Drawdown (%)')
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('strategy_comparison.png', dpi=300, bbox_inches='tight')
    print("✅ Chart saved as 'strategy_comparison.png'")
    
    # Save detailed results
    with open('backtest_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print("✅ Detailed results saved as 'backtest_results.json'")

def main():
    print("🚀 Starting Comprehensive Strategy Backtest")
    print("="*50)
    
    # Fetch historical data
    data = fetch_historical_data("BTCUSDT", months=6)
    
    if not data:
        print("❌ No data available for backtesting")
        return
    
    # Initialize strategies
    scalper30 = Scalper30Strategy(leverage=30)
    multitimeframe = MultiTimeframeScalperStrategy(leverage=5)
    
    # Run backtests
    results = []
    
    # Test Scalper30
    scalper30_result = backtest_strategy(
        scalper30, data, initial_capital=5.0, strategy_name="Scalper30"
    )
    results.append(scalper30_result)
    
    # Test Multi-Timeframe
    multitimeframe_result = backtest_strategy(
        multitimeframe, data, initial_capital=5.0, strategy_name="Multi-Timeframe"
    )
    results.append(multitimeframe_result)
    
    # Compare results
    best_strategy = compare_strategies(results, months=6)
    
    # Create visualization
    create_visualization(results, months=6)
    
    print(f"\n🎯 RECOMMENDATION: Use {best_strategy['strategy_name']} for live trading")
    print(f"📊 Expected performance: {best_strategy['total_return']:.2f}% return over 6 months")

if __name__ == "__main__":
    main()
