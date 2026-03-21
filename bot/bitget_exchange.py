import ccxt
import logging
import time

logger = logging.getLogger(__name__)

class BitgetExchange:
    def __init__(self, api_key=None, api_secret=None, password=None, testnet=True, taker_fee=0.0006, symbol="BTCUSDT", client=None):
        """
        Bitget Futures Exchange Wrapper using CCXT.
        Bitget is cloud-friendly and often works where others are blocked.
        """
        if client:
            self.client = client
        else:
            self.client = ccxt.bitget({
                'apiKey': api_key,
                'secret': api_secret,
                'password': password,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'swap', # USDT-M Futures are 'swap' in Bitget
                    'adjustForTimeDifference': True,
                }
            })
            
            if testnet:
                self.client.set_sandbox_mode(True)
                logger.info("Initializing Bitget Futures Testnet connection...")
            else:
                logger.info("Initializing Bitget Futures Mainnet connection...")

        # Bitget CCXT symbol format for USDT-M: BTC/USDT:USDT
        if symbol.endswith("USDT") and ":" not in symbol:
             self.symbol = f"{symbol[:-4]}/{symbol[-4:]}:{symbol[-4:]}"
        else:
             self.symbol = symbol

        self.taker_fee = taker_fee
        self.shared_account = None 

        # Position tracking
        self.position_direction = None
        self.position_size = 0.0
        self.entry_price = 0.0
        
        try:
            self.client.load_markets()
            balance = self.client.fetch_balance()
            usdt_balance = balance['total'].get('USDT', 0.0)
            logger.info(f"✅ SUCCESS: Connected to Bitget. Balance: ${usdt_balance}")
        except Exception as e:
            logger.error(f"❌ Bitget Connection Failed: {e}")

    @property
    def cash(self):
        try:
            balance = self.client.fetch_balance()
            return float(balance['total'].get('USDT', 0.0))
        except Exception as e:
            logger.error(f"Error fetching balance from Bitget: {e}")
            return 0.0

    @property
    def is_in_position(self):
        self.sync_position()
        return self.position_direction is not None

    def sync_position(self):
        try:
            if self.symbol not in self.client.markets:
                return

            positions = self.client.fetch_positions([self.symbol])
            active_pos = None
            for pos in positions:
                if float(pos.get('contracts', 0)) > 0:
                    active_pos = pos
                    break

            if active_pos:
                self.position_direction = active_pos['side'].upper()
                self.position_size = float(active_pos['contracts'])
                self.entry_price = float(active_pos['entryPrice'])
            else:
                self.position_direction = None
                self.position_size = 0.0
                self.entry_price = 0.0
        except Exception as e:
            logger.error(f"Error syncing position for {self.symbol} on Bitget: {e}")

    def execute_market_order(self, direction, size, current_price, timestamp):
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
            
            logger.info(f"Executing Bitget Market {direction} order for {size} {self.symbol}")
            order = self.client.create_market_order(self.symbol, side, size, params=params)
            
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
            logger.error(f"Bitget Order Execution Error ({direction}): {e}")
            return False

    def get_unrealized_pnl(self, current_price):
        try:
            self.sync_position()
            if self.position_direction == 'LONG':
                return (current_price - self.entry_price) * self.position_size
            elif self.position_direction == 'SHORT':
                return (self.entry_price - current_price) * self.position_size
            return 0.0
        except Exception as e:
            logger.error(f"Error fetching uPnL from Bitget: {e}")
            return 0.0

    def check_liquidation(self, current_price, timestamp):
        return False

    def get_portfolio_value(self, current_price):
        return self.cash
