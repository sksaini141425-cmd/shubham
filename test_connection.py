import ccxt
import os
from dotenv import load_dotenv

load_dotenv(override=True)

api_key = os.getenv('BINANCE_API_KEY')
secret = os.getenv('BINANCE_API_SECRET')

print(f"Testing with Key: {api_key[:10]}...")

def test_env(name, sandbox):
    print(f"\n--- Testing {name} (Sandbox={sandbox}) ---")
    exchange = ccxt.binance({
        'apiKey': api_key,
        'secret': secret,
        'options': {'defaultType': 'future'}
    })
    exchange.set_sandbox_mode(sandbox)
    try:
        balance = exchange.fetch_balance()
        print(f"✅ SUCCESS! Balance: {balance['total'].get('USDT')}")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False

# Try both
test_env("Mainnet/New Demo", False)
test_env("Legacy Testnet", True)
