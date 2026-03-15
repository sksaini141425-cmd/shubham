#!/usr/bin/env python3
"""
Example: Using Leverage with Enhanced Position Sizer
Demonstrates how to integrate leverage trading into the existing bot
"""

import sys
import logging
from datetime import datetime

# Import the leverage modules
from leverage_position_sizer import LeveragePositionSizer
from enhanced_paper_exchange import EnhancedPaperExchange
from config_leverage import (
    STARTING_BALANCE, LEVERAGE, RISK_PER_TRADE,
    STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT, MIN_POSITION_VALUE_USDT
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def example_trading_with_leverage():
    """
    Example: Trade BTC with 5x leverage on $3 starting capital
    Shows how leverage enables meeting Binance minimum position size
    """
    
    print("\n" + "="*80)
    print("EXAMPLE: TRADING WITH LEVERAGE")
    print("="*80)
    print(f"\nStarting Capital: ${STARTING_BALANCE}")
    print(f"Leverage: {LEVERAGE}x")
    print(f"Effective Buying Power: ${STARTING_BALANCE * LEVERAGE}")
    print(f"Risk per Trade: {RISK_PER_TRADE*100}%")
    print(f"Minimum Position Size: ${MIN_POSITION_VALUE_USDT}")
    
    # Initialize the sizer
    sizer = LeveragePositionSizer(
        account_balance=STARTING_BALANCE,
        leverage=LEVERAGE
    )
    
    print("\n" + "-"*80)
    print("SCENARIO 1: WITHOUT LEVERAGE")
    print("-"*80)
    
    # Without leverage
    sizer_no_leverage = LeveragePositionSizer(STARTING_BALANCE, leverage=1)
    
    entry_price_btc = 68000
    stop_loss_btc = 66640  # 2% below
    
    result_no_leverage = sizer_no_leverage.calculate_position_size(
        entry_price=entry_price_btc,
        stop_loss_price=stop_loss_btc,
        pair='BTC/USDT'
    )
    
    print(f"\nBTC Position (1x leverage):")
    print(f"  Entry Price: ${entry_price_btc:,.0f}")
    print(f"  Stop Loss: ${stop_loss_btc:,.0f}")
    print(f"  Position Size: {result_no_leverage['position_size']:.8f} BTC")
    print(f"  Position Value: ${result_no_leverage['position_value']:.2f}")
    print(f"  Risk Amount: ${result_no_leverage['risk_amount']:.2f}")
    print(f"  Meets Minimum ($5): {result_no_leverage['meets_minimum']}")
    print(f"  ❌ PROBLEM: Position too small! Below $5 minimum")
    
    print("\n" + "-"*80)
    print("SCENARIO 2: WITH 5x LEVERAGE")
    print("-"*80)
    
    result_with_leverage = sizer.calculate_position_size(
        entry_price=entry_price_btc,
        stop_loss_price=stop_loss_btc,
        pair='BTC/USDT'
    )
    
    print(f"\nBTC Position (5x leverage):")
    print(f"  Entry Price: ${entry_price_btc:,.0f}")
    print(f"  Stop Loss: ${stop_loss_btc:,.0f}")
    print(f"  Position Size: {result_with_leverage['position_size']:.8f} BTC")
    print(f"  Position Value (Notional): ${result_with_leverage['position_value']:.2f}")
    print(f"  Effective Exposure: ${result_with_leverage['leverage_effect']:.2f}")
    print(f"  Margin Required: ${result_with_leverage['margin_required']:.2f}")
    print(f"  Risk Amount: ${result_with_leverage['risk_amount']:.2f}")
    print(f"  Meets Minimum ($5): {result_with_leverage['meets_minimum']}")
    print(f"  ✓ SUCCESS: Can trade with leverage!")
    
    print("\n" + "-"*80)
    print("SCENARIO 3: LIVE TRADING SIMULATION")
    print("-"*80)
    
    # Initialize paper exchange
    exchange = EnhancedPaperExchange(
        initial_balance=STARTING_BALANCE,
        leverage=LEVERAGE
    )
    
    print(f"\nInitial Account:")
    summary = exchange.get_account_summary()
    print(f"  Balance: ${summary['balance']:.2f}")
    print(f"  Leverage: {summary['leverage']}x")
    print(f"  {summary['margin_warning']}")
    
    # Open a BTC position
    print(f"\n1️⃣  Opening BTC Position...")
    btc_position = exchange.open_position(
        symbol='BTC/USDT',
        side='buy',
        entry_price=68000,
        quantity=result_with_leverage['position_size']
    )
    
    # Simulate price movement
    current_prices = [68000, 68340, 68500, 68200, 67865, 67800]
    
    print(f"\n2️⃣  Monitoring Position...")
    for i, price in enumerate(current_prices):
        exchange.update_position_price(btc_position['id'], price)
        pos_summary = exchange.get_position_summary()
        
        if pos_summary['positions']:
            pos = pos_summary['positions'][0]
            print(f"  [{i+1}] Price: ${price:,.0f} | "
                  f"P&L: ${pos['unrealized_pnl']:+.2f} ({pos['unrealized_pnl_pct']:+.1f}%)")
        
        # Check for SL/TP
        result = exchange.check_tp_sl(btc_position['id'], price)
        if result:
            print(f"\n  >>> Position closed!")
            break
    
    # Final summary
    print(f"\n3️⃣  Final Account Status:")
    final_summary = exchange.get_account_summary()
    print(f"  Final Balance: ${final_summary['balance']:.2f}")
    print(f"  Total P&L: ${final_summary['profit_loss']:+.2f}")
    print(f"  ROI: {final_summary['roi_percent']:+.2f}%")
    print(f"  Total Trades: {final_summary['total_trades']}")
    print(f"  Win Rate: {final_summary['win_rate']:.1f}%")
    
    print("\n" + "="*80)
    print("LEVERAGE BENEFITS & RISKS")
    print("="*80)
    
    print("\n✓ BENEFITS:")
    print("  • Can open positions smaller than Binance minimum ($5)")
    print("  • Amplifies gains on trending markets")
    print("  • Better capital efficiency")
    print("  • More trade opportunities")
    
    print("\n✗ RISKS:")
    print("  • Also amplifies LOSSES (5x loss on 2% drop = 10% capital loss)")
    print("  • Liquidation risk if margin drops below threshold")
    print("  • Funding costs for borrowed capital")
    print("  • Requires strict stop losses!")
    
    print("\n📊 EXAMPLE RISK CALCULATION:")
    print(f"  With 5x leverage on $5 opening:")
    print(f"    • Actual position: $5 notional")
    print(f"    • Effective exposure: $25")
    print(f"    • 2% drop = $0.10 loss = 2% of $5")
    print(f"    • BUT on margin: 2% × 5 = 10% of capital")
    
    print("\n" + "="*80 + "\n")

if __name__ == '__main__':
    example_trading_with_leverage()
