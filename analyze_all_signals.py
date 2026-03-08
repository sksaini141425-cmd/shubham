import json
import re
from collections import defaultdict
import sys

sys.stdout = open('leaderboard.txt', 'w', encoding='utf-8')

print("🏆 ULTIMATE VIP GROUP LEADERBOARD ($3 A/C) 🏆")
print("=========================================================\n")

try:
    with open(r'C:\Users\sksai\vip_signals.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
except Exception as e:
    print(f"Error loading JSON: {e}")
    exit()

ACCOUNT_BAL = 3.00
LEVERAGE = 45

# group_name -> list of parsed signals
group_stats = defaultdict(list)
raw_messages_count = defaultdict(int)

for item in data:
    group_name = item.get('group', 'Unknown')
    text = item.get('text', '')
    if not text: continue
    
    raw_messages_count[group_name] += 1
    
    clean_text = text.replace('*', '').replace('-', ' ').strip()
    up_text = clean_text.upper()
    
    # Catch combinations of stop loss and take profit
    has_sl = any(k in up_text for k in ['STOP LOSS', 'SL'])
    has_tp = any(k in up_text for k in ['TARGET', 'TP', 'TAKE PROFIT'])
    if not has_sl or not has_tp: continue

    direction = 'LONG' if 'buy' in clean_text.lower() or 'long' in clean_text.lower() else 'SHORT' if 'sell' in clean_text.lower() or 'short' in clean_text.lower() else None
    if not direction: continue
    
    entry, sl, tp1, tp_last = None, None, None, None
    lines = clean_text.split('\n')
    for line in lines:
        nums = re.findall(r'\d+(?:\.\d+)?', line)
        if not nums: continue
        val = float(nums[0])
        
        up = line.upper()
        if 'NOW' in up or 'BUY' in up or 'SELL' in up or 'ENTRY' in up:
            if not entry: entry = val
        elif 'STOP LOSS' in up or 'SL' in up:
            if not sl: sl = val
        elif 'TARGET' in up or 'TP' in up:
            if not tp1: tp1 = val
            tp_last = val
            
    if entry and sl and tp1:
        if entry == 0: continue
        
        # Determine strict R:R
        risk_points = abs(entry - sl)
        reward_points = abs(tp_last - entry) if tp_last else abs(tp1 - entry)
        if risk_points == 0: continue
        
        risk_pct = (risk_points / entry) * LEVERAGE
        reward_pct = (reward_points / entry) * LEVERAGE
        
        risk_usd = ACCOUNT_BAL * risk_pct
        reward_usd = ACCOUNT_BAL * reward_pct
        rr = reward_usd / risk_usd if risk_usd > 0 else 0
        
        group_stats[group_name].append({
            'risk_usd': risk_usd,
            'reward_usd': reward_usd,
            'rr': rr
        })

print(f"Total RAW Messages Scraped: {len(data)}")
print(f"Total Valid Trades Mined: {sum(len(v) for v in group_stats.values())}\n")

results = []
for group, signals in group_stats.items():
    if not signals: continue
    
    total_risk = sum(s['risk_usd'] for s in signals)
    total_reward = sum(s['reward_usd'] for s in signals)
    avg_risk = total_risk / len(signals)
    avg_reward = total_reward / len(signals)
    avg_rr = sum(s['rr'] for s in signals) / len(signals)
    
    results.append({
        'group': group,
        'signals_count': len(signals),
        'raw_count': raw_messages_count[group],
        'avg_risk': avg_risk,
        'avg_reward': avg_reward,
        'avg_rr': avg_rr
    })

# Ranked by RR ratio, then minimum risk
results.sort(key=lambda x: (x['avg_rr'], -x['avg_risk']), reverse=True)

if not results:
    print("No valid signals found in any group! Ensure they actually post Entry/SL/TP numbers.")
else:
    for i, r in enumerate(results):
        print(f"#{i+1} {r['group'].upper()}")
        print(f"  -> Total Signals (7 Days): {r['signals_count']} (out of {r['raw_count']} chat msgs)")
        print(f"  -> Average Risk: -${r['avg_risk']:.2f} per trade")
        print(f"  -> Average Reward: +${r['avg_reward']:.2f} per trade")
        print(f"  -> Reward/Risk Ratio: {r['avg_rr']:.2f}x")
        
        if r['avg_risk'] > 1.50:
            print("  -> ⚠️ VERDICT: DANGEROUS for $3 account (Stop losses are way too huge)")
        elif r['avg_rr'] < 1.0:
            print("  -> ⚠️ VERDICT: POOR STRATEGY (They risk more than they make)")
        else:
            print("  -> ✅ VERDICT: Safe & mathematically viable for $3 account")
        print("-" * 50)
