import json
from datetime import datetime

def run_realistic_simulation():
    try:
        with open('trade_log_local_test.json', 'r') as f:
            logs = json.load(f)
    except Exception as e:
        print(f"Error loading logs: {e}")
        return

    # Extract completed trades, filtering out the TONIXAI glitch
    trades = []
    active_trades = {}
    
    # We'll calculate the Average Profit % per winning trade
    total_win_pct = 0
    win_count = 0

    for entry in logs:
        symbol = entry['symbol']
        action = entry['action']
        
        # Skip the glitch coin for a realistic calculation
        if "TONIXAI" in symbol:
            continue

        if action in ['LONG', 'SHORT']:
            active_trades[symbol] = {
                'entry_price': entry['price'],
                'type': action
            }
        elif 'CLOSE' in action:
            if symbol in active_trades:
                trade_info = active_trades.pop(symbol)
                entry_p = trade_info['entry_price']
                exit_p = entry['price']
                
                if entry_p == 0: continue
                
                if trade_info['type'] == 'LONG':
                    ret = (exit_p - entry_p) / entry_p
                else:
                    ret = (entry_p - exit_p) / entry_p
                
                trades.append(ret)
                if ret > 0:
                    total_win_pct += ret
                    win_count += 1

    avg_win_pct = total_win_pct / win_count if win_count > 0 else 0
    
    # Simulation: Starting with $3.00
    balance_fixed = 3.0
    balance_comp = 3.0
    leverage = 50
    fee_rate = 0.0005 # 0.05%

    for ret in trades:
        # Fixed: Always use $0.30 margin
        margin_fixed = 0.30
        pnl_f = margin_fixed * leverage * ret
        fee_f = (margin_fixed * leverage * fee_rate) * 2
        balance_fixed += (pnl_f - fee_f)

        # Compounding: Use 10% of current balance
        margin_c = balance_comp / 10
        pnl_c = margin_c * leverage * ret
        fee_c = (margin_c * leverage * fee_rate) * 2
        balance_comp += (pnl_c - fee_c)

    # Average Profitable Dollar for NEXT trade
    # Based on current $7.50 balance
    current_balance = 7.50
    next_margin = current_balance / 10
    avg_dollar_profit = next_margin * leverage * avg_win_pct

    print(f"--- Realistic Results (Excluding Glitches) ---")
    print(f"Average Profit per Winning Trade: {avg_win_pct*100:.2f}%")
    print(f"Average Profit in Dollars for Next Trade: ${avg_dollar_profit:.2f}")
    print(f"----------------------------------------------")
    print(f"If we used Fixed Sizing ($0.30):  Final Balance = ${balance_fixed:.2f}")
    print(f"If we used Compounding (10%):     Final Balance = ${balance_comp:.2f}")
    print(f"----------------------------------------------")
    print(f"Compounding would have turned your $3 into ${balance_comp:.2f} instead of ${balance_fixed:.2f}.")

if __name__ == "__main__":
    run_realistic_simulation()
