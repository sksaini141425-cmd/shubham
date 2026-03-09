import ccxt
import logging
import time

logger = logging.getLogger(__name__)

class BinanceExchange:
    def __init__(self, api_key=None, api_secret=None, testnet=True, taker_fee=0.0005):
        """
        Binance USDⓈ-M Futures Exchange Wrapper using CCXT.
        """
        self.client = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'options': {
                'defaultType': 'future'
            }
        })
        if testnet:
            self.client.set_sandbox_mode(True)
        
        self.symbol = "BTC/USDT"
        self.taker_fee = taker_fee
        self.shared_account = None  # For compatibility with main.py logic

        # Position tracking (cached from exchange)
        self.position_direction = None
        self.position_size = 0.0
        self.entry_price = 0.0
        
        try:
            # Test connection and load markets
            logger.info(f"Loading Binance {'Testnet' if testnet else 'Mainnet'} markets...")
            self.client.load_markets()
            self.client.fetch_balance()
            logger.info(f"Connected to Binance {'Testnet' if testnet else 'Mainnet'} Futures.")
        except Exception as e:
            logger.error(f"Failed to connect to Binance: {e}")

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
                    'pnl': None,
                    'cash_delta': 0
                })
            
            return True
        except Exception as e:
            logger.error(f"Binance Order Execution Error ({direction}): {e}")
            return False

    def get_unrealized_pnl(self, current_price):
        """Fetches uPnL directly from Binance."""
        try:
            positions = self.client.fetch_positions([self.symbol])
            if positions:
                return float(positions[0].get('unrealizedPnl', 0.0))
        except Exception as e:
            logger.error(f"Error fetching uPnL from Binance: {e}")
        return 0.0

    def get_portfolio_value(self, current_price):
        """Total Balance including unrealized PnL."""
        return self.cash # CCXT fetch_balance()['total'] usually includes everything
