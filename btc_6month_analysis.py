"""
BTC/USDT 6-Month Comprehensive Analysis
Analyzes 6 months of 1-minute data for robust strategy optimization
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot.data_loader import DataLoader
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import time

def analyze_6months_data(symbol='BTCUSDT'):
    """Analyze 6 months of BTC data with chunked fetching"""
    print(f"🔍 Analyzing {symbol} for last 6 months...")
    print("⏱️ This will take several minutes due to large dataset...")
    
    # Calculate total minutes needed
    total_minutes = 6 * 30 * 24 * 60  # 6 months * 30 days * 24 hours * 60 minutes
    print(f"📊 Need to fetch ~{total_minutes:,} candles")
    
    loader = DataLoader(exchange_id='mexc')
    all_data = []
    chunk_size = 1000
    delay_between_requests = 1  # 1 second delay to avoid rate limits
    
    print(f"🔄 Fetching data in chunks of {chunk_size} candles...")
    
    for i in range(0, total_minutes, chunk_size):
        try:
            # Progress indicator
            progress = (i / total_minutes) * 100
            print(f"   Progress: {progress:.1f}% ({i:,} / {total_minutes:,} minutes)")
            
            # Fetch chunk
            data = loader.fetch_ohlcv(symbol, '1m', chunk_size)
            if data:
                all_data.extend(data)
                print(f"   ✅ Got {len(data)} candles")
            else:
                print(f"   ❌ No data returned for chunk {i//chunk_size}")
            
            # Rate limiting
            if i < total_minutes - chunk_size:
                time.sleep(delay_between_requests)
                
        except Exception as e:
            print(f"   ⚠️ Error at chunk {i//chunk_size}: {e}")
            time.sleep(5)  # Wait longer on error
            continue
    
    if not all_data:
        print("❌ No data fetched")
        return None, None
    
    print(f"✅ Total data fetched: {len(all_data):,} candles")
    
    # Convert to DataFrame
    df = pd.DataFrame(all_data)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    
    # Remove duplicates and sort
    df = df[~df.index.duplicated(keep='first')]
    df = df.sort_index()
    
    print(f"📅 Date range: {df.index.min()} to {df.index.max()}")
    print(f"📊 Actual days covered: {(df.index.max() - df.index.min()).days}")
    
    return df, analyze_comprehensive_patterns(df)

def analyze_comprehensive_patterns(df):
    """Comprehensive analysis of 6-month data"""
    print(f"\n🔬 COMPREHENSIVE 6-MONTH ANALYSIS")
    print("=" * 60)
    
    # Basic statistics
    print(f"📈 PRICE STATISTICS:")
    print(f"   Current Price: ${df['close'].iloc[-1]:,.2f}")
    print(f"   Price Range: ${df['low'].min():,.2f} - ${df['high'].max():,.2f}")
    print(f"   Total Range: ${df['high'].max() - df['low'].min():,.2f} ({((df['high'].max() - df['low'].min())/df['low'].min()*100):.1f}%)")
    print(f"   Average Price: ${df['close'].mean():,.2f}")
    print(f"   Daily Volatility (Std): ${df['close'].std():,.2f}")
    
    # Calculate indicators
    df['price_change'] = df['close'] - df['open']
    df['price_change_pct'] = (df['price_change'] / df['open']) * 100
    df['high_low_range'] = df['high'] - df['low']
    df['high_low_range_pct'] = (df['high_low_range'] / df['open']) * 100
    df['body_size'] = abs(df['close'] - df['open'])
    df['body_size_pct'] = (df['body_size'] / df['open']) * 100
    
    # Candle analysis
    print(f"\n🕯️ CANDLE PATTERNS (6-MONTH AVERAGE):")
    print(f"   Average Body Size: {df['body_size_pct'].mean():.3f}%")
    print(f"   Average Range: {df['high_low_range_pct'].mean():.3f}%")
    print(f"   Max Single Range: {df['high_low_range_pct'].max():.3f}%")
    print(f"   95th Percentile Range: {df['high_low_range_pct'].quantile(0.95):.3f}%")
    print(f"   99th Percentile Range: {df['high_low_range_pct'].quantile(0.99):.3f}%")
    
    # Drop analysis with different thresholds
    thresholds = [0.05, 0.1, 0.2, 0.3, 0.5]
    print(f"\n📉 DROP ANALYSIS BY THRESHOLD:")
    
    for threshold in thresholds:
        drops = df[df['price_change_pct'] < -threshold]
        drop_freq = len(drops) / len(df) * 100
        avg_drop = drops['price_change_pct'].mean() if len(drops) > 0 else 0
        max_drop = drops['price_change_pct'].min() if len(drops) > 0 else 0
        
        print(f"   Drops > {threshold}%,: {len(drops):,} ({drop_freq:.1f}%), Avg: {avg_drop:.3f}%, Max: {max_drop:.3f}%")
    
    # Rebound analysis
    print(f"\n🚀 REBOUND ANALYSIS:")
    for threshold in [0.1, 0.2, 0.3]:
        rebounds = analyze_rebounds(df, threshold)
        if rebounds:
            print(f"   After {threshold}% drops:")
            print(f"     Positive rebounds: {rebounds['positive_rate']*100:.1f}%")
            print(f"     Average rebound: {rebounds['avg_rebound']:.3f}%")
            print(f"     Max rebound: {rebounds['max_rebound']:.3f}%")
            print(f"     Samples: {rebounds['samples']}")
    
    # Weekly patterns
    df['day_of_week'] = df.index.dayofweek
    df['hour'] = df.index.hour
    df['week'] = df.index.isocalendar().week
    
    print(f"\n📅 WEEKLY PATTERNS:")
    weekly_volatility = df.groupby('day_of_week')['high_low_range_pct'].mean()
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    for i, vol in enumerate(weekly_volatility):
        print(f"   {day_names[i]}: {vol:.3f}% avg range")
    
    print(f"\n⏰ HOURLY PATTERNS:")
    hourly_volatility = df.groupby('hour')['high_low_range_pct'].mean()
    best_hour = hourly_volatility.idxmax()
    worst_hour = hourly_volatility.idxmin()
    print(f"   Most Volatile: {best_hour}:00 ({hourly_volatility.max():.3f}% avg)")
    print(f"   Least Volatile: {worst_hour}:00 ({hourly_volatility.min():.3f}% avg)")
    
    # Monthly trends
    print(f"\n📈 MONTHLY TRENDS:")
    monthly_returns = df.groupby(df.index.to_period('M'))['close'].last().pct_change().dropna()
    print(f"   Average Monthly Return: {monthly_returns.mean()*100:.2f}%")
    print(f"   Best Month: {monthly_returns.max()*100:.2f}%")
    print(f"   Worst Month: {monthly_returns.min()*100:.2f}%")
    print(f"   Volatility (Monthly Std): {monthly_returns.std()*100:.2f}%")
    
    # Strategy optimization recommendations
    print(f"\n💡 STRATEGY OPTIMIZATION (6-MONTH DATA):")
    
    # Optimal RSI levels based on actual data
    price_changes = df['price_change_pct']
    oversold_20 = price_changes.quantile(0.15)  # 15th percentile
    oversold_10 = price_changes.quantile(0.10)  # 10th percentile
    overbought_80 = price_changes.quantile(0.85)  # 85th percentile
    overbought_90 = price_changes.quantile(0.90)  # 90th percentile
    
    print(f"   🎯 RSI Thresholds (based on 6-month data):")
    print(f"      Conservative oversold: < 40 (drops ~{oversold_20:.2f}%)")
    print(f"      Aggressive oversold: < 35 (drops ~{oversold_10:.2f}%)")
    print(f"      Conservative overbought: > 60 (gains ~{overbought_80:.2f}%)")
    print(f"      Aggressive overbought: > 65 (gains ~{overbought_90:.2f}%)")
    
    # Optimal holding periods
    print(f"   ⏱️ Holding Period Analysis:")
    for minutes in [5, 10, 15, 30, 60, 120]:
        if len(df) > minutes:
            returns = df['close'].pct_change(minutes).dropna()
            significant_moves = returns[abs(returns) > 0.005]  # > 0.5%
            print(f"      {minutes} min: Avg {returns.mean()*100:.3f}%, {len(significant_moves)} significant moves ({len(significant_moves)/len(returns)*100:.1f}%)")
    
    # Risk management
    print(f"   🛡️ Risk Management:")
    print(f"      95th percentile drop: {df['price_change_pct'].quantile(0.05):.3f}%")
    print(f"      99th percentile drop: {df['price_change_pct'].quantile(0.01):.3f}%")
    print(f"      Suggested stop loss: {abs(df['price_change_pct'].quantile(0.02))*100:.1f}% (98% of drops)")
    print(f"      Suggested take profit: {df['price_change_pct'].quantile(0.98)*100:.1f}% (98% of gains)")
    
    return {
        'total_candles': len(df),
        'avg_range': df['high_low_range_pct'].mean(),
        'volatility_95': df['high_low_range_pct'].quantile(0.95),
        'drop_01pct': len(df[df['price_change_pct'] < -0.1]),
        'drop_02pct': len(df[df['price_change_pct'] < -0.2]),
        'best_hour': best_hour,
        'worst_hour': worst_hour,
        'price_range_6m': (df['high'].max() - df['low'].min()) / df['low'].min() * 100
    }

def analyze_rebounds(df, threshold):
    """Analyze rebounds after drops of specific threshold"""
    drops = df[df['price_change_pct'] < -threshold]
    rebounds = []
    
    for i in range(1, len(df)-1):
        if df['price_change_pct'].iloc[i] < -threshold:
            # Look at next 1-5 candles for rebound
            for j in range(1, min(6, len(df)-i)):
                next_candle = df.iloc[i+j]
                rebound_pct = (next_candle['close'] - df['close'].iloc[i]) / df['close'].iloc[i] * 100
                rebounds.append(rebound_pct)
                break  # Only first rebound
    
    if not rebounds:
        return None
    
    rebounds_series = pd.Series(rebounds)
    return {
        'positive_rate': sum(1 for r in rebounds if r > 0) / len(rebounds),
        'avg_rebound': rebounds_series.mean(),
        'max_rebound': rebounds_series.max(),
        'samples': len(rebounds)
    }

if __name__ == "__main__":
    print("🔬 BTC/USDT 6-MONTH COMPREHENSIVE ANALYSIS")
    print("=" * 60)
    print("⚠️  WARNING: This will take 10-20 minutes and fetch ~260,000 candles")
    print("⚠️  Make sure you have stable internet connection")
    
    user_input = input("\nContinue? (y/n): ")
    if user_input.lower() != 'y':
        print("❌ Analysis cancelled")
        exit()
    
    start_time = time.time()
    df, stats = analyze_6months_data()
    
    if df is not None:
        # Save data
        df.to_csv('btc_6month_data.csv')
        
        # Save summary
        with open('btc_6month_summary.json', 'w') as f:
            json.dump({k: int(v) if isinstance(v, (np.int32, np.int64)) else float(v) if isinstance(v, (np.float32, np.float64)) else v 
                     for k, v in stats.items()}, f, indent=2)
        
        elapsed = time.time() - start_time
        print(f"\n✅ Analysis complete in {elapsed/60:.1f} minutes!")
        print(f"💾 Data saved to btc_6month_data.csv")
        print(f"📋 Summary saved to btc_6month_summary.json")
        
        print(f"\n📊 FINAL SUMMARY:")
        print(f"   Total candles analyzed: {stats['total_candles']:,}")
        print(f"   6-month price range: {stats['price_range_6m']:.1f}%")
        print(f"   Average volatility: {stats['avg_range']:.3f}%")
        print(f"   95th percentile moves: {stats['volatility_95']:.3f}%")
        print(f"   Drops >0.1%: {stats['drop_01pct']:,}")
        print(f"   Drops >0.2%: {stats['drop_02pct']:,}")
        print(f"   Best trading hour: {stats['best_hour']}:00")
        print(f"   Worst trading hour: {stats['worst_hour']}:00")
    else:
        print("❌ Analysis failed")
