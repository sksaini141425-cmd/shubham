import json
from datetime import datetime

def analyze_risk_metrics():
    try:
        with open('trade_log_local_test.json', 'r') as f:
            logs = json.load(f)
    except Exception as e:
        print(f"Error loading logs: {e}")
        return

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

    if not trades:
        print("No valid trades found for risk analysis.")
        return

    wins = [t for t in trades if t > 0]
    losses = [t for t in trades if t <= 0]
    
    win_rate = (len(wins) / len(trades)) * 100
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    
    # Calculate Max Drawdown (Consecutive losses)
    max_consecutive_losses = 0
    current_consecutive_losses = 0
    for t in trades:
        if t <= 0:
            current_consecutive_losses += 1
            max_consecutive_losses = max(max_consecutive_losses, current_consecutive_losses)
        else:
            current_consecutive_losses = 0

    # Risk of Ruin Calculation (Simplified)
    # Using 50x leverage, a 2% move against you is a 100% loss of margin.
    leverage = 50
    margin_per_trade_pct = 0.10 # 10% of balance
    
    print(f"--- Risk Analysis (Last Night's Performance) ---")
    print(f"Total Trades:      {len(trades)}")
    print(f"Win Rate:          {win_rate:.2f}%")
    print(f"Average Win:       {avg_win*100*leverage:.2f}% (with 50x leverage)")
    print(f"Average Loss:      {avg_loss*100*leverage:.2f}% (with 50x leverage)")
    print(f"Max Serial Losses: {max_consecutive_losses} trades in a row")
    print(f"-----------------------------------------------")
    
    # Probability of losing money in a session
    # We use the win/loss ratio and win rate
    if avg_loss != 0:
        profit_factor = abs((len(wins) * avg_win) / (len(losses) * avg_loss))
    else:
        profit_factor = float('inf')
        
    print(f"Profit Factor:     {profit_factor:.2f}")
    
    risk_level = "LOW"
    if win_rate < 50: risk_level = "HIGH"
    elif win_rate < 65: risk_level = "MEDIUM"
    
    print(f"Calculated Risk Level: {risk_level}")
    
    if max_consecutive_losses > 3:
        print("⚠️ WARNING: Your strategy had a streak of 4+ losses. With 50x leverage, this is where you could lose 50%+ of your balance.")

if __name__ == "__main__":
    analyze_risk_metrics()
