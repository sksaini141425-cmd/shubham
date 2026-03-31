from real_binance_exchange import RealBinanceExchange

try:
    print("🔗 Testing Binance connection...")
    exchange = RealBinanceExchange(use_testnet=True)
    balance = exchange.get_account_summary()
    print(f"✅ Connected! Balance: ${balance['balance']}")
    
    # Test market data
    btc_data = exchange.get_real_market_data('BTC/USDT')
    if btc_data:
        print(f"📊 BTC Price: ${btc_data['price']}")
        print(f"📈 Signal: {btc_data['signal']}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("💡 Make sure your .env file has valid API keys")
