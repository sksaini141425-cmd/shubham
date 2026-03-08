import json

with open('trade_log.json') as f:
    trades = json.load(f)

print(f'Total trade entries: {len(trades)}')
closes = [t for t in trades if t.get('action','').startswith('CLOSE')]
opens = [t for t in trades if not t.get('action','').startswith('CLOSE')]
wins = [t for t in closes if (t.get('pnl') or 0) > 0]
losses = [t for t in closes if (t.get('pnl') or 0) <= 0]
print(f'Opened: {len(opens)}, Closed: {len(closes)}')
print(f'Wins: {len(wins)}, Losses: {len(losses)}')
if closes:
    print(f'Win Rate: {len(wins)/len(closes)*100:.1f}%')
    total_pnl = sum(t.get('pnl',0) or 0 for t in closes)
    print(f'Total Net PnL: ${total_pnl:.4f}')
    avg_win = sum(t.get('pnl',0) or 0 for t in wins)/len(wins) if wins else 0
    avg_loss = sum(t.get('pnl',0) or 0 for t in losses)/len(losses) if losses else 0
    print(f'Avg Win: ${avg_win:.4f}  |  Avg Loss: ${avg_loss:.4f}')
    if avg_loss != 0:
        print(f'Win/Loss Ratio: {abs(avg_win/avg_loss):.2f}x')
        
    # Close reasons by type
    print()
    print('--- Breakdown by close action ---')
    action_types = {}
    for t in closes:
        a = t.get('action','')
        action_types[a] = action_types.get(a, {'count':0,'pnl':0})
        action_types[a]['count'] += 1
        action_types[a]['pnl'] += (t.get('pnl') or 0)
    for a, s in action_types.items():
        print(f'  {a}: {s["count"]} trades | Total PnL: ${s["pnl"]:.4f}')
    
    print()
    print('--- Loss breakdown by symbol ---')
    sym_stats = {}
    for t in closes:
        sym = t.get('symbol','?')
        if sym not in sym_stats:
            sym_stats[sym] = {'wins':0,'losses':0,'pnl':0.0}
        pnl = t.get('pnl') or 0
        sym_stats[sym]['pnl'] += pnl
        if pnl > 0:
            sym_stats[sym]['wins'] += 1
        else:
            sym_stats[sym]['losses'] += 1
    # Sort by total pnl (worst first)
    for sym, s in sorted(sym_stats.items(), key=lambda x: x[1]['pnl']):
        total = s['wins'] + s['losses']
        print(f'  {sym}: {s["wins"]}W/{s["losses"]}L | PnL: ${s["pnl"]:.4f}')

print()
print('--- Last 20 closed trades ---')
for t in closes[-20:]:
    pnl = t.get('pnl', 0) or 0
    entry = t.get('entry_price', t.get('price', 0))
    exit_p = t.get('price', 0)
    print(f'{t.get("action","?")} | {t.get("symbol","?")} | {t.get("timestamp","")[:19]} | Entry: ${entry:.4f} -> Exit: ${exit_p:.4f} | PnL: ${pnl:.4f} | Bal: ${t.get("balance",0):.4f}')
