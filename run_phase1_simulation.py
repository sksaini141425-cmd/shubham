#!/usr/bin/env python3
"""
Phase 1 Simulation: $3 → $4 Conservative Growth Strategy
Test the conservative approach before risking real money
"""

import sys
import logging
from datetime import datetime, timedelta
import random

# Import the phase 1 configuration
from config_phase1 import (
    STARTING_BALANCE, LEVERAGE, RISK_PER_TRADE,
    STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT, MIN_POSITION_VALUE_USDT,
    TRADING_PAIRS, MAX_CONCURRENT_POSITIONS, MAX_DAILY_TRADES,
    PHASE1_TARGETS, RECOMMENDED_STRATEGIES
)

# Import leverage modules
from leverage_position_sizer import LeveragePositionSizer
from enhanced_paper_exchange import EnhancedPaperExchange

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Phase1Simulator:
    def __init__(self):
        self.exchange = EnhancedPaperExchange(
            initial_balance=STARTING_BALANCE,
            leverage=LEVERAGE
        )
        self.position_sizer = LeveragePositionSizer(
            account_balance=STARTING_BALANCE,
            leverage=LEVERAGE
        )
        self.daily_trades = 0
        self.daily_pnl = 0
        self.total_trades = 0
        self.winning_trades = 0
        
    def simulate_trade(self, pair='BTC/USDT'):
        """Simulate a single trade with realistic outcomes"""
        
        # Get current account state
        summary = self.exchange.get_account_summary()
        current_balance = summary['balance']
        
        # Skip if not enough capital or too many trades
        if self.daily_trades >= MAX_DAILY_TRADES:
            return False, "Max daily trades reached"
        
        # With leverage, we need less capital to open positions
        # Check if we have enough margin for the minimum position
        required_margin = MIN_POSITION_VALUE_USDT / LEVERAGE
        if current_balance < required_margin:
            return False, f"Insufficient capital: need ${required_margin:.2f}, have ${current_balance:.2f}"
        
        # Calculate position size
        entry_price = self._get_realistic_price(pair)
        stop_loss_price = entry_price * (1 - STOP_LOSS_PERCENT / 100)
        
        position = self.position_sizer.calculate_position_size(
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            pair=pair
        )
        
        if not position['meets_minimum']:
            return False, "Position too small"
        
        # Open position
        trade = self.exchange.open_position(
            symbol=pair,
            side='buy',
            entry_price=entry_price,
            quantity=position['position_size']
        )
        
        # Simulate price movement with 60% win rate
        win_probability = 0.60  # Phase 1 target
        
        if random.random() < win_probability:
            # Winning trade - hit take profit
            exit_price = entry_price * (1 + TAKE_PROFIT_PERCENT / 100)
            result = "WIN"
        else:
            # Losing trade - hit stop loss
            exit_price = entry_price * (1 - STOP_LOSS_PERCENT / 100)
            result = "LOSS"
        
        # Close position
        self.exchange.update_position_price(trade['id'], exit_price)
        close_result = self.exchange.check_tp_sl(trade['id'], exit_price)
        
        # Update statistics
        self.daily_trades += 1
        self.total_trades += 1
        
        if result == "WIN":
            self.winning_trades += 1
        
        # Calculate P&L for this trade
        trade_pnl = (exit_price - entry_price) * position['position_size']
        self.daily_pnl += trade_pnl
        
        return True, f"{result}: P&L ${trade_pnl:+.4f}"
    
    def _get_realistic_price(self, pair):
        """Get realistic price for simulation"""
        prices = {
            'BTC/USDT': random.uniform(65000, 70000),
            'ETH/USDT': random.uniform(3000, 3500),
        }
        return prices.get(pair, 50000)
    
    def run_daily_simulation(self):
        """Run one day of trading simulation"""
        print(f"\n{'='*60}")
        print(f"PHASE 1 DAILY SIMULATION - {datetime.now().strftime('%Y-%m-%d')}")
        print(f"{'='*60}")
        
        # Reset daily counters
        self.daily_trades = 0
        self.daily_pnl = 0
        
        # Starting account
        start_summary = self.exchange.get_account_summary()
        print(f"\n📊 Starting Balance: ${start_summary['balance']:.2f}")
        print(f"🎯 Target: ${PHASE1_TARGETS['phase_complete_balance']:.2f}")
        print(f"📈 Daily Target: ${PHASE1_TARGETS['daily_profit_target']:.2f}")
        
        # Simulate trading day
        trades_made = 0
        while trades_made < MAX_DAILY_TRADES:
            # Randomly choose pair
            pair = random.choice(TRADING_PAIRS)
            
            success, message = self.simulate_trade(pair)
            
            if success:
                trades_made += 1
                current_summary = self.exchange.get_account_summary()
                win_rate = (self.winning_trades / self.total_trades) * 100 if self.total_trades > 0 else 0
                
                print(f"  Trade {trades_made}: {pair} | {message} | "
                      f"Balance: ${current_summary['balance']:.2f} | "
                      f"Win Rate: {win_rate:.1f}%")
                
                # Stop if daily loss limit hit
                if self.daily_pnl < -PHASE1_TARGETS['max_daily_loss']:
                    print(f"\n⚠️  Daily loss limit reached! Stopping trading.")
                    break
                
                # Stop if target reached
                if current_summary['balance'] >= PHASE1_TARGETS['phase_complete_balance']:
                    print(f"\n🎉 Phase 1 Target Reached!")
                    break
            else:
                print(f"  Skipped: {message}")
                break
        
        # Daily summary
        end_summary = self.exchange.get_account_summary()
        daily_roi = (self.daily_pnl / start_summary['balance']) * 100
        total_roi = ((end_summary['balance'] - STARTING_BALANCE) / STARTING_BALANCE) * 100
        
        print(f"\n📊 DAILY SUMMARY:")
        print(f"  Starting Balance: ${start_summary['balance']:.2f}")
        print(f"  Ending Balance: ${end_summary['balance']:.2f}")
        print(f"  Daily P&L: ${self.daily_pnl:+.2f} ({daily_roi:+.1f}%)")
        print(f"  Total P&L: ${end_summary['balance'] - STARTING_BALANCE:+.2f} ({total_roi:+.1f}%)")
        print(f"  Trades Today: {trades_made}")
        win_rate = (self.winning_trades/self.total_trades)*100 if self.total_trades > 0 else 0
        print(f"  Win Rate: {win_rate:.1f}%")
        
        # Check phase completion
        if end_summary['balance'] >= PHASE1_TARGETS['phase_complete_balance']:
            print(f"\n🎉 PHASE 1 COMPLETE! Ready for Phase 2 ($4 → $7)")
            return True
        else:
            remaining = PHASE1_TARGETS['phase_complete_balance'] - end_summary['balance']
            print(f"\n📌 Continue Phase 1: ${remaining:.2f} to target")
            return False
    
    def run_week_simulation(self):
        """Run one week of trading to see progression"""
        print(f"\n{'='*80}")
        print(f"PHASE 1 WEEK SIMULATION: $3 → $4 CONSERVATIVE GROWTH")
        print(f"{'='*80}")
        print(f"\nStrategy Parameters:")
        print(f"  • Leverage: {LEVERAGE}x")
        print(f"  • Risk per trade: {RISK_PER_TRADE*100}%")
        print(f"  • Max daily trades: {MAX_DAILY_TRADES}")
        print(f"  • Target win rate: {PHASE1_TARGETS['win_rate_target']*100}%")
        print(f"  • Stop Loss: {STOP_LOSS_PERCENT}% | Take Profit: {TAKE_PROFIT_PERCENT}%")
        
        days_completed = 0
        phase_complete = False
        
        for day in range(7):  # 7-day week
            print(f"\n{'─'*60}")
            print(f"DAY {day + 1}")
            print(f"{'─'*60}")
            
            phase_complete = self.run_daily_simulation()
            days_completed += 1
            
            if phase_complete:
                break
            
            # Ask to continue
            if day < 6:  # Not the last day
                print(f"\nPress Enter to continue to next day...")
                input()
        
        # Final summary
        final_summary = self.exchange.get_account_summary()
        total_profit = final_summary['balance'] - STARTING_BALANCE
        total_roi = (total_profit / STARTING_BALANCE) * 100
        
        print(f"\n{'='*80}")
        print(f"WEEK SUMMARY - {days_completed} DAYS")
        print(f"{'='*80}")
        print(f"  Starting Capital: ${STARTING_BALANCE:.2f}")
        print(f"  Final Balance: ${final_summary['balance']:.2f}")
        print(f"  Total Profit: ${total_profit:+.2f}")
        print(f"  Total ROI: {total_roi:+.1f}%")
        print(f"  Total Trades: {self.total_trades}")
        final_win_rate = (self.winning_trades/self.total_trades)*100 if self.total_trades > 0 else 0
        print(f"  Win Rate: {final_win_rate:.1f}%")
        
        if phase_complete:
            print(f"\n🎉 SUCCESS! Phase 1 completed in {days_completed} days!")
            print(f"🚀 Ready to upgrade to Phase 2: $4 → $7")
        else:
            remaining = PHASE1_TARGETS['phase_complete_balance'] - final_summary['balance']
            print(f"\n📌 Phase 1 in progress: ${remaining:.2f} remaining")
            print(f"💡 Continue with conservative approach")

def main():
    """Run Phase 1 simulation"""
    print("🎯 PHASE 1: $3 → $4 CONSERVATIVE GROWTH STRATEGY")
    print("=" * 80)
    print("\nThis simulation tests the conservative approach before real trading.")
    print("Expected timeline: 3-7 days to reach $4 target")
    print("\nKey Principles:")
    print("  • Capital preservation first")
    print("  • 2x leverage (safe)")
    print("  • 3% risk per trade")
    print("  • 60% win rate target")
    print("  • Quick trades (2 hours max)")
    
    print(f"\nPress Enter to start simulation...")
    input()
    
    simulator = Phase1Simulator()
    simulator.run_week_simulation()

if __name__ == '__main__':
    main()
