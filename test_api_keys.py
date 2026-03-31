"""
Test if your API keys can fetch REAL market data from Binance
This uses the EXPOSED keys you shared (not recommended, but for testing only)
"""

import requests
import hmac
import hashlib
import time

# Your exposed keys (replace with NEW keys after testing!)
API_KEY = "qPaAZoNeYUt6cqwo7eycleHDD8MOcN6AjnDwJTV0DYW6RF3W6Q05QIv2XRnZSY3Y"
API_SECRET = "RwZpldyXysusEpU2phSFBbeaNTh5K9FoaOQ5uMPHBe7pQTR4UYD5fx4bxQyx6OYk"

def get_binance_ticker(symbol="BTCUSDT"):
    """Fetch real market data from Binance"""
    
    # Public endpoint (no signature needed)
    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
    
    headers = {
        'X-MBX-APIKEY': API_KEY
    }
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if 'code' in data:
            print(f"❌ API Error: {data['msg']}")
            return None
        
        return {
            'symbol': data['symbol'],
            'price': float(data['lastPrice']),
            'change': float(data['priceChangePercent']),
            'volume': float(data['volume']),
            'high': float(data['highPrice']),
            'low': float(data['lowPrice']),
            'bid': float(data['bidPrice']),
            'ask': float(data['askPrice'])
        }
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_api_keys():
    """Test if API keys work"""
    print("🔍 Testing Binance API Keys...")
    print("=" * 50)
    
    # Test BTC
    btc = get_binance_ticker("BTCUSDT")
    if btc:
        print(f"✅ BTC Price: ${btc['price']:,.2f}")
        print(f"✅ 24h Change: {btc['change']:.2f}%")
        print(f"✅ Volume: {btc['volume']:,.2f} BTC")
        print()
        
        # Test ETH
        eth = get_binance_ticker("ETHUSDT")
        if eth:
            print(f"✅ ETH Price: ${eth['price']:,.2f}")
            print(f"✅ 24h Change: {eth['change']:.2f}%")
            print()
            
            print("🎉 API KEYS WORK! Real market data accessible!")
            print()
            print("⚠️  IMPORTANT: These keys are exposed in chat!")
            print("🔒 Create NEW keys immediately after testing!")
            return True
    
    print("❌ API keys not working or restricted")
    return False

if __name__ == "__main__":
    test_api_keys()
