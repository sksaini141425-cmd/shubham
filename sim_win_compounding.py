import json
from datetime import datetime

def run_win_compounding_simulation():
    try:
        with open('trade_log_local_test.json', 'r') as f:
            logs = json.load(f)
    except Exception as e:
        print(f"Error loading logs: {e}")
        return

    # Extract completed trades, filtering out the TONIXAI glitch
    trades = []
    active_trades = {}
    
    for entry in logs:
        symbol = entry['symbol']
        action = entry['action']
        if "TONIXAI" in symbol: continue

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

    # Simulation: Starting with $3.00
    balance = 3.0
    current_margin = 0.30 # Starting lot size
    leverage = 50
    fee_rate = 0.0005 

    history = []
    for ret in trades:
        # Check if we have enough balance to even place the trade
        if balance < current_margin:
            current_margin = balance * 0.5 # Safety reset if balance drops too low
            
        pnl = current_margin * leverage * ret
        fee = (current_margin * leverage * fee_rate) * 2
        balance += (pnl - fee)
        
        # LOGIC: Increase lot size by 10% after every profitable trade
        if pnl > 0:
            old_margin = current_margin
            current_margin = current_margin * 1.10
        else:
            # On a loss, most professional traders reset to base to protect capital
            # But for this simulation, we'll keep it at the current level to see the "Aggressive" result
            # or reset to 0.30? Let's do a 10% reduction or reset. 
            # I'll stick to the user's prompt: just increase on profit.
            pass

        history.append({
            'margin': current_margin,
            'balance': balance
        })

    print(f"--- Win-Streak Compounding Results ---")
    print(f"Initial Lot Size: $0.30")
    print(f"Final Lot Size:   ${current_margin:.2f}")
    print(f"Final Balance:    ${balance:.2f}")
    print(f"--------------------------------------")
    print(f"Summary: By increasing your 'bet' by 10% after every win,")
    print(f"your trade size grew from $0.30 to ${current_margin:.2f}.")
    print(f"This turned your $3.00 into ${balance:.2f} realistically.")

if __name__ == "__main__":
    run_win_compounding_simulation()
