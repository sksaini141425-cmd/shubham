#!/usr/bin/env python3
"""
Multi-Timeframe Scalper Bot Runner
Advanced scalper using multi-timeframe analysis and dynamic risk management.
Based on user's configuration parameters.
"""
import os
import subprocess
import sys
import time
import webbrowser

def main():
    # Set environment variables for this specific strategy
    env = os.environ.copy()
    env.update({
        'STRATEGY': 'multitimeframe',
        'INITIAL_CAPITAL': '5.0',
        'LEVERAGE': '5',
        'MAX_CONCURRENT_TRADES': '3',
        'TOP_N_SYMBOLS': '10',
        'MIN_VOLUME_USD': '5000000',
        'USE_REAL_EXCHANGE': 'false',
        'EXCHANGE': 'mexc',
        'PORT': '5005',  # Different port for isolation
        'BOT_PROFILE': 'multitimeframe'  # Isolated profile
    })
    
    print(f"🚀 Starting ISOLATED Multi-Timeframe Scalper Bot...")
    print("📊 Advanced multi-timeframe analysis")
    print("⚡ Dynamic risk management")
    print("🎯 Optimized for BTCUSDT")
    print(f"🔒 Profile: {env['BOT_PROFILE']} (ISOLATED)")
    print(f"🌐 Port: {env['PORT']} (SEPARATE)")
    
    # Print configuration
    print(f"💰 Initial Capital: ${env['INITIAL_CAPITAL']}")
    print(f"⚡ Leverage: {env['LEVERAGE']}x (conservative)")
    print(f"📈 Risk per Trade: 2%")
    print(f"🎯 Timeframes: 1h/4h/1d trend + 1m entry")
    print(f"📊 Dashboard will be available at: http://localhost:{env['PORT']}")
    print("🔄 Starting multi-timeframe bot...")
    
    # Start the bot
    try:
        process = subprocess.Popen([
            sys.executable, 'main.py',
            '--strategy', env['STRATEGY'],
            '--capital', env['INITIAL_CAPITAL'],
            '--leverage', env['LEVERAGE'],
            '--port', env['PORT'],
            '--exchange', env['EXCHANGE']
        ], env=env)
        
        print(f"✅ Multi-Timeframe Scalper started with PID: {process.pid}")
        
        # Wait a moment for startup
        time.sleep(3)
        
        # Open browser
        dashboard_url = f"http://localhost:{env['PORT']}"
        print(f"🌐 Opening dashboard: {dashboard_url}")
        webbrowser.open(dashboard_url)
        
        # Wait for process to complete
        process.wait()
        
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
        if 'process' in locals():
            process.terminate()
    except Exception as e:
        print(f"❌ Error starting bot: {e}")

if __name__ == "__main__":
    main()
