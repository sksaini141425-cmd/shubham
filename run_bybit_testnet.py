import subprocess
import sys
import os
import time
import webbrowser

def run_bot():
    print("🚀 Starting ProfitBot Pro in BYBIT TESTNET Mode...")
    print("💰 Initial Capital: $3.00 (or your Bybit Testnet balance)")
    print("🛠️ Strategy: Scalper70 (70% Winrate Target)")
    print("⚡ Leverage: 50x")
    print("📡 Mode: REAL EXCHANGE (Bybit Testnet)")
    print("📊 Dashboard will be available at: http://localhost:5000")
    
    # Wait a few seconds for the server to start before opening the browser
    def open_browser():
        time.sleep(5)
        print("🌐 Opening Dashboard in your browser...")
        webbrowser.open("http://localhost:5000")

    import threading
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Force real exchange mode for this script
    os.environ['USE_REAL_EXCHANGE'] = 'true'
    os.environ['USE_TESTNET'] = 'true'
    os.environ['EXCHANGE'] = 'bybit'
    os.environ['TOP_N_SYMBOLS'] = '60'
    os.environ['MIN_VOLUME_USD'] = '1000000' 
    
    cmd = [
        sys.executable, "main.py",
        "--capital", "3.0",
        "--max_trades", "10",
        "--leverage", "50",
        "--strategy", "scalper70",
        "--exchange", "bybit",
        "--port", "5000"
    ]
    
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")

if __name__ == "__main__":
    run_bot()
