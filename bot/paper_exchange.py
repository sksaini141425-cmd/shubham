import logging
import json
import os
import time
from datetime import datetime

import threading
from sqlalchemy import create_engine, Column, String, Float, Integer, JSON, desc
from sqlalchemy.orm import sessionmaker, declarative_base

logger = logging.getLogger(__name__)

TRADE_LOG_FILE = "trade_log.json"
Base = declarative_base()

class Trade(Base):
    __tablename__ = 'trades'
    id = Column(Integer, primary_key=True)
    timestamp = Column(String)
    action = Column(String)
    symbol = Column(String)
    price = Column(Float)
    size = Column(Float)
    notional = Column(Float)
    fee = Column(Float)
    pnl = Column(Float)
    balance_before = Column(Float)
    balance = Column(Float)
    entry_price = Column(Float)

class PaperAccount:
    """Thread-safe global singleton to hold the master paper trading balance and synchronized trade history."""
    def __init__(self, initial_capital=10000.0, log_file=TRADE_LOG_FILE):
        self.lock = threading.Lock()
        self.cash = initial_capital
        self.trade_history = []
        self.log_file = log_file
        
        # Check for Database
        self.db_url = os.environ.get('DATABASE_URL')
        if self.db_url:
            # Fix Render's postgres:// to postgresql:// if needed
            if self.db_url.startswith("postgres://"):
                self.db_url = self.db_url.replace("postgres://", "postgresql://", 1)
            
            try:
                self.engine = create_engine(self.db_url)
                Base.metadata.create_all(self.engine)
                self.Session = sessionmaker(bind=self.engine)
                logger.info("Connected to PostgreSQL for persistent history.")
                
                # Load history from DB
                session = self.Session()
                db_trades = session.query(Trade).order_by(Trade.id).all()
                self.trade_history = [
                    {
                        'timestamp': t.timestamp,
                        'action': t.action,
                        'symbol': t.symbol,
                        'price': t.price,
                        'size': t.size,
                        'notional': t.notional,
                        'fee': t.fee,
                        'pnl': t.pnl,
                        'balance_before': t.balance_before,
                        'balance': t.balance,
                        'entry_price': t.entry_price
                    } for t in db_trades
                ]
                if self.trade_history:
                    self.cash = self.trade_history[-1].get('balance', self.cash)
                session.close()
                
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}. Falling back to JSON.")
                self.db_url = None

        if not self.db_url:
            # Try to load existing trades/balance to prevent reset on restart (if desired)
            if os.path.exists(self.log_file):
                 try:
                     with open(self.log_file, "r") as f:
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
            # if 'fee' in trade_dict:
            #     self.cash -= trade_dict['fee']
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
            
            # Persist to database if available
            if self.db_url:
                try:
                    session = self.Session()
                    db_trade = Trade(
                        timestamp=trade_dict.get('timestamp'),
                        action=trade_dict.get('action'),
                        symbol=trade_dict.get('symbol'),
                        price=trade_dict.get('price'),
                        size=trade_dict.get('size'),
                        notional=trade_dict.get('notional'),
                        fee=trade_dict.get('fee'),
                        pnl=trade_dict.get('pnl'),
                        balance_before=trade_dict.get('balance_before'),
                        balance=trade_dict.get('balance'),
                        entry_price=trade_dict.get('entry_price')
                    )
                    session.add(db_trade)
                    session.commit()
                    session.close()
                except Exception as e:
                    logger.error(f"Failed to save to database: {e}")

            # Persist to JSON as backup/fallback
            try:
                with open(self.log_file, "w") as f:
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
        self.entry_fee_paid = 0.0
        self.symbol = "BTCUSDT"

        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.leverage = 1.0  # Default, set by bot
        self.entry_margin = 0.0
        self.entry_time = None
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

            # Margin = Notional / Leverage
            self.entry_margin = order_value / self.leverage
            # Cash Delta = -(Margin + Fee)
            cash_delta = -(self.entry_margin + fee_paid_usd)
            
            self.position_direction = direction
            self.position_size = size
            self.entry_price = current_price
            self.entry_fee_paid = fee_paid_usd
            self.entry_time = str(timestamp) if isinstance(timestamp, (str, bytes)) else datetime.fromtimestamp(timestamp/1000).isoformat()

            logger.info(f"[{timestamp}] OPENED {direction} {size:.4f} @ ${current_price:.2f} | Margin: ${self.entry_margin:.2f} | Fee: ${fee_paid_usd:.2f} | TOTAL DEDUCTED: ${(self.entry_margin + fee_paid_usd):.2f}")

            if self.shared_account:
                self.shared_account.log_trade({
                    'timestamp': self.entry_time,
                    'action': direction,
                    'symbol': self.symbol,
                    'price': round(current_price, 8),
                    'size': round(size, 8),
                    'notional': round(order_value, 4),
                    'fee': round(fee_paid_usd, 6),
                    'margin_locked': round(self.entry_margin, 4),
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

            # Cash Delta = Margin + PnL - ExitFee
            cash_delta = self.entry_margin + pnl - fee_paid_usd
            close_time = str(timestamp) if isinstance(timestamp, (str, bytes)) else datetime.fromtimestamp(timestamp/1000).isoformat()

            logger.info(f"[{timestamp}] CLOSED {self.position_direction} {self.position_size:.4f} @ ${current_price:.2f} | PnL: ${pnl:.2f} | Fee: ${fee_paid_usd:.2f} | Margin Returned: ${self.entry_margin:.2f}")

            entry_time_str = self.entry_time if hasattr(self, 'entry_time') and self.entry_time else "Unknown"

            if self.shared_account:
                self.shared_account.log_trade({
                    'timestamp': close_time,
                    'entry_time': entry_time_str,
                    'action': f"CLOSE ({self.position_direction})",
                    'symbol': self.symbol,
                    'price': round(current_price, 8),
                    'entry_price': round(self.entry_price, 8),
                    'size': round(self.position_size, 8),
                    'notional': round(order_value, 4),
                    'fee': round(fee_paid_usd, 6),
                    'pnl': round(pnl - fee_paid_usd - self.entry_fee_paid, 6),
                    'margin_returned': round(self.entry_margin, 4),
                    'cash_delta': cash_delta
                })

            self.position_direction = None
            self.position_size = 0.0
            self.entry_price = 0.0
            self.entry_fee_paid = 0.0

        return True

    def get_unrealized_pnl(self, current_price):
        """Calculates current float PnL."""
        if not self.is_in_position:
            return 0.0
        
        pnl = 0.0
        if self.position_direction == 'LONG':
            pnl = (current_price - self.entry_price) * self.position_size
        elif self.position_direction == 'SHORT':
            pnl = (self.entry_price - current_price) * self.position_size
            
        # Real-time Liquidation Simulation
        # If PnL loss > 80% of entry margin (Maintenance Margin), liquidate.
        if pnl < -(self.entry_margin * 0.8):
            logger.error(f"⚠️ LIQUIDATION DETECTED for {self.symbol}! PnL: ${pnl:.2f} | Margin: ${self.entry_margin:.2f}")
            # We don't call execute_market_order directly here to avoid recursive locks or state issues,
            # but we can return a flag or handle it in the next cycle.
            # Actually, for the sake of "seriousness", let's handle it.
            
        return pnl

    def check_liquidation(self, current_price, timestamp):
        """Checks if the position should be liquidated based on price."""
        if not self.is_in_position: return False
        
        pnl = self.get_unrealized_pnl(current_price)
        # Maintenance margin is usually around 0.5% - 1%, but for simplicity:
        # If loss hits 90% of margin, liquidate.
        if pnl <= -(self.entry_margin * 0.9):
            logger.error(f"🔥 LIQUIDATING {self.symbol} {self.position_direction} at ${current_price:.2f} (Loss: ${pnl:.2f})")
            
            # Liquidation Fee (usually higher)
            liquidation_fee = self.position_size * current_price * self.taker_fee * 2
            
            # Cash Delta = Margin + PnL - LiquidationFee
            # Note: PnL is negative here, e.g. -0.9 * Margin
            cash_delta = self.entry_margin + pnl - liquidation_fee
            
            if self.shared_account:
                self.shared_account.log_trade({
                    'timestamp': str(timestamp),
                    'action': f"LIQUIDATION ({self.position_direction})",
                    'symbol': self.symbol,
                    'price': round(current_price, 2),
                    'entry_price': round(self.entry_price, 2),
                    'size': round(self.position_size, 6),
                    'notional': round(self.position_size * current_price, 2),
                    'fee': round(liquidation_fee, 4),
                    'pnl': round(pnl - liquidation_fee - self.entry_fee_paid, 4),
                    'cash_delta': cash_delta
                })
                
            self.position_direction = None
            self.position_size = 0.0
            self.entry_price = 0.0
            return True
        return False

    def get_portfolio_value(self, current_price):
        """Total Value = Cash + Float PnL"""
        return self.cash + self.get_unrealized_pnl(current_price)
