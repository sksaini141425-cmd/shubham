#!/usr/bin/env python3
"""
Altered Multi-Timeframe Bot - For Comparison
More relaxed settings to generate more trades
"""
import os
import subprocess
import sys
import time
import webbrowser

def main():
    print("🚀 Starting ALTERED Multi-Timeframe Bot")
    print("📊 RELAXED Settings - More Trade Opportunities")
    print("⚡ ADX: 15, Stoch RSI: 30/70, EMA: 20")
    print("🎯 Goal: More frequent trades with good win rate")
    
    # Set environment with ALTERED settings
    env = os.environ.copy()
    env.update({
        'STRATEGY': 'multitimeframe',
        'INITIAL_CAPITAL': '5.0',
        'LEVERAGE': '5',
        'MAX_CONCURRENT_TRADES': '3',
        'TOP_N_SYMBOLS': '10',
        'MIN_VOLUME_USD': '5000000',
        'USE_REAL_EXCHANGE': 'false',
        'EXCHANGE': 'binance',  # Use Binance for multi-timeframe data
        'PORT': '5008',  # Another isolated port
        'BOT_PROFILE': 'Multi-Timeframe-Altered',  # Descriptive name
        'TELEGRAM_BOT_TOKEN': env.get('TELEGRAM_BOT_TOKEN', ''),
        'TELEGRAM_CHAT_ID': env.get('TELEGRAM_CHAT_ID', ''),
        'GEMINI_API_KEY': env.get('GEMINI_API_KEY', ''),
        'BINANCE_API_KEY': env.get('BINANCE_API_KEY', ''),
        'BINANCE_API_SECRET': env.get('BINANCE_API_SECRET', '')
    })
    
    print(f"🔒 Profile: {env['BOT_PROFILE']} (ISOLATED)")
    print(f"🌐 Port: {env['PORT']} (SEPARATE)")
    print(f"💰 Capital: ${env['INITIAL_CAPITAL']}")
    print(f"⚡ Leverage: {env['LEVERAGE']}x")
    print(f"📈 Risk per Trade: 2%")
    print(f"🎯 ALTERED Parameters:")
    print(f"   - ADX Threshold: 15 (vs 25 original)")
    print(f"   - Stoch RSI Oversold: 30 (vs 20 original)")
    print(f"   - Stoch RSI Overbought: 70 (vs 80 original)")
    print(f"   - EMA Period: 20 (same)")
    print(f"   - Avoid Hours: 12, 13, 14 UTC (same)")
    
    try:
        # Start bot with ALTERED strategy
        process = subprocess.Popen([
            sys.executable, 'main.py',
            '--strategy', env['STRATEGY'],
            '--capital', env['INITIAL_CAPITAL'],
            '--leverage', env['LEVERAGE'],
            '--port', env['PORT'],
            '--exchange', env['EXCHANGE'],
            '--profile', env['BOT_PROFILE']
        ], env=env)
        
        print(f"✅ Altered Multi-Timeframe Bot started with PID: {process.pid}")
        
        # Wait for startup
        time.sleep(3)
        
        # Open dashboard
        dashboard_url = f"http://localhost:{env['PORT']}"
        print(f"🌐 Opening dashboard: {dashboard_url}")
        webbrowser.open(dashboard_url)
        
        print(f"\n🎯 ALTERED STRATEGY IS RUNNING!")
        print(f"📊 Dashboard: {dashboard_url}")
        print(f"💰 Goal: More frequent trades")
        print(f"🔒 Profile: {env['BOT_PROFILE']} (isolated)")
        print(f"⚡ RELAXED SETTINGS for more opportunities")
        
        print(f"\n📊 COMPARISON SETUP:")
        print(f"🔹 Original Bot (Port 5007): Your exact settings")
        print(f"🔹 Altered Bot (Port 5008): Relaxed settings")
        print(f"🔹 Compare performance side-by-side")
        
        # Monitor
        try:
            while True:
                time.sleep(60)  # Check every minute
                if process.poll() is not None:
                    print(f"\n❌ Bot stopped")
                    break
                print(f"📊 [{time.strftime('%H:%M:%S')}] Altered bot running - {dashboard_url}")
        except KeyboardInterrupt:
            print(f"\n👋 Monitoring stopped (bot continues)")
            
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
        if 'process' in locals():
            process.terminate()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
