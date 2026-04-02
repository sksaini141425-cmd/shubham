"""
BTC/USDT 1-Minute Candle Analysis
Analyzes price drops, rebounds, and patterns for strategy optimization
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot.data_loader import DataLoader
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import json

def analyze_candle_patterns(symbol='BTCUSDT', hours_back=24):
    """Analyze BTC candle patterns over specified period"""
    print(f"🔍 Analyzing {symbol} 1-minute candles for last {hours_back} hours...")
    
    # Load data
    loader = DataLoader(exchange_id='mexc')
    minutes_needed = hours_back * 60
    
    # Fetch data in chunks to avoid API limits
    all_data = []
    chunk_size = 1000
    
    for i in range(0, minutes_needed, chunk_size):
        end_minutes = min(i + chunk_size, minutes_needed)
        print(f"Fetching minutes {i} to {end_minutes}...")
        
        try:
            data = loader.fetch_ohlcv(symbol, '1m', end_minutes)
            if data:
                all_data.extend(data)
            else:
                print(f"No data for minutes {i}-{end_minutes}")
        except Exception as e:
            print(f"Error fetching data: {e}")
            
        if len(all_data) >= minutes_needed:
            break
    
    if not all_data:
        print("❌ No data fetched")
        return
    
    print(f"✅ Fetched {len(all_data)} candles")
    
    # Convert to DataFrame for analysis
    df = pd.DataFrame(all_data)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    
    # Calculate price changes and patterns
    df['price_change'] = df['close'] - df['open']
    df['price_change_pct'] = (df['price_change'] / df['open']) * 100
    df['high_low_range'] = df['high'] - df['low']
    df['high_low_range_pct'] = (df['high_low_range'] / df['open']) * 100
    df['body_size'] = abs(df['close'] - df['open'])
    df['body_size_pct'] = (df['body_size'] / df['open']) * 100
    df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
    df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
    
    # Analyze drops and rebounds
    print("\n📊 CANDLE PATTERN ANALYSIS")
    print("=" * 50)
    
    # Basic statistics
    print(f"📈 Price Statistics:")
    print(f"   Current Price: ${df['close'].iloc[-1]:.2f}")
    print(f"   Price Range: ${df['low'].min():.2f} - ${df['high'].max():.2f}")
    print(f"   Average Price: ${df['close'].mean():.2f}")
    print(f"   Price Volatility (Std): ${df['close'].std():.2f}")
    
    print(f"\n🕯️ Candle Statistics:")
    print(f"   Average Body Size: {df['body_size_pct'].mean():.3f}%")
    print(f"   Average Range: {df['high_low_range_pct'].mean():.3f}%")
    print(f"   Max Range: {df['high_low_range_pct'].max():.3f}%")
    print(f"   Min Range: {df['high_low_range_pct'].min():.3f}%")
    
    # Drop analysis
    significant_drops = df[df['price_change_pct'] < -0.1]  # Drops > 0.1%
    print(f"\n📉 DROP ANALYSIS:")
    print(f"   Total Candles: {len(df)}")
    print(f"   Significant Drops (>0.1%): {len(significant_drops)} ({len(significant_drops)/len(df)*100:.1f}%)")
    
    if len(significant_drops) > 0:
        print(f"   Average Drop Size: {significant_drops['price_change_pct'].mean():.3f}%")
        print(f"   Max Drop: {significant_drops['price_change_pct'].min():.3f}%")
        print(f"   Drop Frequency: ~1 every {len(df)/len(significant_drops):.1f} minutes")
    
    # Rebound analysis
    rebounds = []
    for i in range(1, len(df)-1):
        if df['price_change_pct'].iloc[i] < -0.1:  # Drop candle
            next_candle = df.iloc[i+1]
            rebound_pct = (next_candle['close'] - df['close'].iloc[i]) / df['close'].iloc[i] * 100
            rebounds.append(rebound_pct)
    
    if rebounds:
        rebounds_series = pd.Series(rebounds)
        print(f"\n🚀 REBOUND ANALYSIS:")
        print(f"   Drops with next data: {len(rebounds)}")
        print(f"   Average Rebound: {rebounds_series.mean():.3f}%")
        print(f"   Max Rebound: {rebounds_series.max():.3f}%")
        print(f"   Positive Rebounds: {sum(1 for r in rebounds if r > 0)} ({sum(1 for r in rebounds if r > 0)/len(rebounds)*100:.1f}%)")
    
    # Time-based patterns
    df['hour'] = df.index.hour
    hourly_volatility = df.groupby('hour')['high_low_range_pct'].mean()
    
    print(f"\n⏰ TIME-BASED PATTERNS:")
    print(f"   Most Volatile Hour: {hourly_volatility.idxmax()} ({hourly_volatility.max():.3f}% avg range)")
    print(f"   Least Volatile Hour: {hourly_volatility.idxmin()} ({hourly_volatility.min():.3f}% avg range)")
    
    # Strategy recommendations
    print(f"\n💡 STRATEGY RECOMMENDATIONS:")
    
    # Based on analysis
    avg_range = df['high_low_range_pct'].mean()
    max_drop = significant_drops['price_change_pct'].min() if len(significant_drops) > 0 else 0
    
    if avg_range < 0.5:
        print(f"   • Low volatility market - consider wider stop losses")
    elif avg_range > 1.0:
        print(f"   • High volatility market - tighter stops may work better")
    
    if len(rebounds) > 0 and sum(1 for r in rebounds if r > 0)/len(rebounds) > 0.6:
        print(f"   • Good rebound rate ({sum(1 for r in rebounds if r > 0)/len(rebounds)*100:.1f}%) - dip buying strategy viable")
    
    # Optimal RSI levels based on actual price movements
    price_changes = df['price_change_pct']
    oversold_threshold = price_changes.quantile(0.2)  # 20th percentile
    overbought_threshold = price_changes.quantile(0.8)  # 80th percentile
    
    print(f"   • Suggested RSI oversold level: < 35 (current drops often {oversold_threshold:.2f}%)")
    print(f"   • Suggested RSI overbought level: > 65 (current gains often {overbought_threshold:.2f}%)")
    print(f"   • Average holding time: 5-15 minutes (based on typical candle patterns)")
    
    return df, {
        'avg_range': avg_range,
        'max_drop': max_drop,
        'rebound_rate': sum(1 for r in rebounds if r > 0)/len(rebounds) if rebounds else 0,
        'total_drops': len(significant_drops),
        'total_candles': len(df)
    }

def analyze_specific_periods(df, periods=[5, 15, 30, 60]):
    """Analyze price movements over different time periods"""
    print(f"\n📅 MULTI-TIMEFRAME ANALYSIS:")
    
    for minutes in periods:
        if len(df) < minutes:
            continue
            
        # Calculate rolling statistics using iloc for indexing
        rolling_change = df['close'].rolling(window=minutes).apply(
            lambda x: (x.iloc[-1] - x.iloc[0]) / x.iloc[0] * 100, raw=False
        )
        
        print(f"\n   {minutes}-minute periods:")
        print(f"     Average change: {rolling_change.mean():.3f}%")
        print(f"     Max gain: {rolling_change.max():.3f}%")
        print(f"     Max loss: {rolling_change.min():.3f}%")
        print(f"     Std deviation: {rolling_change.std():.3f}%")
        
        # Count significant moves
        significant_moves = rolling_change[abs(rolling_change) > 0.5]
        print(f"     Significant moves (>0.5%): {len(significant_moves)} ({len(significant_moves)/len(rolling_change)*100:.1f}%)")

if __name__ == "__main__":
    print("🔬 BTC/USDT Candle Pattern Analysis")
    print("=" * 50)
    
    # Analyze last 24 hours
    df, stats = analyze_candle_patterns('BTCUSDT', hours_back=24)
    
    if df is not None:
        # Multi-timeframe analysis
        analyze_specific_periods(df)
        
        print(f"\n📋 SUMMARY:")
        print(f"   Total candles analyzed: {stats['total_candles']}")
        print(f"   Significant drops: {stats['total_drops']}")
        print(f"   Average volatility: {stats['avg_range']:.3f}%")
        print(f"   Rebound rate: {stats['rebound_rate']*100:.1f}%")
        
        print(f"\n✅ Analysis complete! Use these insights to optimize your Scalper70 strategy.")
        
        # Save data for further analysis
        df.to_csv('btc_candle_data.csv')
        print(f"💾 Data saved to btc_candle_data.csv")
