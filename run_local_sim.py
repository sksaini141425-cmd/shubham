import subprocess
import sys
import os
import time
import webbrowser

def run_bot():
    print("🚀 Starting ProfitBot Pro in Local Simulation Mode...")
    print("💰 Initial Capital: $3.00")
    print("🛠️ Strategy: Scalper70 (70% Winrate Target)")
    print("⚡ Leverage: 20x (Adjusted for Min Notional)")
    print("📊 Dashboard will be available at: http://localhost:5000")
    
    # Wait a few seconds for the server to start before opening the browser
    def open_browser():
        time.sleep(5)
        print("🌐 Opening Dashboard in your browser...")
        webbrowser.open("http://localhost:5000")

    import threading
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Run main.py with appropriate arguments for local simulation
    # We set TOP_N_SYMBOLS=60 to scan a wider market range
    os.environ['TOP_N_SYMBOLS'] = '60'
    os.environ['MIN_VOLUME_USD'] = '10000000' # Higher volume for reliability
    os.environ['USE_REAL_EXCHANGE'] = 'false' # Ensure simulation mode is forced for this script
    
    cmd = [
        sys.executable, "main.py",
        "--capital", "3.0",
        "--max_trades", "10",
        "--leverage", "50",
        "--strategy", "scalper70",
        "--port", "5000",
        "--paper"
    ]
    
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")

if __name__ == "__main__":
    run_bot()
