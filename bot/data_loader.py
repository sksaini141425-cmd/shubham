import requests
import logging

logger = logging.getLogger(__name__)

# Bybit standard fees (comparable to Binance)
BYBIT_MAKER_FEE = 0.0002  # 0.02%
BYBIT_TAKER_FEE = 0.00055  # 0.055%

# Bybit interval map
INTERVAL_MAP = {
    '1m': '1', '3m': '3', '5m': '5', '15m': '15', '30m': '30',
    '1h': '60', '2h': '120', '4h': '240', '1d': 'D'
}

class DataLoader:
    def __init__(self, exchange_id='bybit', api_key=None, secret=None, testnet=False):
        # Using Bybit public API - no US regional blocks on market data
        self.base_url = "https://api.bybit.com"
        self._symbol_info_cache = {}
        logger.info("Using Bybit public API for market data (no geo-restrictions).")
        self._load_exchange_info()

    def _load_exchange_info(self):
        """
        Fetches Bybit instrument info once at startup — gets min order sizes, fees etc.
        """
        try:
            url = f"{self.base_url}/v5/market/instruments-info"
            params = {"category": "linear", "limit": 1000}
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            for sym in data.get('result', {}).get('list', []):
                name = sym.get('symbol', '')
                if not name.endswith('USDT'):
                    continue

                lot_filter = sym.get('lotSizeFilter', {})
                price_filter = sym.get('priceFilter', {})

                min_qty = float(lot_filter.get('minOrderQty', 0.001))
                step_size = float(lot_filter.get('qtyStep', 0.001))
                tick_size = float(price_filter.get('tickSize', 0.01))
                # Bybit min notional is qty * price, approximate $1 minimum
                # We'll use $5 as safe default
                min_notional = max(float(lot_filter.get('minOrderAmt', 5.0)), 1.0)

                self._symbol_info_cache[name] = {
                    'min_notional': min_notional,
                    'min_qty': min_qty,
                    'step_size': step_size,
                    'tick_size': tick_size,
                    'taker_fee': BYBIT_TAKER_FEE,
                    'maker_fee': BYBIT_MAKER_FEE
                }

            logger.info(f"Loaded Bybit instrument info for {len(self._symbol_info_cache)} symbols.")

        except Exception as e:
            logger.error(f"Failed to load Bybit instrumentInfo: {e}. Using defaults.")

    def get_symbol_info(self, symbol):
        return self._symbol_info_cache.get(symbol, {
            'min_notional': 5.0,
            'min_qty': 0.001,
            'step_size': 0.001,
            'tick_size': 0.01,
            'taker_fee': BYBIT_TAKER_FEE,
            'maker_fee': BYBIT_MAKER_FEE
        })

    def round_step_size(self, quantity, step_size):
        if step_size == 0:
            return quantity
        precision = len(str(step_size).rstrip('0').split('.')[-1]) if '.' in str(step_size) else 0
        return round(int(quantity / step_size) * step_size, precision)

    def get_top_futures_symbols(self, top_n=20, min_volume_usd=50_000_000):
        """
        Fetches top N most actively traded USDT linear perp symbols by 24h volume from Bybit.
        """
        fallback = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT',
                    'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'DOTUSDT',
                    'MATICUSDT', 'LTCUSDT', 'ATOMUSDT', 'UNIUSDT', 'SHIBUSDT',
                    'AAVEUSDT', 'NEARUSDT', 'FTMUSDT', 'APTUSDT', 'ARBUSDT']
        try:
            url = f"{self.base_url}/v5/market/tickers"
            resp = requests.get(url, params={"category": "linear"}, timeout=10)
            resp.raise_for_status()
            tickers = resp.json().get('result', {}).get('list', [])

            usdt_pairs = [
                t for t in tickers
                if t['symbol'].endswith('USDT')
                and float(t.get('turnover24h', 0)) >= min_volume_usd
            ]
            usdt_pairs.sort(key=lambda x: float(x.get('turnover24h', 0)), reverse=True)
            symbols = [t['symbol'] for t in usdt_pairs[:top_n]]
            logger.info(f"Top {len(symbols)} Bybit futures by volume: {symbols}")
            return symbols if symbols else fallback[:top_n]

        except Exception as e:
            logger.error(f"Error fetching Bybit top symbols: {e}")
            return fallback[:top_n]

    def fetch_ohlcv(self, symbol, timeframe='1m', limit=100):
        """Fetches OHLCV candles from Bybit linear futures."""
        interval = INTERVAL_MAP.get(timeframe, '1')
        url = f"{self.base_url}/v5/market/kline"
        try:
            resp = requests.get(url, params={
                "category": "linear",
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            }, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            raw = data.get('result', {}).get('list', [])

            if not raw:
                return None

            # Bybit returns newest first, reverse to oldest-first
            raw = list(reversed(raw))
            candles = [{
                'timestamp': int(k[0]),
                'open': float(k[1]),
                'high': float(k[2]),
                'low': float(k[3]),
                'close': float(k[4]),
                'volume': float(k[5])
            } for k in raw]

            return candles

        except Exception as e:
            logger.error(f"Error fetching {symbol} from Bybit: {e}")
            return None

    def fetch_ticker(self, symbol):
        """Fetches latest price for a symbol from Bybit."""
        try:
            resp = requests.get(f"{self.base_url}/v5/market/tickers",
                                params={"category": "linear", "symbol": symbol}, timeout=5)
            resp.raise_for_status()
            items = resp.json().get('result', {}).get('list', [])
            if items:
                return float(items[0]['lastPrice'])
            return None
        except Exception as e:
            logger.error(f"Error fetching Bybit ticker for {symbol}: {e}")
            return None
