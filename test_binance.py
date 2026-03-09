import os
from dotenv import load_dotenv
from bot.binance_exchange import BinanceExchange
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestBinance")

def test_connection():
    load_dotenv(override=True)
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    
    if not api_key or not api_secret or api_key == "your_api_key_here":
        logger.error("❌ API Keys not found or still set to defaults in .env file.")
        return

    try:
        # Use our actual class to test it
        exchange = BinanceExchange(
            api_key=api_key,
            api_secret=api_secret,
            testnet=True
        )
        
        cash = exchange.cash
        logger.info(f"✅ Successfully connected to Binance Testnet via BinanceExchange class!")
        logger.info(f"💰 Available USDT Balance: {cash}")
        
    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    test_connection()
