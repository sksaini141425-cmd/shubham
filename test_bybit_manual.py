import os
import ccxt
import logging
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("BybitTester")

def test_manual_trade():
    # Load .env
    load_dotenv()
    
    api_key = os.getenv('BYBIT_API_KEY')
    api_secret = os.getenv('BYBIT_API_SECRET')
    
    if not api_key or not api_secret:
        logger.error("❌ API Keys missing in .env!")
        return

    # Try all possible Bybit environments
    environments = [
        {"name": "Bybit Mainnet/Demo", "testnet": False},
        {"name": "Bybit Testnet Server", "testnet": True}
    ]

    for env in environments:
        logger.info(f"\n🔄 Trying to connect to {env['name']}...")
        exchange = ccxt.bybit({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'linear', 
                'adjustForTimeDifference': True,
                'recvWindow': 60000
            }
        })
        
        if env['testnet']:
            exchange.set_sandbox_mode(True)

        try:
            # Load markets first to verify connection
            exchange.load_markets()
            balance = exchange.fetch_balance()
            
            # Check for balance in USDT
            usdt_bal = balance['total'].get('USDT', 0.0)
            logger.info(f"✅ {env['name']} CONNECTED!")
            logger.info(f"💰 Found Balance: ${usdt_bal} USDT")
            
            if usdt_bal > 0:
                # Try a tiny test trade (0.001 BTC)
                symbol = 'BTC/USDT:USDT'
                logger.info(f"🚀 Opening tiny TEST trade on {symbol}...")
                order = exchange.create_market_buy_order(symbol, 0.001)
                logger.info(f"✅ Trade Successful! ID: {order['id']}")
                
                import time
                time.sleep(2)
                
                logger.info(f"🛑 Closing test trade...")
                close_order = exchange.create_market_sell_order(symbol, 0.001, params={'reduceOnly': True})
                logger.info(f"✅ Trade Closed! ID: {close_order['id']}")
                
                logger.info(f"\n🏆 {env['name']} is 100% READY!")
                return # Stop if successful
            else:
                logger.warning(f"⚠️ {env['name']} connected, but balance is $0.00.")

        except Exception as e:
            if "API key is invalid" in str(e):
                logger.error(f"❌ {env['name']} rejected the keys (Invalid API Key).")
            else:
                logger.error(f"❌ {env['name']} Error: {e}")

    logger.error("\n❌ No environment could verify these keys. Please double-check the Key/Secret on Bybit.")

if __name__ == "__main__":
    test_manual_trade()
