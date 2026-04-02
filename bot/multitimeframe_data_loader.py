"""
Multi-Timeframe Data Loader
Fetches data from multiple timeframes for multi-timeframe strategy analysis
"""
import requests
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MultiTimeframeDataLoader:
    def __init__(self, exchange_id='binance'):
        self.exchange_id = exchange_id
        self.api_key = os.getenv('BINANCE_API_KEY')
        self.api_secret = os.getenv('BINANCE_API_SECRET')
        
        if exchange_id == 'binance':
            self.base_url = "https://api.binance.com/api/v3"
        else:
            self.base_url = "https://api.mexc.com/api/v3"
        
        logger.info(f"Multi-Timeframe Data Loader initialized for {exchange_id}")
        
    def fetch_klines(self, symbol, interval, limit=100):
        """Fetch kline data for specific timeframe"""
        try:
            url = f"{self.base_url}/klines"
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }
            
            # Add API key for Binance if available (better rate limits)
            headers = {}
            if self.exchange_id == 'binance' and self.api_key:
                headers['X-MBX-APIKEY'] = self.api_key
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Convert to standard format
            candles = []
            for item in data:
                candles.append({
                    'timestamp': datetime.fromtimestamp(item[0] / 1000),
                    'open': float(item[1]),
                    'high': float(item[2]),
                    'low': float(item[3]),
                    'close': float(item[4]),
                    'volume': float(item[5])
                })
            
            return candles
            
        except Exception as e:
            logger.error(f"Error fetching {symbol} {interval} data: {e}")
            return []
    
    def fetch_all_timeframes(self, symbol):
        """Fetch data for all required timeframes"""
        timeframes = {
            '1d': 50,    # 50 days for daily trend
            '4h': 100,   # 100 4h candles for medium trend  
            '1h': 100,   # 100 1h candles for short trend
            '15m': 200,  # 200 15m candles for volatility
            '5m': 200,   # 200 5m candles for ATR
            '1m': 500    # 500 1m candles for entry signals
        }
        
        data = {}
        
        for timeframe, limit in timeframes.items():
            logger.info(f"Fetching {symbol} {timeframe} data ({limit} candles)")
            candles = self.fetch_klines(symbol, timeframe, limit)
            data[timeframe] = candles
            
            if candles:
                logger.info(f"✅ Got {len(candles)} {timeframe} candles")
            else:
                logger.warning(f"❌ No {timeframe} data for {symbol}")
        
        return data
    
    def get_latest_aligned_data(self, symbol):
        """Get aligned data from all timeframes ending at same time"""
        all_data = self.fetch_all_timeframes(symbol)
        
        # Get the latest timestamp from 1m data (most granular)
        if '1m' not in all_data or not all_data['1m']:
            return None
            
        latest_time = all_data['1m'][-1]['timestamp']
        
        aligned_data = {}
        
        for timeframe, candles in all_data.items():
            if not candles:
                continue
                
            # Find the candle closest to the latest 1m time
            aligned_candles = []
            for candle in candles:
                # Only include candles up to the latest 1m time
                if candle['timestamp'] <= latest_time:
                    aligned_candles.append(candle)
            
            aligned_data[timeframe] = aligned_candles
        
        return aligned_data
