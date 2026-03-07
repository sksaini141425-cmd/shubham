import logging
import json
import os
import time

logger = logging.getLogger(__name__)

TRADE_LOG_FILE = "trade_log.json"

def _save_trade_log(history):
    """Persist trade history to disk so the dashboard can read it."""
    try:
        with open(TRADE_LOG_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save trade log: {e}")

class PaperExchange:
    def __init__(self, initial_capital=10000.0, maker_fee=0.0002, taker_fee=0.0005):
        """
        Simulates Binance USDⓈ-M Futures execution.
        Default fees are standard Binance VIP0 rates (0.02% maker, 0.05% taker).
        """
        self.initial_capital = initial_capital
        self.cash = initial_capital

        # 'LONG', 'SHORT', or None
        self.position_direction = None
        self.position_size = 0.0
        self.entry_price = 0.0
        self.symbol = "BTCUSDT"

        self.maker_fee = maker_fee
        self.taker_fee = taker_fee

        self.trade_history = []
        logger.info(f"Initialized Paper Exchange with ${self.initial_capital} and {self.taker_fee*100}% Taker Fee.")

    @property
    def is_in_position(self):
        return self.position_direction is not None

    def execute_market_order(self, direction, size, current_price, timestamp):
        """Executes a simulated market order (long, short, or close)."""
        fee_paid_usd = size * current_price * self.taker_fee
        order_value = size * current_price

        if direction in ['LONG', 'SHORT']:
            if self.is_in_position:
                logger.warning("Attempted to open position while already in one.")
                return False

            balance_before = round(self.cash, 4)
            self.position_direction = direction
            self.position_size = size
            self.entry_price = current_price
            self.cash -= fee_paid_usd

            logger.info(f"[{timestamp}] OPENED {direction} {size:.4f} @ ${current_price:.2f} | Fee: ${fee_paid_usd:.2f}")

            self.trade_history.append({
                'timestamp': str(timestamp),
                'action': direction,
                'symbol': self.symbol,
                'price': round(current_price, 2),
                'size': round(size, 6),
                'notional': round(order_value, 2),
                'fee': round(fee_paid_usd, 4),
                'pnl': None,
                'balance_before': balance_before,
                'balance': round(self.cash, 4)
            })

        elif direction == 'CLOSE':
            if not self.is_in_position:
                logger.warning("Attempted to close position while flat.")
                return False

            pnl = 0.0
            if self.position_direction == 'LONG':
                pnl = (current_price - self.entry_price) * self.position_size
            elif self.position_direction == 'SHORT':
                pnl = (self.entry_price - current_price) * self.position_size

            balance_before = round(self.cash, 4)
            self.cash += (pnl - fee_paid_usd)

            logger.info(f"[{timestamp}] CLOSED {self.position_direction} {self.position_size:.4f} @ ${current_price:.2f} | PnL: ${pnl:.2f} | Fee: ${fee_paid_usd:.2f} | New Cash: ${self.cash:.2f}")

            self.trade_history.append({
                'timestamp': str(timestamp),
                'action': f"CLOSE ({self.position_direction})",
                'symbol': self.symbol,
                'price': round(current_price, 2),
                'entry_price': round(self.entry_price, 2),
                'size': round(self.position_size, 6),
                'notional': round(order_value, 2),
                'fee': round(fee_paid_usd, 4),
                'pnl': round(pnl - fee_paid_usd, 4),
                'balance_before': balance_before,
                'balance': round(self.cash, 4)
            })

            self.position_direction = None
            self.position_size = 0.0
            self.entry_price = 0.0

        _save_trade_log(self.trade_history)
        return True

    def get_unrealized_pnl(self, current_price):
        """Calculates current float PnL."""
        if not self.is_in_position:
            return 0.0
        if self.position_direction == 'LONG':
            return (current_price - self.entry_price) * self.position_size
        elif self.position_direction == 'SHORT':
            return (self.entry_price - current_price) * self.position_size
        return 0.0

    def get_portfolio_value(self, current_price):
        """Total Value = Cash + Float PnL"""
        return self.cash + self.get_unrealized_pnl(current_price)
