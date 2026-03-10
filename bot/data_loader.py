import requests
import logging
import time

logger = logging.getLogger(__name__)

# Standard Binance-equivalent fees for simulation
TAKER_FEE = 0.0005   # 0.05%
MAKER_FEE = 0.0002   # 0.02%

# MEXC Public spot API - No US geo-block, no API key needed for basic market data
MEXC_BASE = "https://api.mexc.com/api/v3"

class DataLoader:
    def __init__(self, exchange_id='mexc', api_key=None, secret=None, testnet=False):
        self._symbol_info_cache = {}
        logger.info("Using MEXC public API for market data (US-accessible, reliable).")
        self._load_default_symbol_info()

    def _load_default_symbol_info(self):
        """Pre-populate known symbols with realistic Binance-like defaults."""
        # Top 10 pairs typically have these minimum notional requirements on Binance
        self._symbol_info_cache = {
            'BTCUSDT': {'min_notional': 20.0, 'step_size': 0.001, 'tick_size': 0.1, 'taker_fee': TAKER_FEE, 'maker_fee': MAKER_FEE},
            'ETHUSDT': {'min_notional': 20.0, 'step_size': 0.01, 'tick_size': 0.01, 'taker_fee': TAKER_FEE, 'maker_fee': MAKER_FEE},
            'SOLUSDT': {'min_notional': 10.0, 'step_size': 1.0, 'tick_size': 0.01, 'taker_fee': TAKER_FEE, 'maker_fee': MAKER_FEE},
            'BNBUSDT': {'min_notional': 10.0, 'step_size': 0.01, 'tick_size': 0.01, 'taker_fee': TAKER_FEE, 'maker_fee': MAKER_FEE},
            'XRPUSDT': {'min_notional': 5.0, 'step_size': 1.0, 'tick_size': 0.0001, 'taker_fee': TAKER_FEE, 'maker_fee': MAKER_FEE},
            'DOGEUSDT': {'min_notional': 5.0, 'step_size': 1.0, 'tick_size': 0.00001, 'taker_fee': TAKER_FEE, 'maker_fee': MAKER_FEE},
            'ADAUSDT': {'min_notional': 5.0, 'step_size': 1.0, 'tick_size': 0.0001, 'taker_fee': TAKER_FEE, 'maker_fee': MAKER_FEE},
            'AVAXUSDT': {'min_notional': 10.0, 'step_size': 0.1, 'tick_size': 0.01, 'taker_fee': TAKER_FEE, 'maker_fee': MAKER_FEE},
            'LINKUSDT': {'min_notional': 10.0, 'step_size': 0.1, 'tick_size': 0.001, 'taker_fee': TAKER_FEE, 'maker_fee': MAKER_FEE},
            'DOTUSDT': {'min_notional': 10.0, 'step_size': 0.1, 'tick_size': 0.001, 'taker_fee': TAKER_FEE, 'maker_fee': MAKER_FEE},
        }
        # Fill others with standard $5 default
        for sym in ['MATICUSDT', 'LTCUSDT', 'ATOMUSDT', 'UNIUSDT', 'SHIBUSDT', 'AAVEUSDT', 'NEARUSDT', 'FTMUSDT', 'APTUSDT', 'ARBUSDT']:
            if sym not in self._symbol_info_cache:
                self._symbol_info_cache[sym] = {
                    'min_notional': 5.0,
                    'min_qty': 0.001,
                    'step_size': 0.001,
                    'tick_size': 0.01,
                    'taker_fee': TAKER_FEE,
                    'maker_fee': MAKER_FEE
                }

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

    def get_top_futures_symbols(self, top_n=60, min_volume_usd=1_000_000, offset=0):
        """Dynamically fetches the highest volume USDT pairs from MEXC."""
        try:
            # Note: verify=False is a workaround for local SSL protocol errors
            resp = requests.get(f"{MEXC_BASE}/ticker/24hr", timeout=10, verify=False)
            resp.raise_for_status()
            data = resp.json()
            
            # Filter for USDT pairs and sort by quote volume (USD value)
            valid_pairs = []
            for item in data:
                if not item['symbol'].endswith('USDT'):
                    continue
                    
                # Exclude leveraged tokens or weird pairs (usually contain numbers or down/up)
                if 'UPUSDT' in item['symbol'] or 'DOWNUSDT' in item['symbol'] or 'BEAR' in item['symbol'] or 'BULL' in item['symbol']:
                    continue
                    
                vol = float(item.get('quoteVolume', 0))
                if vol >= min_volume_usd:
                    valid_pairs.append({'symbol': item['symbol'], 'vol': vol})
            
            # Sort by volume descending
            valid_pairs.sort(key=lambda x: x['vol'], reverse=True)
            
            # Extract symbols with offset and limit
            symbols = [p['symbol'] for p in valid_pairs[offset : offset + top_n]]
            
            # Fallback if API fails to return enough pairs
            if not symbols:
                symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT']
                
            logger.info(f"Dynamically fetched top {len(symbols)} symbols (Offset: {offset}, Limit: {top_n}).")
            return symbols
            
        except Exception as e:
            logger.error(f"Error fetching top symbols dynamically: {e}")
            fallback = [
                'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'DOTUSDT',
                'MATICUSDT', 'LTCUSDT', 'ATOMUSDT', 'UNIUSDT', 'SHIBUSDT', 'AAVEUSDT', 'NEARUSDT', 'FTMUSDT', 'APTUSDT', 'ARBUSDT',
                'GALAUSDT', 'ALGOUSDT', 'ICPUSDT', 'VETUSDT', 'FILUSDT', 'SANDUSDT', 'MANAUSDT', 'EOSUSDT', 'THETAUSDT', 'AXSUSDT',
                'EGLDUSDT', 'XTZUSDT', 'GRTUSDT', 'AAVEUSDT', 'FLOWUSDT', 'CHZUSDT', 'MKRUSDT', 'CRVUSDT', 'ENJUSDT', 'BATUSDT',
                'STXUSDT', 'KSMUSDT', 'LRCUSDT', 'ONEUSDT', 'ZILUSDT', 'ANKRUSDT', 'RVNUSDT', 'IOTXUSDT', 'CELOUSDT', 'KAVAUSDT',
                'SUSHIUSDT', 'OMGUSDT', 'ZRXUSDT', 'ICXUSDT', 'IOSTUSDT', 'RENUSDT', 'STORJUSDT', 'SKLUSDT', 'SXPUSDT', 'SRMUSDT'
            ]
            return fallback[offset : offset + top_n]

    def fetch_ohlcv(self, symbol, timeframe='1m', limit=100):
        """
        Fetches OHLCV candles from MEXC public API.
        MEXC uses the exact same return format as Binance.
        """
        endpoint = f"{MEXC_BASE}/klines"
        
        for attempt in range(3):
            try:
                # verify=False is used to bypass local SSL handshake failures
                resp = requests.get(endpoint, params={
                    'symbol': symbol,
                    'interval': timeframe,
                    'limit': limit
                }, timeout=10, verify=False)
                
                if resp.status_code == 429: # Rate limited
                    logger.warning(f"MEXC rate limit hit for {symbol}. Backing off 3s...")
                    time.sleep(3)
                    continue
                    
                resp.raise_for_status()
                data = resp.json()

                if not data or not isinstance(data, list):
                    return None

                candles = [{
                    'timestamp': int(k[0]),
                    'open': float(k[1]),
                    'high': float(k[2]),
                    'low': float(k[3]),
                    'close': float(k[4]),
                    'volume': float(k[5])
                } for k in data]

                return candles
                
            except Exception as e:
                if attempt < 2:
                    time.sleep(2)
                    continue
                logger.error(f"Error fetching {symbol} from MEXC (SSL/ConnectionIssue): {e}")
                return None
                
        return None

    def fetch_ticker(self, symbol):
        """Fetches latest price from MEXC."""
        try:
            resp = requests.get(f"{MEXC_BASE}/ticker/price", params={'symbol': symbol}, timeout=5, verify=False)
            resp.raise_for_status()
            return float(resp.json().get('price', 0))
        except Exception as e:
            logger.error(f"Error fetching MEXC ticker for {symbol}: {e}")
            return None
