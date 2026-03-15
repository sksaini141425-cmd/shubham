"""
Advanced Position Sizing with Leverage Support
Calculates position sizes for margin trading with dynamic minimum adjustments
"""
import logging
from typing import Dict, Tuple
from config_leverage import (
    LEVERAGE, USE_LEVERAGE, STARTING_BALANCE, RISK_PER_TRADE,
    MIN_POSITION_VALUE_USDT, STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT,
    MAX_CONCURRENT_POSITIONS, TAKER_FEE, MAKER_FEE, FUNDING_RATE,
    MAX_DAILY_LOSS_PERCENT, LIQUIDATION_LEVEL, WARNING_LEVEL
)

logger = logging.getLogger(__name__)

class LeveragePositionSizer:
    """
    Calculates position sizes with leverage to meet Binance minimum requirements
    Manages margin levels and liquidation risk
    """
    
    def __init__(self, account_balance: float = STARTING_BALANCE, leverage: int = LEVERAGE):
        self.account_balance = account_balance
        self.leverage = leverage if USE_LEVERAGE else 1
        self.effective_balance = account_balance * self.leverage
        self.open_positions = 0
        self.total_margin_used = 0.0
        self.daily_loss = 0.0
        
        logger.info(f"Position Sizer initialized:")
        logger.info(f"  Account Balance: ${account_balance:.2f}")
        logger.info(f"  Leverage: {self.leverage}x")
        logger.info(f"  Effective Balance: ${self.effective_balance:.2f}")
    
    def update_balance(self, new_balance: float):
        """Update account balance after trades"""
        self.account_balance = new_balance
        self.effective_balance = new_balance * self.leverage
        self.daily_loss = max(0, STARTING_BALANCE - new_balance)
    
    def can_open_position(self) -> Tuple[bool, str]:
        """
        Check if safe to open another position
        Returns: (can_open: bool, reason: str)
        """
        # Check position limit
        if self.open_positions >= MAX_CONCURRENT_POSITIONS:
            return False, f"Max positions ({MAX_CONCURRENT_POSITIONS}) reached"
        
        # Check daily loss limit
        loss_percent = (self.daily_loss / STARTING_BALANCE) * 100 if STARTING_BALANCE > 0 else 0
        if loss_percent >= MAX_DAILY_LOSS_PERCENT:
            return False, f"Daily loss limit ({MAX_DAILY_LOSS_PERCENT}%) exceeded"
        
        # Check margin level
        margin_percent = (self.total_margin_used / self.account_balance) * 100 if self.account_balance > 0 else 100
        if margin_percent >= (100 / self.leverage) * 0.80:  # 80% of available margin
            return False, f"Margin usage too high ({margin_percent:.1f}%)"
        
        return True, "OK"
    
    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss_price: float,
        pair: str = "UNKNOWN"
    ) -> Dict:
        """
        Calculate optimal position size with leverage to meet minimum
        
        Returns dictionary with:
        - position_size: amount to trade
        - position_value: notional value (before leverage)
        - margin_required: margin needed for this position
        - risk_amount: amount at risk
        - leverage_effect: effective exposure with leverage
        - meets_minimum: whether it meets Binance minimum
        """
        
        if entry_price <= 0 or stop_loss_price <= 0:
            return self._invalid_position()
        
        # Calculate risk parameters
        risk_amount = self.account_balance * RISK_PER_TRADE
        price_difference = abs(entry_price - stop_loss_price)
        
        if price_difference == 0:
            return self._invalid_position(reason="Stop loss equals entry price")
        
        # Position size WITHOUT leverage
        base_position_size = risk_amount / price_difference
        base_position_value = base_position_size * entry_price
        
        # WITH leverage - can use larger position
        if USE_LEVERAGE:
            # Leverage allows us to trade larger size with less capital
            leveraged_position_size = base_position_size * self.leverage
            leveraged_position_value = leveraged_position_size * entry_price
        else:
            leveraged_position_size = base_position_size
            leveraged_position_value = base_position_value
        
        # Check if meets minimum
        meets_minimum = leveraged_position_value >= MIN_POSITION_VALUE_USDT
        
        # If below minimum, scale up to meet minimum
        if not meets_minimum and self.effective_balance >= MIN_POSITION_VALUE_USDT:
            # Adjust to minimum
            adjusted_position_size = MIN_POSITION_VALUE_USDT / entry_price
            adjusted_position_value = MIN_POSITION_VALUE_USDT
            
            # Adjust risk amount accordingly
            adjusted_risk_amount = adjusted_position_size * price_difference
            
            logger.warning(
                f"Position for {pair} below minimum. Scaling up:\n"
                f"  Original: ${leveraged_position_value:.2f}\n"
                f"  Adjusted: ${adjusted_position_value:.2f}\n"
                f"  Risk: ${adjusted_risk_amount:.2f} ({adjusted_risk_amount/self.account_balance*100:.1f}% of capital)"
            )
            
            leverage_effect = adjusted_position_value
            margin_required = adjusted_position_value / self.leverage if self.leverage > 1 else adjusted_position_value
            
        else:
            adjusted_position_size = leveraged_position_size
            adjusted_position_value = leveraged_position_value
            adjusted_risk_amount = risk_amount
            leverage_effect = adjusted_position_value
            margin_required = adjusted_position_value / self.leverage if self.leverage > 1 else adjusted_position_value
        
        # Calculate fees
        entry_fee = adjusted_position_value * TAKER_FEE
        exit_fee = adjusted_position_value * MAKER_FEE
        holding_cost_per_hour = adjusted_position_value * (FUNDING_RATE / 8)  # 8-hour funding period
        
        result = {
            'position_size': round(adjusted_position_size, 8),
            'position_value': round(adjusted_position_value, 2),
            'margin_required': round(margin_required, 2),
            'risk_amount': round(adjusted_risk_amount, 2),
            'leverage_effect': round(leverage_effect, 2),
            'meets_minimum': meets_minimum or (adjusted_position_value >= MIN_POSITION_VALUE_USDT),
            'entry_fee': round(entry_fee, 4),
            'exit_fee': round(exit_fee, 4),
            'hourly_funding_cost': round(holding_cost_per_hour, 4),
            'total_trading_cost': round(entry_fee + exit_fee, 4),
            'leverage': self.leverage,
            'pair': pair
        }
        
        return result
    
    def _invalid_position(self, reason: str = "Invalid parameters") -> Dict:
        """Return invalid position dictionary"""
        return {
            'position_size': 0,
            'position_value': 0,
            'margin_required': 0,
            'risk_amount': 0,
            'leverage_effect': 0,
            'meets_minimum': False,
            'entry_fee': 0,
            'exit_fee': 0,
            'hourly_funding_cost': 0,
            'total_trading_cost': 0,
            'leverage': self.leverage,
            'valid': False,
            'reason': reason
        }
    
    def get_stop_loss(self, entry_price: float, side: str = 'long') -> float:
        """Calculate stop loss price"""
        if side == 'long':
            return entry_price * (1 - STOP_LOSS_PERCENT / 100)
        else:
            return entry_price * (1 + STOP_LOSS_PERCENT / 100)
    
    def get_take_profit(self, entry_price: float, side: str = 'long') -> float:
        """Calculate take profit price"""
        tp_pct = TAKE_PROFIT_PERCENT
        if side == 'long':
            return entry_price * (1 + tp_pct / 100)
        else:
            return entry_price * (1 - tp_pct / 100)
    
    def get_margin_level(self) -> float:
        """
        Get current margin level percentage
        100% = liquidation (on 1x)
        For 5x: ~20% = liquidation
        """
        if self.account_balance <= 0:
            return 100.0
        
        margin_percent = (self.total_margin_used / self.account_balance) * 100
        return min(margin_percent, 100.0)
    
    def is_liquidation_risk(self) -> Tuple[bool, float]:
        """
        Check if approaching liquidation
        Returns: (is_risky: bool, margin_level: float)
        """
        margin_level = self.get_margin_level()
        liquidation_threshold = (100 / self.leverage) * LIQUIDATION_LEVEL
        return margin_level >= liquidation_threshold, margin_level
    
    def get_margin_warning(self) -> str:
        """Get margin status message"""
        margin_level = self.get_margin_level()
        liquidation_threshold = (100 / self.leverage) * LIQUIDATION_LEVEL
        warning_threshold = (100 / self.leverage) * WARNING_LEVEL
        
        if margin_level >= liquidation_threshold:
            return f"🚨 LIQUIDATION RISK! Margin: {margin_level:.1f}% (limit: {liquidation_threshold:.1f}%)"
        elif margin_level >= warning_threshold:
            return f"⚠️  HIGH MARGIN USAGE: {margin_level:.1f}% (warning: {warning_threshold:.1f}%)"
        else:
            return f"✓ Safe margin level: {margin_level:.1f}%"
    
    def record_position_open(self, position_value: float):
        """Record opening a position"""
        self.open_positions += 1
        margin_required = position_value / self.leverage if self.leverage > 1 else position_value
        self.total_margin_used += margin_required
    
    def record_position_close(self, position_value: float):
        """Record closing a position"""
        if self.open_positions > 0:
            self.open_positions -= 1
        margin_freed = position_value / self.leverage if self.leverage > 1 else position_value
        self.total_margin_used = max(0, self.total_margin_used - margin_freed)
    
    def get_summary(self) -> Dict:
        """Get position sizer summary"""
        margin_level = self.get_margin_level()
        is_risky, _ = self.is_liquidation_risk()
        
        return {
            'account_balance': round(self.account_balance, 2),
            'leverage': self.leverage,
            'effective_balance': round(self.effective_balance, 2),
            'open_positions': self.open_positions,
            'margin_used': round(self.total_margin_used, 2),
            'margin_available': round(self.account_balance - self.total_margin_used, 2),
            'margin_level_percent': round(margin_level, 2),
            'liquidation_risk': is_risky,
            'daily_loss': round(self.daily_loss, 2),
            'margin_warning': self.get_margin_warning()
        }


# Example usage
if __name__ == "__main__":
    sizer = LeveragePositionSizer(account_balance=3.0, leverage=5)
    
    # Example: Open BTC position
    result = sizer.calculate_position_size(
        entry_price=68000,
        stop_loss_price=66640,  # 2% below
        pair='BTC/USDT'
    )
    
    print("Position Calculation Result:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    
    print("\nPosition Sizer Summary:")
    summary = sizer.get_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")
