import requests
import logging
import time
import urllib3

# Increase connection pool size for high-frequency scanning
adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100)
session = requests.Session()
session.mount("https://", adapter)
session.mount("http://", adapter)

# Suppress insecure request warnings if needed
from urllib3.exceptions import InsecureRequestWarning
urllib3.disable_warnings(InsecureRequestWarning)

logger = logging.getLogger(__name__)

# Standard Binance-equivalent fees for simulation
TAKER_FEE = 0.0005   # 0.05%
MAKER_FEE = 0.0002   # 0.02%

# MEXC Public spot API - No US geo-block, no API key needed for basic market data
MEXC_BASE = "https://api.mexc.com/api/v3"

class DataLoader:
    def __init__(self, exchange_id='mexc', api_key=None, secret=None, testnet=False, ccxt_client=None):
        self._symbol_info_cache = {}
        self.exchange_id = exchange_id
        self.ccxt_client = ccxt_client
        logger.info(f"Using {exchange_id.upper()} for market data.")
        self._load_default_symbol_info()

    def _load_default_symbol_info(self):
        """Pre-populate known symbols with realistic Binance-like defaults."""
        # Top 10 pairs typically have these minimum notional requirements on Binance
        # Step size updated for low-capital/high-leverage precision (e.g. BTC 0.00001)
        self._symbol_info_cache = {
            'BTCUSDT': {'min_notional': 20.0, 'step_size': 0.00001, 'tick_size': 0.1, 'taker_fee': TAKER_FEE, 'maker_fee': MAKER_FEE},
            'ETHUSDT': {'min_notional': 20.0, 'step_size': 0.0001, 'tick_size': 0.01, 'taker_fee': TAKER_FEE, 'maker_fee': MAKER_FEE},
            'SOLUSDT': {'min_notional': 10.0, 'step_size': 0.01, 'tick_size': 0.01, 'taker_fee': TAKER_FEE, 'maker_fee': MAKER_FEE},
            'BNBUSDT': {'min_notional': 10.0, 'step_size': 0.001, 'tick_size': 0.01, 'taker_fee': TAKER_FEE, 'maker_fee': MAKER_FEE},
            'XRPUSDT': {'min_notional': 5.0, 'step_size': 0.1, 'tick_size': 0.0001, 'taker_fee': TAKER_FEE, 'maker_fee': MAKER_FEE},
            'DOGEUSDT': {'min_notional': 5.0, 'step_size': 0.1, 'tick_size': 0.00001, 'taker_fee': TAKER_FEE, 'maker_fee': MAKER_FEE},
            'ADAUSDT': {'min_notional': 5.0, 'step_size': 0.1, 'tick_size': 0.0001, 'taker_fee': TAKER_FEE, 'maker_fee': MAKER_FEE},
            'AVAXUSDT': {'min_notional': 5.0, 'step_size': 0.01, 'tick_size': 0.01, 'taker_fee': TAKER_FEE, 'maker_fee': MAKER_FEE},
            'LINKUSDT': {'min_notional': 5.0, 'step_size': 0.01, 'tick_size': 0.01, 'taker_fee': TAKER_FEE, 'maker_fee': MAKER_FEE},
            'DOTUSDT': {'min_notional': 5.0, 'step_size': 0.01, 'tick_size': 0.01, 'taker_fee': TAKER_FEE, 'maker_fee': MAKER_FEE},
        }
        # Fill others with standard $5 default
        for sym in ['MATICUSDT', 'LTCUSDT', 'ATOMUSDT', 'UNIUSDT', 'SHIBUSDT', 'AAVEUSDT', 'NEARUSDT', 'FTMUSDT', 'APTUSDT', 'ARBUSDT']:
            if sym not in self._symbol_info_cache:
                self._symbol_info_cache[sym] = {
                    'min_notional': 5.0,
                    'min_qty': 0.00001,
                    'step_size': 0.00001,
                    'tick_size': 0.01,
                    'taker_fee': TAKER_FEE,
                    'maker_fee': MAKER_FEE
                }

    def get_symbol_info(self, symbol):
        return self._symbol_info_cache.get(symbol, {
            'min_notional': 5.0,
            'min_qty': 0.00001,
            'step_size': 0.00001,
            'tick_size': 0.01,
            'taker_fee': TAKER_FEE,
            'maker_fee': MAKER_FEE
        })

    def round_step_size(self, quantity, step_size):
        if not step_size or step_size <= 0:
            return quantity
        
        # Calculate precision correctly even for scientific notation (e.g. 1e-05)
        import math
        precision = max(0, int(-math.log10(step_size))) if step_size < 1 else 0
        
        # Use floor division to avoid over-buying (safer for margin)
        rounded_qty = float(math.floor(quantity / step_size) * step_size)
        return round(rounded_qty, precision)

    def get_top_futures_symbols(self, top_n=60, min_volume_usd=1_000_000, offset=0):
        """Dynamically fetches the highest volume USDT pairs."""
        if self.ccxt_client:
            try:
                # Use load_markets to ensure market cache is populated
                markets = self.ccxt_client.load_markets()
                
                # Fetch all tickers to get volume data
                tickers = self.ccxt_client.fetch_tickers()
                
                valid_pairs = []
                for symbol, ticker in tickers.items():
                    try:
                        market = self.ccxt_client.market(symbol)
                        # Generic CCXT check for USDT linear perpetuals
                        # Bitget uses type='swap' and linear=True
                        is_linear = market.get('linear', False)
                        is_swap = market.get('type') == 'swap'
                        is_usdt = market.get('quote') == 'USDT'
                        
                        if not (is_linear and is_swap and is_usdt):
                            continue
                        
                        vol = float(ticker.get('quoteVolume', 0) or (ticker.get('baseVolume', 0) * ticker.get('last', 0)) or 0)
                        if vol >= min_volume_usd:
                            # Normalize symbol to BTCUSDT format
                            clean_sym = symbol.replace('/USDT:USDT', '').replace('USDT', '').replace('/', '').split(':')[0] + 'USDT'
                            valid_pairs.append({
                                'symbol': clean_sym,
                                'volume': vol
                            })
                    except:
                        continue
                
                # Sort by volume and take top_n
                valid_pairs.sort(key=lambda x: x['vol'], reverse=True)
                symbols = [p['symbol'] for p in valid_pairs[offset:offset+top_n]]
                
                if symbols:
                    logger.info(f"Fetched {len(symbols)} verified symbols from {self.exchange_id.upper()}.")
                    return symbols
            except Exception as e:
                logger.error(f"CCXT Top Symbols Error: {e}")
                # Fall through to MEXC fallback if CCXT fails

        data = None
        for attempt in range(3):
            try:
                # Note: verify=False is a workaround for local SSL protocol errors
                resp = session.get(f"{MEXC_BASE}/ticker/24hr", timeout=10, verify=False)
                resp.raise_for_status()
                data = resp.json()
                break # Success
            except Exception as e:
                logger.warning(f"Attempt {attempt+1} failed to fetch top symbols: {e}")
                if attempt < 2:
                    time.sleep(2)
                continue
        
        try:
            if not data:
                raise Exception("No data received from MEXC after retries")
            
            # Filter for USDT pairs and sort by quote volume (USD value)
            valid_pairs = []
            
            # --- EXCHANGE-SPECIFIC SYMBOL FILTER ---
            # If we are using a real exchange, only keep symbols that exist there
            valid_market_symbols = set()
            if self.ccxt_client:
                try:
                    for s, m in self.ccxt_client.markets.items():
                        # We want USDT linear perpetuals
                        if m.get('linear') and m.get('quote') == 'USDT':
                            # Normalize to our internal format BTCUSDT
                            clean = s.replace('/USDT:USDT', '').replace('USDT', '').replace('/', '').split(':')[0] + 'USDT'
                            valid_market_symbols.add(clean)
                except Exception as e:
                    logger.error(f"Error filtering exchange symbols: {e}")

            for item in data:
                if not item['symbol'].endswith('USDT'):
                    continue
                
                # If we have an exchange filter active, skip symbols not on that exchange
                if valid_market_symbols and item['symbol'] not in valid_market_symbols:
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
            
            # Fallback / pad so we always have enough markets
            fallback_list = [
                'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'DOTUSDT',
                'MATICUSDT', 'LTCUSDT', 'ATOMUSDT', 'UNIUSDT', 'SHIBUSDT', 'AAVEUSDT', 'NEARUSDT', 'FTMUSDT', 'APTUSDT', 'ARBUSDT',
                'GALAUSDT', 'ALGOUSDT', 'ICPUSDT', 'VETUSDT', 'FILUSDT', 'SANDUSDT', 'MANAUSDT', 'EOSUSDT', 'THETAUSDT', 'AXSUSDT',
                'EGLDUSDT', 'XTZUSDT', 'GRTUSDT', 'FLOWUSDT', 'CHZUSDT', 'MKRUSDT', 'CRVUSDT', 'ENJUSDT', 'BATUSDT',
                'STXUSDT', 'KSMUSDT', 'LRCUSDT', 'ONEUSDT', 'ZILUSDT', 'ANKRUSDT', 'RVNUSDT', 'IOTXUSDT', 'CELOUSDT', 'KAVAUSDT',
                'SUSHIUSDT', 'OMGUSDT', 'ZRXUSDT', 'ICXUSDT', 'IOSTUSDT', 'RENUSDT', 'STORJUSDT', 'SKLUSDT', 'SXPUSDT', 'OPUSDT',
                'INJUSDT', 'SUIUSDT', 'SEIUSDT', 'TIAUSDT', 'WLDUSDT', 'FETUSDT', 'RENDERUSDT', 'BONKUSDT', 'JUPUSDT',
            ]
            
            # --- EXCHANGE FALLBACK FILTER ---
            if valid_market_symbols:
                fallback_list = [s for s in fallback_list if s in valid_market_symbols]
            
            if not symbols:
                symbols = fallback_list[:top_n]
            elif len(symbols) < top_n:
                # Pad with fallback so dashboard shows full market list
                seen = set(symbols)
                for s in fallback_list:
                    if len(symbols) >= top_n:
                        break
                    if s not in seen:
                        symbols.append(s)
                        seen.add(s)
            logger.info(f"Dynamically fetched top {len(symbols)} symbols (Offset: {offset}, Limit: {top_n}).")
            return symbols
            
        except Exception as e:
            logger.error(f"Error fetching top symbols dynamically: {e}")
            fallback = [
                'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'DOTUSDT',
                'MATICUSDT', 'LTCUSDT', 'ATOMUSDT', 'UNIUSDT', 'SHIBUSDT', 'AAVEUSDT', 'NEARUSDT', 'FTMUSDT', 'APTUSDT', 'ARBUSDT',
                'GALAUSDT', 'ALGOUSDT', 'ICPUSDT', 'VETUSDT', 'FILUSDT', 'SANDUSDT', 'MANAUSDT', 'EOSUSDT', 'THETAUSDT', 'AXSUSDT',
                'EGLDUSDT', 'XTZUSDT', 'GRTUSDT', 'FLOWUSDT', 'CHZUSDT', 'MKRUSDT', 'CRVUSDT', 'ENJUSDT', 'BATUSDT',
                'STXUSDT', 'KSMUSDT', 'LRCUSDT', 'ONEUSDT', 'ZILUSDT', 'ANKRUSDT', 'RVNUSDT', 'IOTXUSDT', 'CELOUSDT', 'KAVAUSDT',
                'SUSHIUSDT', 'OMGUSDT', 'ZRXUSDT', 'ICXUSDT', 'IOSTUSDT', 'RENUSDT', 'STORJUSDT', 'SKLUSDT', 'SXPUSDT', 'OPUSDT',
                'INJUSDT', 'SUIUSDT', 'SEIUSDT', 'TIAUSDT', 'WLDUSDT', 'FETUSDT', 'RENDERUSDT', 'BONKUSDT', 'JUPUSDT',
            ]
            return fallback[offset : offset + top_n]

    def fetch_ohlcv(self, symbol, timeframe='5m', limit=400):
        """Fetches historical candles from configured exchange."""
        if self.ccxt_client:
            try:
                ccxt_sym = symbol
                if '/' not in symbol:
                    # Search the markets cache for the correct internal name
                    if hasattr(self.ccxt_client, 'markets') and self.ccxt_client.markets:
                        # Find the market where the internal name matches
                        for s, m in self.ccxt_client.markets.items():
                            clean = s.replace('/USDT:USDT', '').replace('USDT', '').replace('/', '').split(':')[0] + 'USDT'
                            if clean == symbol and m.get('linear') and m.get('quote') == 'USDT':
                                ccxt_sym = s
                                break
                    else:
                        # Fallback logic if markets not loaded
                        if symbol.endswith('USDT'):
                            ccxt_sym = f"{symbol[:-4]}/USDT:USDT"
                
                ohlcv = self.ccxt_client.fetch_ohlcv(ccxt_sym, timeframe, limit=limit)
                return [{
                    'timestamp': int(k[0]),
                    'open': float(k[1]),
                    'high': float(k[2]),
                    'low': float(k[3]),
                    'close': float(k[4]),
                    'volume': float(k[5])
                } for k in ohlcv]
            except Exception as e:
                logger.error(f"CCXT OHLCV Error for {symbol} ({ccxt_sym}): {e}")
                # Fall through to MEXC fallback if CCXT fails but only if not on Bybit (different data)
                if 'bybit' in str(self.ccxt_client.id).lower():
                    return None

        # MEXC Spot Fallback (Only if CCXT is not Bybit)
        endpoint = f"{MEXC_BASE}/klines"
        
        for attempt in range(3):
            try:
                # verify=False is used to bypass local SSL handshake failures
                resp = session.get(endpoint, params={
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
                
                if not data:
                    logger.warning(f"No OHLCV data returned from MEXC for {symbol}")
                    return []
                    
                # Format: [timestamp, open, high, low, close, volume, ...]
                return [{
                    'timestamp': int(k[0]),
                    'open': float(k[1]),
                    'high': float(k[2]),
                    'low': float(k[3]),
                    'close': float(k[4]),
                    'volume': float(k[5])
                } for k in data]
                
            except Exception as e:
                if attempt < 2:
                    time.sleep(2)
                    continue
                logger.error(f"Error fetching {symbol} from MEXC (SSL/ConnectionIssue): {e}")
                return None
                
        return None

    def fetch_ticker(self, symbol):
        """Fetches latest price from configured exchange."""
        if self.ccxt_client:
            try:
                ccxt_sym = symbol
                if '/' not in symbol:
                    # Search the markets cache for the correct internal name
                    if hasattr(self.ccxt_client, 'markets') and self.ccxt_client.markets:
                        for s, m in self.ccxt_client.markets.items():
                            clean = s.replace('/USDT:USDT', '').replace('USDT', '').replace('/', '').split(':')[0] + 'USDT'
                            if clean == symbol and m.get('linear') and m.get('quote') == 'USDT':
                                ccxt_sym = s
                                break
                    else:
                        if symbol.endswith('USDT'):
                            ccxt_sym = f"{symbol[:-4]}/USDT:USDT"
                
                ticker = self.ccxt_client.fetch_ticker(ccxt_sym)
                return float(ticker['last'])
            except Exception as e:
                logger.error(f"CCXT Ticker Error for {symbol} ({ccxt_sym}): {e}")
                if 'bybit' in str(self.ccxt_client.id).lower():
                    return None

        try:
            resp = session.get(f"{MEXC_BASE}/ticker/price", params={'symbol': symbol}, timeout=5, verify=False)
            resp.raise_for_status()
            return float(resp.json().get('price', 0))
        except Exception as e:
            logger.error(f"Error fetching MEXC ticker for {symbol}: {e}")
            return None
