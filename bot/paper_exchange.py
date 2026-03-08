import logging
import json
import os
import time

import threading

logger = logging.getLogger(__name__)

TRADE_LOG_FILE = "trade_log.json"

class PaperAccount:
    """Thread-safe global singleton to hold the master paper trading balance and synchronized trade history."""
    def __init__(self, initial_capital=10000.0):
        self.lock = threading.Lock()
        self.cash = initial_capital
        self.trade_history = []
        
        # Try to load existing trades/balance to prevent reset on restart (if desired)
        if os.path.exists(TRADE_LOG_FILE):
             try:
                 with open(TRADE_LOG_FILE, "r") as f:
                     self.trade_history = json.load(f)
                 if self.trade_history:
                     # Resume balance from the very last logged trade
                     self.cash = self.trade_history[-1].get('balance', self.cash)
             except Exception as e:
                 logger.error(f"Failed to load existing trade log: {e}")

    def get_cash(self):
        with self.lock:
            return self.cash

    def log_trade(self, trade_dict):
        """Thread-safely deducts/adds fee and PnL, logs trade, and saves to disk."""
        with self.lock:
            balance_before = self.cash
            
            # Apply fees and PnL to the master cash balance
            if 'fee' in trade_dict:
                self.cash -= trade_dict['fee']
            if 'pnl' in trade_dict and trade_dict['pnl'] is not None:
                # The incoming pnl SHOULD NOT already have fees deducted here, we just deduct fee above.
                # Actually, our execute_market_order handles fee logic carefully, let's keep it simple: 
                # If it's a CLOSE, the net change to cash is (PnL - CloseFee).
                # If it's an OPEN, the net change is (-OpenFee).
                pass # We will expect the caller to pass the EXACT cash delta instead.
                
            # Better approach: Caller tells us exactly how much to alter cash by
            if 'cash_delta' in trade_dict:
                self.cash += trade_dict['cash_delta']
                del trade_dict['cash_delta'] # Don't save this internal field to JSON
                
            trade_dict['balance_before'] = round(balance_before, 4)
            trade_dict['balance'] = round(self.cash, 4)
            
            self.trade_history.append(trade_dict)
            
            # Persist to disk
            try:
                with open(TRADE_LOG_FILE, "w") as f:
                    json.dump(self.trade_history, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to save trade log: {e}")
            
            return self.cash

class PaperExchange:
    def __init__(self, initial_capital=10000.0, maker_fee=0.0002, taker_fee=0.0005):
        """
        Simulates Binance USDⓈ-M Futures execution.
        Default fees are standard Binance VIP0 rates (0.02% maker, 0.05% taker).
        """
        self.shared_account = None  # Will be injected
        # Note: self.cash is now just a local property that reads from shared_account


        # 'LONG', 'SHORT', or None
        self.position_direction = None
        self.position_size = 0.0
        self.entry_price = 0.0
        self.symbol = "BTCUSDT"

        self.maker_fee = maker_fee
        self.taker_fee = taker_fee

        logger.info(f"Initialized Paper Exchange with {self.taker_fee*100}% Taker Fee.")

    @property
    def cash(self):
        if self.shared_account:
            return self.shared_account.get_cash()
        return 0.0

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

            cash_delta = -fee_paid_usd
            
            self.position_direction = direction
            self.position_size = size
            self.entry_price = current_price

            logger.info(f"[{timestamp}] OPENED {direction} {size:.4f} @ ${current_price:.2f} | Fee: ${fee_paid_usd:.2f}")

            if self.shared_account:
                self.shared_account.log_trade({
                    'timestamp': str(timestamp),
                    'action': direction,
                    'symbol': self.symbol,
                    'price': round(current_price, 2),
                    'size': round(size, 6),
                    'notional': round(order_value, 2),
                    'fee': round(fee_paid_usd, 4),
                    'pnl': None,
                    'cash_delta': cash_delta
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

            cash_delta = pnl - fee_paid_usd

            logger.info(f"[{timestamp}] CLOSED {self.position_direction} {self.position_size:.4f} @ ${current_price:.2f} | PnL: ${pnl:.2f} | Fee: ${fee_paid_usd:.2f}")

            if self.shared_account:
                self.shared_account.log_trade({
                    'timestamp': str(timestamp),
                    'action': f"CLOSE ({self.position_direction})",
                    'symbol': self.symbol,
                    'price': round(current_price, 2),
                    'entry_price': round(self.entry_price, 2),
                    'size': round(self.position_size, 6),
                    'notional': round(order_value, 2),
                    'fee': round(fee_paid_usd, 4),
                    'pnl': round(pnl - fee_paid_usd, 4),
                    'cash_delta': cash_delta
                })

            self.position_direction = None
            self.position_size = 0.0
            self.entry_price = 0.0

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
