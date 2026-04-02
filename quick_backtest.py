#!/usr/bin/env python3
"""
Quick Strategy Comparison
Fast comparison between Scalper30 and Multi-Timeframe strategies
"""
import json
from datetime import datetime, timedelta
from bot.strategy_optimized import Scalper30Strategy
from bot.strategy_multitimeframe import MultiTimeframeScalperStrategy

def generate_test_data(days=30):
    """Generate test data for quick comparison"""
    print(f"📊 Generating {days} days of test data...")
    
    data = []
    base_price = 40000
    
    for i in range(days * 24 * 60):  # 1-minute candles
        # Realistic BTC movement
        if i % (24 * 60) == 0:  # Daily trend
            daily_trend = (i % 3 - 1) * 0.002  # -0.2%, 0, +0.2%
            base_price *= (1 + daily_trend)
        
        # Intraday volatility
        volatility = 0.001  # 0.1% per minute
        price_change = (i % 200 - 100) / 100000  # -0.1% to +0.1%
        current_price = base_price * (1 + price_change)
        
        # OHLC
        high = current_price * (1 + abs(i % 50) / 10000)
        low = current_price * (1 - abs(i % 50) / 10000)
        open_price = low + (high - low) * (i % 100) / 100
        
        data.append({
            'timestamp': datetime.now() - timedelta(days=30) + timedelta(minutes=i),
            'open': open_price,
            'high': high,
            'low': low,
            'close': current_price,
            'volume': 1000000 + (i % 500000)
        })
    
    return data

def quick_test_strategy(strategy, data, strategy_name):
    """Quick strategy test"""
    print(f"🔄 Testing {strategy_name}...")
    
    # Initialize
    initial_capital = 5.0
    current_capital = initial_capital
    trades = 0
    wins = 0
    losses = 0
    
    # Process data
    for i in range(100, min(len(data), 5000)):  # Test on subset for speed
        current_data = data[:i+1]
        
        # Calculate indicators
        current_data = strategy.calculate_indicators(current_data)
        current_data = strategy.generate_signals(current_data)
        
        # Check signal
        signal = current_data[-1].get('signal', 'NONE')
        current_price = current_data[-1]['close']
        
        # Simple trade simulation
        if signal in ['LONG', 'SHORT']:
            trades += 1
            
            # Simulate outcome (simplified)
            if signal == 'LONG':
                # Random walk for next 30 minutes
                future_price = current_price * (1 + (i % 100 - 50) / 10000)
                if future_price > current_price:
                    wins += 1
                    current_capital *= 1.01  # 1% gain
                else:
                    losses += 1
                    current_capital *= 0.995  # 0.5% loss
            else:  # SHORT
                future_price = current_price * (1 + (i % 100 - 50) / 10000)
                if future_price < current_price:
                    wins += 1
                    current_capital *= 1.01
                else:
                    losses += 1
                    current_capital *= 0.995
    
    # Calculate metrics
    win_rate = (wins / trades * 100) if trades > 0 else 0
    total_return = ((current_capital - initial_capital) / initial_capital * 100)
    
    return {
        'strategy_name': strategy_name,
        'trades': trades,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'total_return': total_return,
        'final_capital': current_capital
    }

def main():
    print("🚀 Quick Strategy Comparison")
    print("=" * 40)
    
    # Generate test data
    data = generate_test_data(days=30)
    
    # Test strategies
    scalper30 = Scalper30Strategy(leverage=30)
    multitimeframe = MultiTimeframeScalperStrategy(leverage=5)
    
    # Run tests
    results = []
    
    # Test Scalper30
    scalper30_result = quick_test_strategy(scalper30, data, "Scalper30")
    results.append(scalper30_result)
    
    # Test Multi-Timeframe
    mt_result = quick_test_strategy(multitimeframe, data, "Multi-Timeframe")
    results.append(mt_result)
    
    # Display results
    print("\n📊 COMPARISON RESULTS")
    print("=" * 40)
    
    for result in results:
        print(f"\n🎯 {result['strategy_name']}")
        print(f"   Trades: {result['trades']}")
        print(f"   Wins: {result['wins']}")
        print(f"   Losses: {result['losses']}")
        print(f"   Win Rate: {result['win_rate']:.1f}%")
        print(f"   Total Return: {result['total_return']:.2f}%")
        print(f"   Final Capital: ${result['final_capital']:.2f}")
    
    # Determine winner
    winner = max(results, key=lambda x: x['total_return'])
    print(f"\n🏆 WINNER: {winner['strategy_name']}")
    print(f"   Return: {winner['total_return']:.2f}%")
    print(f"   Win Rate: {winner['win_rate']:.1f}%")
    
    # Save results
    with open('quick_backtest_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n✅ Results saved to 'quick_backtest_results.json'")

if __name__ == "__main__":
    main()
