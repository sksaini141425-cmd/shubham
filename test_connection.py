import ccxt
import os
from dotenv import load_dotenv

load_dotenv(override=True)

def test_binance():
    api_key = os.getenv('BINANCE_API_KEY')
    secret = os.getenv('BINANCE_API_SECRET')
    if not api_key: return
    
    print(f"\n--- Testing Binance ---")
    exchange = ccxt.binance({'apiKey': api_key, 'secret': secret, 'options': {'defaultType': 'future'}})
    for sandbox in [False, True]:
        try:
            exchange.set_sandbox_mode(sandbox)
            balance = exchange.fetch_balance()
            print(f"✅ Binance (Sandbox={sandbox}) SUCCESS! Balance: {balance['total'].get('USDT')}")
        except Exception as e:
            print(f"❌ Binance (Sandbox={sandbox}) FAILED: {e}")

def test_bybit():
    api_key = os.getenv('BYBIT_API_KEY')
    secret = os.getenv('BYBIT_API_SECRET')
    if not api_key:
        print("\nSkipping Bybit: BYBIT_API_KEY not found in .env")
        return
    
    print(f"\n--- Testing Bybit Testnet ---")
    exchange = ccxt.bybit({'apiKey': api_key, 'secret': secret, 'options': {'defaultType': 'linear'}})
    exchange.set_sandbox_mode(True)
    try:
        balance = exchange.fetch_balance()
        print(f"✅ Bybit Testnet SUCCESS! Balance: {balance['total'].get('USDT')}")
    except Exception as e:
        print(f"❌ Bybit Testnet FAILED: {e}")

if __name__ == "__main__":
    test_binance()
    test_bybit()
