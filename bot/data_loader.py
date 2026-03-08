import requests
import logging
import time

logger = logging.getLogger(__name__)

# Standard Binance-equivalent fees for simulation
TAKER_FEE = 0.0005   # 0.05%
MAKER_FEE = 0.0002   # 0.02%

# CryptoCompare public API — no API key needed for basic OHLCV, no US geo-block
CRYPTOCOMPARE_BASE = "https://min-api.cryptocompare.com/data/v2"

# Map of symbol → CryptoCompare base symbol (strip USDT)
def _to_cc_symbol(symbol):
    return symbol.replace('USDT', '')

class DataLoader:
    def __init__(self, exchange_id='cryptocompare', api_key=None, secret=None, testnet=False):
        self._symbol_info_cache = {}
        logger.info("Using CryptoCompare public API for market data (US-accessible, no geo-block).")
        # Pre-populate symbol info with known defaults (CryptoCompare doesn't have futures-style info)
        self._load_default_symbol_info()

    def _load_default_symbol_info(self):
        """Pre-populate known symbols with standard defaults."""
        symbols = [
            'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT',
            'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'DOTUSDT',
            'MATICUSDT', 'LTCUSDT', 'ATOMUSDT', 'UNIUSDT', 'SHIBUSDT',
            'AAVEUSDT', 'NEARUSDT', 'FTMUSDT', 'APTUSDT', 'ARBUSDT'
        ]
        for sym in symbols:
            self._symbol_info_cache[sym] = {
                'min_notional': 5.0,
                'min_qty': 0.001,
                'step_size': 0.001,
                'tick_size': 0.01,
                'taker_fee': TAKER_FEE,
                'maker_fee': MAKER_FEE
            }
        logger.info(f"Pre-loaded default info for {len(symbols)} symbols.")

    def get_symbol_info(self, symbol):
        return self._symbol_info_cache.get(symbol, {
            'min_notional': 5.0,
            'min_qty': 0.001,
            'step_size': 0.001,
            'tick_size': 0.01,
            'taker_fee': TAKER_FEE,
            'maker_fee': MAKER_FEE
        })

    def round_step_size(self, quantity, step_size):
        if step_size == 0:
            return quantity
        precision = len(str(step_size).rstrip('0').split('.')[-1]) if '.' in str(step_size) else 0
        return round(int(quantity / step_size) * step_size, precision)

    def get_top_futures_symbols(self, top_n=20, min_volume_usd=50_000_000):
        """Returns hardcoded top symbols — CryptoCompare sorting isn't needed since we always scan the same set."""
        symbols = [
            'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT',
            'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'DOTUSDT',
            'MATICUSDT', 'LTCUSDT', 'ATOMUSDT', 'UNIUSDT', 'SHIBUSDT',
            'AAVEUSDT', 'NEARUSDT', 'ARBUSDT', 'APTUSDT', 'OPUSDT'
        ]
        logger.info(f"Scanning {top_n} hardcoded symbols: {symbols[:top_n]}")
        return symbols[:top_n]

    def fetch_ohlcv(self, symbol, timeframe='1m', limit=100):
        """
        Fetches OHLCV candles from CryptoCompare.
        No US geo-restrictions. No API key required (100k/month free tier).
        """
        base = _to_cc_symbol(symbol)

        # Map timeframe to CryptoCompare endpoint
        if timeframe in ['1m', '3m', '5m', '15m', '30m']:
            endpoint = f"{CRYPTOCOMPARE_BASE}/histominute"
            aggregate = int(timeframe.replace('m', ''))
        elif timeframe in ['1h', '2h', '4h']:
            endpoint = f"{CRYPTOCOMPARE_BASE}/histohour"
            aggregate = int(timeframe.replace('h', ''))
        else:
            endpoint = f"{CRYPTOCOMPARE_BASE}/histoday"
            aggregate = 1

        for attempt in range(3):
            try:
                resp = requests.get(endpoint, params={
                    'fsym': base,
                    'tsym': 'USDT',
                    'limit': limit,
                    'aggregate': aggregate
                }, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                if data.get('Response') == 'Error':
                    msg = data.get('Message', '')
                    if 'rate limit' in msg.lower() and attempt < 2:
                        logger.warning(f"CryptoCompare rate limit for {symbol}. Retrying in 3s...")
                        time.sleep(3)
                        continue
                    logger.error(f"CryptoCompare error for {symbol}: {msg}")
                    return None
                    
                break # Success, exit retry loop
            except Exception as e:
                if attempt < 2:
                    time.sleep(2)
                    continue
                logger.error(f"Error fetching {symbol} from CryptoCompare: {e}")
                return None

            raw = data.get('Data', {}).get('Data', [])
            if not raw:
                return None

            candles = [{
                'timestamp': int(k['time']) * 1000,
                'open': float(k['open']),
                'high': float(k['high']),
                'low': float(k['low']),
                'close': float(k['close']),
                'volume': float(k['volumefrom'])
            } for k in raw if k['close'] > 0]

            return candles if candles else None

        return None

    def fetch_ticker(self, symbol):
        """Fetches latest price from CryptoCompare."""
        base = _to_cc_symbol(symbol)
        try:
            resp = requests.get("https://min-api.cryptocompare.com/data/price",
                                params={'fsym': base, 'tsyms': 'USDT'}, timeout=5)
            resp.raise_for_status()
            return float(resp.json().get('USDT', 0))
        except Exception as e:
            logger.error(f"Error fetching CryptoCompare ticker for {symbol}: {e}")
            return None
