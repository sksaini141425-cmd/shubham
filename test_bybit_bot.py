import sys
import os
import logging
from dotenv import load_dotenv

# Add current dir to path
sys.path.append(os.getcwd())

from bot.bybit_exchange import BybitExchange

# Setup Logging
logging.basicConfig(level=logging.INFO)

load_dotenv(override=True)

def test_actual_bot_connection():
    api_key = os.getenv('BYBIT_API_KEY').strip()
    secret = os.getenv('BYBIT_API_SECRET').strip()
    
    print(f"Testing keys starting with: {api_key[:5]}")
    
    try:
        # Initialize the same way main.py does
        exchange = BybitExchange(
            api_key=api_key,
            api_secret=secret,
            testnet=True,
            symbol="BTCUSDT"
        )
        
        balance = exchange.cash
        print(f"\nFINAL RESULT: Success! Balance: ${balance}")
    except Exception as e:
        print(f"\nFINAL RESULT: Failed! Error: {e}")

if __name__ == "__main__":
    test_actual_bot_connection()
