"""
Run Optimized Scalper30 Bot
Uses data-driven strategy based on 6-month BTC analysis
"""
import subprocess
import sys
import os
import time
import webbrowser

def run_optimized_bot():
    print("🚀 Starting ProfitBot Pro with OPTIMIZED Scalper30 Strategy...")
    print("📊 Based on 6-month BTC analysis")
    print("💰 Initial Capital: $3.00")
    print("⚡ Leverage: 30x (optimized for low volatility)")
    print("🎯 RSI: 40/60 (realistic thresholds)")
    print("📈 Holding: 30 minutes (optimal for significant moves)")
    print("📊 Dashboard will be available at: http://localhost:5003")
    
    # Wait a few seconds for the server to start before opening browser
    def open_browser():
        time.sleep(5)
        print("🌐 Opening Dashboard in your browser...")
        webbrowser.open("http://localhost:5003")

    import threading
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Set environment variables for optimized strategy
    os.environ.update({
        'STRATEGY': 'scalper30',
        'INITIAL_CAPITAL': '3.00',
        'LEVERAGE': '30',
        'MAX_CONCURRENT_TRADES': '5',
        'TOP_N_SYMBOLS': '15',
        'MIN_VOLUME_USD': '1000000',
        'USE_REAL_EXCHANGE': 'false',
        'EXCHANGE': 'mexc',
        'PORT': '5003',
        'BOT_PROFILE': 'Scalper30-Optimized',  # Descriptive name
        'TELEGRAM_BOT_TOKEN': env.get('TELEGRAM_BOT_TOKEN', ''),
        'TELEGRAM_CHAT_ID': env.get('TELEGRAM_CHAT_ID', ''),
        'GEMINI_API_KEY': env.get('GEMINI_API_KEY', '')
    })
    
    cmd = [
        sys.executable, "main.py",
        "--capital", "3.0",
        "--max_trades", "5",  # Fewer concurrent trades
        "--leverage", "30",  # Optimized leverage
        "--strategy", "scalper30",  # Custom strategy
        "--exchange", "mexc",  # Use MEXC for data
        "--port", "5003",
        "--paper"
    ]
    
    try:
        print("🔄 Starting optimized bot...")
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n🛑 Optimized bot stopped by user.")

if __name__ == "__main__":
    run_optimized_bot()
