import ccxt
import logging
import time

logger = logging.getLogger(__name__)

class BybitExchange:
    def __init__(self, api_key=None, api_secret=None, testnet=True, taker_fee=0.00055, symbol="BTC/USDT:USDT", client=None):
        """
        Bybit Unified Trading Account (UTA) Futures Exchange Wrapper using CCXT.
        Bybit is very stable in India and has a reliable Testnet.
        """
        if client:
            self.client = client
        else:
            # Bybit uses CCXT's unified API for futures
            self.client = ccxt.bybit({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'linear', # USDT-M Futures are 'linear' in Bybit
                    'adjustForTimeDifference': True,
                    'recvWindow': 10000,
                }
            })
            
            # Bybit Testnet handling
            if testnet:
                self.client.set_sandbox_mode(True)
                logger.info("Initializing Bybit Futures Testnet connection...")
            else:
                logger.info("Initializing Bybit Futures Mainnet connection...")

        # Bybit CCXT symbol format: BTC/USDT:USDT
        if symbol.endswith("USDT") and ":" not in symbol:
             self.symbol = f"{symbol[:-4]}/{symbol[-4:]}:{symbol[-4:]}"
        else:
             self.symbol = symbol

        self.taker_fee = taker_fee
        self.shared_account = None 

        # Position tracking (cached from exchange)
        self.position_direction = None
        self.position_size = 0.0
        self.entry_price = 0.0
        
        try:
            # Test connection and load markets
            self.client.load_markets()
            balance = self.client.fetch_balance()
            # In UTA, it's usually under 'total' -> 'USDT'
            usdt_balance = balance['total'].get('USDT', 0.0)
            logger.info(f"✅ SUCCESS: Connected to Bybit. Balance: ${usdt_balance}")
        except Exception as e:
            logger.error(f"❌ Bybit Connection Failed: {e}")

    @property
    def cash(self):
        """Fetches available USDT balance from Bybit."""
        try:
            balance = self.client.fetch_balance()
            return float(balance['total'].get('USDT', 0.0))
        except Exception as e:
            logger.error(f"Error fetching balance from Bybit: {e}")
            return 0.0

    @property
    def is_in_position(self):
        """Checks if there's an active position for the current symbol."""
        self.sync_position()
        return self.position_direction is not None

    def sync_position(self):
        """Syncs local position state with Bybit."""
        try:
            # Check if market exists before attempting to fetch positions
            if self.symbol not in self.client.markets:
                self.position_direction = None
                self.position_size = 0.0
                self.entry_price = 0.0
                return

            positions = self.client.fetch_positions([self.symbol])
            if not positions:
                self.position_direction = None
                self.position_size = 0.0
                self.entry_price = 0.0
                return

            # Bybit fetch_positions returns a list
            active_pos = None
            for pos in positions:
                if float(pos.get('contracts', 0)) > 0:
                    active_pos = pos
                    break

            if active_pos:
                self.position_direction = active_pos['side'].upper() # LONG or SHORT
                self.position_size = float(active_pos['contracts'])
                self.entry_price = float(active_pos['entryPrice'])
            else:
                self.position_direction = None
                self.position_size = 0.0
                self.entry_price = 0.0
        except Exception as e:
            logger.error(f"Error syncing position for {self.symbol} on Bybit: {e}")

    def execute_market_order(self, direction, size, current_price, timestamp):
        """Executes a market order on Bybit."""
        try:
            side = 'buy' if direction in ['LONG'] else 'sell'
            params = {}
            
            if direction == 'CLOSE':
                self.sync_position()
                if not self.position_direction:
                    return False
                # To close, we take the opposite side
                side = 'sell' if self.position_direction == 'LONG' else 'buy'
                size = self.position_size
                params['reduceOnly'] = True
            
            logger.info(f"Executing Bybit Market {direction} order for {size} {self.symbol}")
            order = self.client.create_market_order(self.symbol, side, size, params=params)
            
            # Brief pause for exchange to sync
            time.sleep(0.5)
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
            logger.error(f"Bybit Order Execution Error ({direction}): {e}")
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
            logger.error(f"Error fetching uPnL from Bybit: {e}")
            return 0.0

    def check_liquidation(self, current_price, timestamp):
        """Real exchange handles liquidation."""
        return False

    def get_portfolio_value(self, current_price):
        """Total Balance including unrealized PnL."""
        return self.cash
