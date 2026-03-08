import json
import re

import sys
sys.stdout = open('output.txt', 'w', encoding='utf-8')
print("=========================================================")
print("🤖 VIP SIGNAL $3 ACCOUNT REALITY CHECK")
print("=========================================================\n")

try:
    with open(r'C:\Users\sksai\vip_signals.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
except Exception as e:
    print(f"Error loading JSON: {e}")
    exit()

ACCOUNT_BAL = 3.00
LEVERAGE = 45

parsed_signals = []

for item in data:
    text = item.get('text', '')
    if 'STOP LOSS' not in text.upper(): continue
    
    # Try to extract details
    # Example format:
    # XAUUSD buy NOW 5090.5087
    # STOP LOSS 5084
    # Target 5093
    
    # Clean text
    clean_text = text.replace('*', '').strip()
    
    # Direction
    direction = 'LONG' if 'buy' in clean_text.lower() else 'SHORT' if 'sell' in clean_text.lower() else None
    if not direction: continue
    
    # Regex find all numbers
    numbers = re.findall(r'\d+(?:\.\d+)?', clean_text)
    if len(numbers) < 3: continue
    
    # Usually first number is entry (maybe has two entries like 5090.5087 - take first)
    entry = None
    sl = None
    tp1 = None
    tp3 = None
    
    lines = clean_text.split('\n')
    for line in lines:
        line_num = re.findall(r'\d+(?:\.\d+)?', line)
        if not line_num: continue
        val = float(line_num[0])
        
        if 'NOW' in line.upper() or 'BUY' in line.upper() or 'SELL' in line.upper():
            if not entry: entry = val
        elif 'STOP LOSS' in line.upper() or 'SL' in line.upper():
            sl = val
        elif 'TARGET' in line.upper() or 'TP' in line.upper():
            if not tp1: tp1 = val
            tp3 = val # will end up being the last target
            
    if not entry or not sl or not tp1: continue
    
    # Risk/Reward Math
    risk_points = abs(entry - sl)
    reward_points = abs(tp3 - entry) if tp3 else abs(tp1 - entry)
    
    if entry == 0: continue
    
    # Leverage percentage
    risk_pct = (risk_points / entry) * LEVERAGE
    reward_pct = (reward_points / entry) * LEVERAGE
    
    risk_usd = ACCOUNT_BAL * risk_pct
    reward_usd = ACCOUNT_BAL * reward_pct
    
    parsed_signals.append({
        'date': item['date'],
        'entry': entry,
        'sl': sl,
        'tp1': tp1,
        'tp3': tp3,
        'risk_usd': risk_usd,
        'reward_usd': reward_usd,
        'rr': reward_usd / risk_usd if risk_usd > 0 else 0
    })

print(f"Total Messages Scraped: {len(data)}")
print(f"Total Valid Signals Found: {len(parsed_signals)}")
print("---------------------------------------------------------")

if not parsed_signals:
    print("Could not find any cleanly formatted signals to analyze.")
else:
    total_risk = sum(s['risk_usd'] for s in parsed_signals)
    total_reward = sum(s['reward_usd'] for s in parsed_signals)
    avg_risk = total_risk / len(parsed_signals)
    avg_reward = total_reward / len(parsed_signals)
    avg_rr = sum(s['rr'] for s in parsed_signals) / len(parsed_signals)
    
    print(f"Average Account Risk per Trade: ${avg_risk:.2f} ({(avg_risk/ACCOUNT_BAL)*100:.1f}%)")
    print(f"Average Potential Reward (Final TP): ${avg_reward:.2f} ({(avg_reward/ACCOUNT_BAL)*100:.1f}%)")
    print(f"Average Reward-to-Risk Ratio: {avg_rr:.2f}x")
    print("\n⚠️ WARNING ON $3 CAPITAL:")
    
    if avg_risk > 1.50:
        print(f"These signals have VERY wide Stop-Losses! You would lose ~${avg_risk:.2f} per single losing trade.")
        print("With a $3 account, 2 bad signals from this group will LIQUIDATE your entire account.")
        print("Conclusion: NOT SAFE for a $3 account. You would need to use 5x leverage instead of 45x to survive.")
    elif avg_rr < 1.0:
        print("These signals risk more than they make. Bad mathematical strategy.")
    else:
        print("The risk looks somewhat manageable, but always trade carefully.")
        
    print("---------------------------------------------------------")
    print("Top 3 Most Recent Signals & $3 Math:\n")
    for i, s in enumerate(parsed_signals[:3]):
        print(f"Signal {i+1}: Entry {s['entry']} | SL {s['sl']} | Final TP {s['tp3']}")
        print(f"   -> If it hits SL: You lose ${s['risk_usd']:.2f} ({(s['risk_usd']/ACCOUNT_BAL)*100:.1f}%)")
        print(f"   -> If it hits TP: You make ${s['reward_usd']:.2f} ({(s['reward_usd']/ACCOUNT_BAL)*100:.1f}%)\n")
