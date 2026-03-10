import ccxt
import logging
import time
import os

logger = logging.getLogger(__name__)

class MEXCExchange:
    def __init__(self, api_key=None, api_secret=None, testnet=False, taker_fee=0.0002, symbol="BTC/USDT", client=None):
        """
        MEXC Futures Exchange Wrapper using CCXT.
        MEXC fees are generally lower than Binance (Taker ~0.02%).
        """
        if client:
            self.client = client
        else:
            # MEXC uses separate subdomains for futures
            self.client = ccxt.mexc({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'swap', # MEXC futures are 'swap'
                    'adjustForTimeDifference': True,
                    'recvWindow': 10000, # Increased from 5000
                }
            })
            
            # MEXC Testnet handling
            if testnet:
                # CCXT might not have a default sandbox URL for MEXC
                self.client.urls['api']['swap'] = 'https://futures.testnet.mexc.com/api/v1'
                self.client.urls['api']['public'] = 'https://futures.testnet.mexc.com/api/v1'
                self.client.urls['api']['private'] = 'https://futures.testnet.mexc.com/api/v1'
                logger.info("Initializing MEXC Futures Testnet connection (Manual URLs)...")
            else:
                logger.info("Initializing MEXC Futures Mainnet connection...")

        self.symbol = symbol
        self.taker_fee = taker_fee
        self.shared_account = None 

        # Position tracking (cached from exchange)
        self.position_direction = None
        self.position_size = 0.0
        self.entry_price = 0.0
        
        try:
            # Test connection and load markets
            logger.info("Syncing time with MEXC...")
            self.client.load_markets()
            if self.client.options.get('adjustForTimeDifference'):
                self.client.fetch_time()
            
            balance = self.client.fetch_balance()
            usdt_balance = balance['total'].get('USDT', 0.0)
            logger.info(f"✅ SUCCESS: Connected to MEXC. Balance: ${usdt_balance}")
        except Exception as e:
            logger.error(f"❌ MEXC Connection Failed: {e}")

    @property
    def cash(self):
        """Fetches available USDT balance from MEXC."""
        try:
            balance = self.client.fetch_balance()
            return float(balance['total'].get('USDT', 0.0))
        except Exception as e:
            logger.error(f"Error fetching balance from MEXC: {e}")
            return 0.0

    @property
    def is_in_position(self):
        """Checks if there's an active position for the current symbol."""
        self.sync_position()
        return self.position_direction is not None

    def sync_position(self):
        """Syncs local position state with MEXC."""
        try:
            # MEXC specific: fetch_positions for swap
            positions = self.client.fetch_positions([self.symbol])
            if not positions:
                self.position_direction = None
                self.position_size = 0.0
                self.entry_price = 0.0
                return

            # Find the active position for this symbol
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
            logger.error(f"Error syncing position for {self.symbol} on MEXC: {e}")

    def execute_market_order(self, direction, size, current_price, timestamp):
        """Executes a market order on MEXC."""
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
                # MEXC specific: reduce-only parameter
                params['reduceOnly'] = True
            
            logger.info(f"Executing MEXC Market {direction} order for {size} {self.symbol}")
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
            logger.error(f"MEXC Order Execution Error ({direction}): {e}")
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
            logger.error(f"Error fetching uPnL from MEXC: {e}")
            return 0.0

    def check_liquidation(self, current_price, timestamp):
        """Real exchange handles liquidation."""
        return False

    def get_portfolio_value(self, current_price):
        """Total Balance including unrealized PnL."""
        return self.cash
