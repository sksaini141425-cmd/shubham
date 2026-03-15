"""
Enhanced Paper Exchange with Leverage Support
Integrates with the existing automated-trading-bot
"""
import logging
import json
import os
from datetime import datetime
from typing import Dict, Optional
from leverage_position_sizer import LeveragePositionSizer
from config_leverage import LEVERAGE, STARTING_BALANCE

logger = logging.getLogger(__name__)

class EnhancedPaperExchange:
    """
    Paper Trading Exchange with Leverage Support
    Manages positions, calculates sizes with leverage, tracks P&L
    """
    
    def __init__(self, initial_balance: float = STARTING_BALANCE, leverage: int = LEVERAGE, log_file: str = "trade_log_leverage.json"):
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.leverage = leverage
        self.position_sizer = LeveragePositionSizer(initial_balance, leverage)
        self.open_positions = {}
        self.trade_history = []
        self.log_file = log_file
        
        # Load previous history if exists
        self._load_history()
        
        logger.info(f"Enhanced Paper Exchange initialized with {leverage}x leverage")
        logger.info(f"Starting Balance: ${initial_balance:.2f}")
    
    def _load_history(self):
        """Load previous trades from log file"""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r') as f:
                    data = json.load(f)
                    self.trade_history = data.get('trades', [])
                    if self.trade_history:
                        self.balance = self.trade_history[-1].get('balance_after', self.balance)
                logger.info(f"Loaded {len(self.trade_history)} previous trades")
            except Exception as e:
                logger.warning(f"Could not load history: {e}")
    
    def open_position(self, symbol: str, side: str, entry_price: float, quantity: float, leverage: int = None) -> Dict:
        """
        Open a position with leverage
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            side: 'buy' or 'sell'
            entry_price: Entry price
            quantity: Position size
            leverage: Position leverage (optional, uses default if None)
        
        Returns:
            Position details dictionary
        """
        if leverage is None:
            leverage = self.leverage
        
        position_id = f"{symbol}_{side}_{datetime.now().timestamp()}"
        position_value = entry_price * quantity
        entry_fee = position_value * 0.0004  # 0.04% taker fee
        
        # Calculate stop loss and take profit
        stop_loss = self.position_sizer.get_stop_loss(entry_price, side)
        take_profit = self.position_sizer.get_take_profit(entry_price, side)
        
        position = {
            'id': position_id,
            'symbol': symbol,
            'side': side,
            'entry_price': entry_price,
            'quantity': quantity,
            'position_value': position_value,
            'leverage': leverage,
            'effective_exposure': position_value * leverage,
            'entry_fee': entry_fee,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'entry_time': datetime.now().isoformat(),
            'status': 'open',
            'pnl': 0,
            'pnl_percent': 0
        }
        
        self.open_positions[position_id] = position
        self.position_sizer.record_position_open(position_value)
        
        logger.info(f"✓ Opened {side.upper()} position {symbol}: {quantity:.8f} @ ${entry_price:.4f}")
        logger.info(f"  Position Value: ${position_value:.2f} | Effective: ${position['effective_exposure']:.2f}x")
        logger.info(f"  SL: ${stop_loss:.4f} | TP: ${take_profit:.4f}")
        
        return position
    
    def close_position(self, position_id: str, exit_price: float, reason: str = "Manual") -> Dict:
        """
        Close a position and realize P&L
        
        Args:
            position_id: Position ID to close
            exit_price: Exit price
            reason: Reason for closing (TP, SL, Manual, etc)
        
        Returns:
            Trade result dictionary
        """
        if position_id not in self.open_positions:
            logger.error(f"Position {position_id} not found")
            return {'error': 'Position not found'}
        
        position = self.open_positions[position_id]
        entry_price = position['entry_price']
        quantity = position['quantity']
        side = position['side']
        symbol = position['symbol']
        
        # Calculate P&L
        if side == 'buy':
            pnl = (exit_price - entry_price) * quantity
        else:
            pnl = (entry_price - exit_price) * quantity
        
        # Apply fees and funding costs
        entry_fee = position['entry_fee']
        exit_fee = exit_price * quantity * 0.0004  # Assume 0.04% maker fee
        total_fees = entry_fee + exit_fee
        
        net_pnl = pnl - total_fees
        pnl_percent = (net_pnl / (entry_price * quantity)) * 100
        
        # Update balance
        balance_before = self.balance
        self.balance += net_pnl
        self.position_sizer.update_balance(self.balance)
        
        # Record trade
        trade = {
            'timestamp': datetime.now().isoformat(),
            'position_id': position_id,
            'symbol': symbol,
            'side': side,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'quantity': quantity,
            'position_value': position['position_value'],
            'leverage': position['leverage'],
            'pnl': round(net_pnl, 6),
            'pnl_percent': round(pnl_percent, 2),
            'fees': round(total_fees, 6),
            'reason': reason,
            'balance_before': round(balance_before, 2),
            'balance_after': round(self.balance, 2)
        }
        
        self.trade_history.append(trade)
        self.position_sizer.record_position_close(position['position_value'])
        del self.open_positions[position_id]
        
        # Log trade
        emoji = "✓" if net_pnl > 0 else "✗"
        logger.info(f"{emoji} Closed {symbol} {side.upper()}: Entry ${entry_price:.4f} → Exit ${exit_price:.4f}")
        logger.info(f"   P&L: ${net_pnl:+.2f} ({pnl_percent:+.2f}%) | Fees: ${total_fees:.4f} | Reason: {reason}")
        logger.info(f"   Balance: ${balance_before:.2f} → ${self.balance:.2f}")
        
        self._save_history()
        
        return trade
    
    def update_position_price(self, position_id: str, current_price: float):
        """Update position unrealized P&L at current price"""
        if position_id not in self.open_positions:
            return
        
        position = self.open_positions[position_id]
        entry_price = position['entry_price']
        quantity = position['quantity']
        side = position['side']
        
        # Calculate unrealized P&L
        if side == 'buy':
            unrealized_pnl = (current_price - entry_price) * quantity
        else:
            unrealized_pnl = (entry_price - current_price) * quantity
        
        position['current_price'] = current_price
        position['pnl'] = unrealized_pnl
        position['pnl_percent'] = (unrealized_pnl / (entry_price * quantity)) * 100
    
    def check_tp_sl(self, position_id: str, current_price: float) -> Optional[Dict]:
        """
        Check if position should be closed due to TP/SL
        
        Returns:
            Trade result if closed, None otherwise
        """
        if position_id not in self.open_positions:
            return None
        
        position = self.open_positions[position_id]
        side = position['side']
        stop_loss = position['stop_loss']
        take_profit = position['take_profit']
        
        # Check stop loss
        if side == 'buy' and current_price <= stop_loss:
            return self.close_position(position_id, stop_loss, "Stop Loss")
        elif side == 'sell' and current_price >= stop_loss:
            return self.close_position(position_id, stop_loss, "Stop Loss")
        
        # Check take profit
        if side == 'buy' and current_price >= take_profit:
            return self.close_position(position_id, take_profit, "Take Profit")
        elif side == 'sell' and current_price <= take_profit:
            return self.close_position(position_id, take_profit, "Take Profit")
        
        return None
    
    def get_position_summary(self) -> Dict:
        """Get summary of all open positions"""
        total_unrealized = sum(p['pnl'] for p in self.open_positions.values())
        
        summary = {
            'open_positions': len(self.open_positions),
            'total_unrealized_pnl': round(total_unrealized, 2),
            'positions': []
        }
        
        for pos_id, pos in self.open_positions.items():
            summary['positions'].append({
                'symbol': pos['symbol'],
                'side': pos['side'],
                'entry': pos['entry_price'],
                'current': pos.get('current_price', pos['entry_price']),
                'quantity': pos['quantity'],
                'value': pos['position_value'],
                'unrealized_pnl': round(pos['pnl'], 2),
                'unrealized_pnl_pct': round(pos['pnl_percent'], 2)
            })
        
        return summary
    
    def get_account_summary(self) -> Dict:
        """Get complete account summary"""
        position_summary = self.get_position_summary()
        sizer_summary = self.position_sizer.get_summary()
        
        # Calculate statistics
        total_trades = len(self.trade_history)
        winning_trades = len([t for t in self.trade_history if t['pnl'] > 0])
        total_profit = sum(t['pnl'] for t in self.trade_history)
        
        return {
            'balance': round(self.balance, 2),
            'initial_balance': round(self.initial_balance, 2),
            'profit_loss': round(self.balance - self.initial_balance, 2),
            'roi_percent': round(((self.balance - self.initial_balance) / self.initial_balance) * 100, 2),
            'leverage': self.leverage,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'win_rate': round((winning_trades / total_trades * 100) if total_trades > 0 else 0, 2),
            'total_profit': round(total_profit, 2),
            'open_positions': position_summary['open_positions'],
            'total_unrealized_pnl': position_summary['total_unrealized_pnl'],
            'margin_level': sizer_summary['margin_level_percent'],
            'margin_warning': sizer_summary['margin_warning']
        }
    
    def _save_history(self):
        """Save trade history to file"""
        try:
            with open(self.log_file, 'w') as f:
                json.dump({'trades': self.trade_history}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")
    
    def print_summary(self):
        """Print account summary to console"""
        summary = self.get_account_summary()
        
        print("\n" + "="*80)
        print("ACCOUNT SUMMARY")
        print("="*80)
        print(f"Balance: ${summary['balance']:.2f} | ROI: {summary['roi_percent']:+.2f}%")
        print(f"Trades: {summary['total_trades']} | Win Rate: {summary['win_rate']:.1f}%")
        print(f"Unrealized P&L: ${summary['total_unrealized_pnl']:+.2f}")
        print(summary['margin_warning'])
        print("="*80 + "\n")
