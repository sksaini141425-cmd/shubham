import requests
import json
import logging

logger = logging.getLogger(__name__)

# Binance standard futures fees
BINANCE_MAKER_FEE = 0.0002  # 0.02%
BINANCE_TAKER_FEE = 0.0005  # 0.05%

class DataLoader:
    def __init__(self, exchange_id='binanceusdm', api_key=None, secret=None, testnet=True):
        # Always use mainnet for market DATA - public endpoints are not IP-blocked.
        # We only do paper trading (no real orders), so testnet is not needed.
        self.base_url = "https://fapi.binance.com"
        logger.info("Using Binance Mainnet public API for market data.")
        # Cache of per-symbol rules: {symbol: {min_notional, min_qty, step_size, ...}}
        self._symbol_info_cache = {}
        logger.info(f"Initialized native {exchange_id} data loader.")
        self._load_exchange_info()

    def _load_exchange_info(self):
        """
        Fetches Binance exchangeInfo once at startup and caches per-symbol rules:
        - min_notional: minimum order value in USDT
        - min_qty: minimum order quantity
        - step_size: quantity precision
        - taker_fee: always 0.05% on Binance USDM (same for all)
        - maker_fee: always 0.02% on Binance USDM (same for all)
        """
        try:
            url = f"{self.base_url}/fapi/v1/exchangeInfo"
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            for sym in data.get('symbols', []):
                name = sym['symbol']
                filters = {f['filterType']: f for f in sym.get('filters', [])}

                min_notional = float(filters.get('MIN_NOTIONAL', {}).get('notional', 5.0))
                min_qty = float(filters.get('LOT_SIZE', {}).get('minQty', 0.001))
                step_size = float(filters.get('LOT_SIZE', {}).get('stepSize', 0.001))
                tick_size = float(filters.get('PRICE_FILTER', {}).get('tickSize', 0.01))

                self._symbol_info_cache[name] = {
                    'min_notional': min_notional,    # USDT minimum order
                    'min_qty': min_qty,
                    'step_size': step_size,
                    'tick_size': tick_size,
                    'taker_fee': BINANCE_TAKER_FEE,  # 0.05% — same for all USDM
                    'maker_fee': BINANCE_MAKER_FEE    # 0.02% — same for all USDM
                }

            logger.info(f"Loaded exchange info for {len(self._symbol_info_cache)} symbols.")

        except Exception as e:
            logger.error(f"Failed to load exchangeInfo: {e}. Using defaults.")

    def get_symbol_info(self, symbol):
        """
        Returns per-symbol trade rules from Binance.
        Falls back to safe defaults if symbol not found.
        """
        return self._symbol_info_cache.get(symbol, {
            'min_notional': 5.0,
            'min_qty': 0.001,
            'step_size': 0.001,
            'tick_size': 0.01,
            'taker_fee': BINANCE_TAKER_FEE,
            'maker_fee': BINANCE_MAKER_FEE
        })

    def round_step_size(self, quantity, step_size):
        """Rounds quantity down to the nearest valid step size."""
        if step_size == 0:
            return quantity
        precision = len(str(step_size).rstrip('0').split('.')[-1]) if '.' in str(step_size) else 0
        return round(int(quantity / step_size) * step_size, precision)

    def get_top_futures_symbols(self, top_n=20, min_volume_usd=50_000_000):
        """
        Fetches the top N most actively traded USDT perpetual futures symbols by 24h volume.
        Filters out low-liquidity symbols.
        """
        fallback_symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT',
                            'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'DOTUSDT']

        if self.base_url == "https://testnet.binancefuture.com":
            logger.info("Testnet active. Bypassing dynamic top symbol fetch to avoid 451 errors.")
            return fallback_symbols[:top_n]

        try:
            url = f"{self.base_url}/fapi/v1/ticker/24hr"
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            tickers = resp.json()

            usdt_pairs = [
                t for t in tickers
                if t['symbol'].endswith('USDT')
                and float(t.get('quoteVolume', 0)) >= min_volume_usd
            ]
            usdt_pairs.sort(key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)
            symbols = [t['symbol'] for t in usdt_pairs[:top_n]]
            logger.info(f"Top {len(symbols)} futures by volume: {symbols}")
            return symbols

        except Exception as e:
            logger.error(f"Error fetching top symbols: {e}")
            return fallback_symbols[:top_n]

    def fetch_ohlcv(self, symbol, timeframe='1m', limit=100):
        """Fetches OHLCV candles from Binance USDM Futures."""
        native_symbol = symbol.replace('/', '').replace(':USDT', '')
        endpoint = f"{self.base_url}/fapi/v1/klines"
        parsed_data = []
        remaining_limit = limit
        end_time = None

        try:
            while remaining_limit > 0:
                fetch_amount = min(remaining_limit, 1500)
                params = {'symbol': native_symbol, 'interval': timeframe, 'limit': fetch_amount}
                if end_time:
                    params['endTime'] = end_time

                resp = requests.get(endpoint, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                if not data:
                    break

                chunk = [{
                    'timestamp': k[0], 'open': float(k[1]), 'high': float(k[2]),
                    'low': float(k[3]), 'close': float(k[4]), 'volume': float(k[5])
                } for k in data]

                parsed_data = chunk + parsed_data
                remaining_limit -= len(data)
                end_time = data[0][0] - 1

            return parsed_data[-limit:]

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching {native_symbol}: {e}")
            return None

    def fetch_ticker(self, symbol):
        """Fetches the latest price for a symbol."""
        native_symbol = symbol.replace('/', '').replace(':USDT', '')
        try:
            resp = requests.get(f"{self.base_url}/fapi/v1/ticker/price",
                                params={'symbol': native_symbol}, timeout=5)
            resp.raise_for_status()
            return float(resp.json()['price'])
        except Exception as e:
            logger.error(f"Error fetching ticker for {native_symbol}: {e}")
            return None
