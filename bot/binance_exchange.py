import ccxt
import logging
import time

logger = logging.getLogger(__name__)

class BinanceExchange:
    def __init__(self, api_key=None, api_secret=None, testnet=False, taker_fee=0.0005, symbol="BTC/USDT"):
        """
        Binance USDⓈ-M Futures Exchange Wrapper using CCXT.
        """
        self.client = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'options': {
                'defaultType': 'future',
                'adjustForTimeDifference': True,
                'urls': {
                    'api': {
                        'fapiPublic': 'https://fapi.binance.com/fapi/v1',
                        'fapiPrivate': 'https://fapi.binance.com/fapi/v1',
                    }
                }
            }
        })
        
        self.symbol = symbol
        self.taker_fee = taker_fee
        self.shared_account = None 

        # Position tracking (cached from exchange)
        self.position_direction = None
        self.position_size = 0.0
        self.entry_price = 0.0
        
        try:
            # 1. Try NEW Demo Trading (Mainnet Endpoints, Sandbox=False)
            logger.info("Attempting connection to NEW Binance Demo (fapi.binance.com)...")
            self.client.set_sandbox_mode(False)
            
            # Use the Demo Trading specialized endpoints if they exist
            # but usually it's just the fapi.binance.com with Demo keys.
            
            self.client.load_markets()
            balance = self.client.fetch_balance()
            
            usdt_balance = balance['total'].get('USDT', 0.0)
            logger.info(f"✅ SUCCESS: Connected to Binance Demo. Virtual Balance: ${usdt_balance}")
        except Exception as e:
            logger.error(f"❌ Connection Failed: {e}")
            
            # Last ditch effort: Some users report that new Demo keys need 'demo-api' URLs
            try:
                logger.info("Retrying with 'demo-api.binance.com' URLs...")
                self.client.urls['api']['fapiPublic'] = 'https://demo-api.binance.com/fapi/v1'
                self.client.urls['api']['fapiPrivate'] = 'https://demo-api.binance.com/fapi/v1'
                self.client.load_markets()
                balance = self.client.fetch_balance()
                logger.info(f"✅ SUCCESS: Connected to Binance Demo (Special Demo URL). Balance: ${balance['total'].get('USDT', 0.0)}")
            except Exception as e2:
                 logger.error(f"❌ All connection attempts failed: {e2}")

    @property
    def cash(self):
        """Fetches available USDT balance from Binance."""
        try:
            balance = self.client.fetch_balance()
            return float(balance['total'].get('USDT', 0.0))
        except Exception as e:
            logger.error(f"Error fetching balance from Binance: {e}")
            return 0.0

    @property
    def is_in_position(self):
        """Checks if there's an active position for the current symbol."""
        self.sync_position()
        return self.position_direction is not None

    def sync_position(self):
        """Syncs local position state with Binance."""
        try:
            positions = self.client.fetch_positions([self.symbol])
            if not positions:
                self.position_direction = None
                self.position_size = 0.0
                self.entry_price = 0.0
                return

            pos = positions[0]
            size = float(pos['contracts'])
            if size > 0:
                self.position_direction = pos['side'].upper() # LONG or SHORT
                self.position_size = size
                self.entry_price = float(pos['entryPrice'])
            else:
                self.position_direction = None
                self.position_size = 0.0
                self.entry_price = 0.0
        except Exception as e:
            logger.error(f"Error syncing position for {self.symbol}: {e}")

    def execute_market_order(self, direction, size, current_price, timestamp):
        """Executes a market order on Binance."""
        try:
            side = 'buy' if direction in ['LONG'] else 'sell'
            params = {}
            
            if direction == 'CLOSE':
                self.sync_position()
                if not self.position_direction:
                    return False
                side = 'sell' if self.position_direction == 'LONG' else 'buy'
                size = self.position_size
                params['reduceOnly'] = True
            
            logger.info(f"Executing Binance Market {direction} order for {size} {self.symbol}")
            order = self.client.create_market_order(self.symbol, side, size, params=params)
            
            self.sync_position()
            
            if self.shared_account:
                fee = size * current_price * self.taker_fee
                action = direction
                if direction == 'CLOSE':
                    action = f"CLOSE ({self.position_direction})"
                
                self.shared_account.log_trade({
                    'timestamp': str(timestamp),
                    'action': action,
                    'symbol': self.symbol,
                    'price': round(current_price, 2),
                    'size': round(size, 6),
                    'fee': round(fee, 4),
                    'pnl': 0.0,
                    'cash_delta': 0.0
                })
            
            return True
        except Exception as e:
            logger.error(f"Binance Order Execution Error ({direction}): {e}")
            return False

    def get_unrealized_pnl(self, current_price):
        """Calculates current floating PnL for the active position."""
        try:
            self.sync_position()
            if self.position_direction == 'LONG':
                return (current_price - self.entry_price) * self.position_size
            elif self.position_direction == 'SHORT':
                return (self.entry_price - current_price) * self.position_size
            return 0.0
        except Exception as e:
            logger.error(f"Error fetching uPnL from Binance: {e}")
            return 0.0

    def check_liquidation(self, current_price, timestamp):
        """Real exchange handles liquidation, so this just returns False."""
        return False

    def get_portfolio_value(self, current_price):
        """Total Balance including unrealized PnL."""
        return self.cash # CCXT fetch_balance()['total'] usually includes everything
