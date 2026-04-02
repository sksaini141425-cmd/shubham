#!/usr/bin/env python3
"""
Original Multi-Timeframe Bot launcher.
Runs the BTCUSDT multi-timeframe profile with the requested fixed parameters.
"""
import os
import subprocess
import sys
import time
import webbrowser


def main():
    print("Starting ORIGINAL Multi-Timeframe Bot")
    print("Using the exact BTCUSDT multi-timeframe configuration")
    print("ADX: 25, Stoch RSI: 20/80, EMA: 20, ATR SL/TP: 1.5x/3.0x")

    env = os.environ.copy()
    env.update({
        'STRATEGY': 'multitimeframe',
        'INITIAL_CAPITAL': '5.0',
        'LEVERAGE': '5',
        'MAX_CONCURRENT_TRADES': '10',
        'TOP_N_SYMBOLS': '1',
        'TARGET_SYMBOL': 'BTCUSDT',
        'MIN_VOLUME_USD': '5000000',
        'USE_REAL_EXCHANGE': 'false',
        'EXCHANGE': 'binance',
        'PORT': '5007',
        'BOT_PROFILE': 'Multi-Timeframe-Original',
        'TELEGRAM_BOT_TOKEN': env.get('TELEGRAM_BOT_TOKEN', ''),
        'TELEGRAM_CHAT_ID': env.get('TELEGRAM_CHAT_ID', ''),
        'GEMINI_API_KEY': env.get('GEMINI_API_KEY', ''),
        'BINANCE_API_KEY': env.get('BINANCE_API_KEY', ''),
        'BINANCE_API_SECRET': env.get('BINANCE_API_SECRET', '')
    })

    print(f"Profile: {env['BOT_PROFILE']}")
    print(f"Dashboard port: {env['PORT']}")
    print(f"Capital: ${env['INITIAL_CAPITAL']}")
    print(f"Leverage: {env['LEVERAGE']}x")
    print("Risk per trade: 2%")
    print("Target pair: BTCUSDT")
    print("Order type: LIMIT")
    print("Avoid hours: 12, 13, 14 UTC")

    try:
        process = subprocess.Popen([
            sys.executable, 'main.py',
            '--strategy', env['STRATEGY'],
            '--capital', env['INITIAL_CAPITAL'],
            '--leverage', env['LEVERAGE'],
            '--max_trades', env['MAX_CONCURRENT_TRADES'],
            '--port', env['PORT'],
            '--exchange', env['EXCHANGE'],
            '--profile', env['BOT_PROFILE']
        ], env=env)

        print(f"Original Multi-Timeframe Bot started with PID: {process.pid}")

        time.sleep(3)

        dashboard_url = f"http://localhost:{env['PORT']}"
        print(f"Opening dashboard: {dashboard_url}")
        webbrowser.open(dashboard_url)

        print("\nMulti-Timeframe profile is running")
        print(f"Dashboard: {dashboard_url}")
        print("Mode: paper trading")
        print("Execution profile: BTCUSDT only")

        try:
            while True:
                time.sleep(60)
                if process.poll() is not None:
                    print("\nBot stopped")
                    break
                print(f"[{time.strftime('%H:%M:%S')}] Bot running - {dashboard_url}")
        except KeyboardInterrupt:
            print("\nMonitoring stopped (bot continues)")

    except KeyboardInterrupt:
        print("\nBot stopped by user")
        if 'process' in locals():
            process.terminate()
    except Exception as exc:
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()
