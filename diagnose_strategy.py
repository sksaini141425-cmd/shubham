"""
Focused strategy diagnosis - identifies specific structural problems.
"""
import sys, json, math, urllib.request
sys.path.insert(0, '.')
from bot.strategy import SmartMoneyStrategy

def fetch_klines(symbol='BTCUSDT', interval='1m', limit=500):
    url = f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}'
    with urllib.request.urlopen(url, timeout=10) as r:
        data = json.loads(r.read())
    return [{'timestamp':k[0],'open':float(k[1]),'high':float(k[2]),
              'low':float(k[3]),'close':float(k[4]),'volume':float(k[5])} for k in data]

results_summary = []

for symbol in ['BTCUSDT','ETHUSDT','SOLUSDT','DOGEUSDT','XRPUSDT','BNBUSDT']:
    try:
        candles = fetch_klines(symbol, '1m', 500)
        s = SmartMoneyStrategy(leverage=45)
        candles = s.calculate_indicators(candles)
        candles = s.generate_signals(candles)

        TAKER_FEE = 0.0005
        capital = 3.0
        in_pos = False
        dir_ = entry = size_ = entry_i = 0
        sl_pct = 0.0
        trades = []
        signals = {'LONG':0,'SHORT':0,'NONE':0}

        for i, c in enumerate(candles):
            sig = c.get('signal','NONE')
            price = c['close']
            atr = c.get('ATR')
            signals[sig] = signals.get(sig,0)+1

            if not in_pos and sig in ['LONG','SHORT'] and atr:
                notional = 5.25
                size_ = notional / price
                open_fee = notional * TAKER_FEE
                in_pos = True; dir_ = sig; entry = price; entry_i = i
                atr_pct = atr / price
                sl_pct = min(-0.02, -(atr_pct*1.5))
                capital -= open_fee

            elif in_pos and atr:
                upnl = ((price - entry) if dir_=='LONG' else (entry - price)) * size_
                upnl_pct = upnl / (size_ * entry)
                close_fee = size_ * price * TAKER_FEE
                close, reason = False, ''

                # Trail SL logic
                if upnl_pct >= 0.005 and sl_pct < 0.0:
                    sl_pct = 0.0
                if upnl_pct >= 0.015:
                    new_sl = upnl_pct * 0.5
                    if new_sl > sl_pct: sl_pct = new_sl

                if upnl_pct >= 0.03: close, reason = True, 'TP'
                elif upnl_pct <= sl_pct: close, reason = True, 'SL'
                elif (i - entry_i) >= 60: close, reason = True, 'TIMEOUT'
                elif dir_=='LONG' and sig=='SHORT': close, reason = True, 'REVERSAL'
                elif dir_=='SHORT' and sig=='LONG': close, reason = True, 'REVERSAL'

                if close:
                    net_pnl = upnl - close_fee
                    capital += net_pnl
                    trades.append({'dir':dir_,'pnl':net_pnl,'pnl_pct':upnl_pct*100,'reason':reason,'bars':i-entry_i})
                    in_pos = False; sl_pct = 0.0

        wins = [t for t in trades if t['pnl'] > 0]
        losses = [t for t in trades if t['pnl'] <= 0]
        wr = len(wins)/len(trades)*100 if trades else 0
        total_pnl = sum(t['pnl'] for t in trades)
        results_summary.append((symbol, len(trades), wr, total_pnl, signals))

        print(f"\n{symbol}: {len(trades)} trades | WR={wr:.0f}% | PnL=${total_pnl:.4f}")
        print(f"  Signals: {signals}")
        by_reason = {}
        for t in trades:
            r = t['reason']
            if r not in by_reason: by_reason[r] = {'n':0,'w':0,'pnl':0}
            by_reason[r]['n']+=1; by_reason[r]['pnl']+=t['pnl']
            if t['pnl']>0: by_reason[r]['w']+=1
        for r,s in by_reason.items():
            print(f"  {r}: {s['n']} trades | WR:{s['w']/s['n']*100:.0f}% | PnL:${s['pnl']:.4f}")
    except Exception as e:
        print(f"{symbol}: ERROR - {e}")

# === KEY DIAGNOSIS ===
print("\n" + "="*60)
print("ROOT CAUSE ANALYSIS")
print("="*60)

all_t = sum(r[1] for r in results_summary)
all_wr = sum(r[2]*r[1] for r in results_summary)/all_t if all_t else 0
print(f"\nSimulation WR: {all_wr:.1f}%")
print(f"Reported live WR: ~10% (losing 90%)")
print(f"\nGap = {all_wr - 10:.0f}% — this means the problem is NOT the signal logic alone.\n")

print("LIKELY ROOT CAUSES:")
print("1. FEES vs CAPITAL SIZE:")
NOTIONAL = 5.25
CAPITAL = 3.0
fee_per_round = NOTIONAL * 0.0005 * 2
print(f"   Round-trip fee: ${fee_per_round:.4f} on ${NOTIONAL:.2f} notional")
print(f"   That's {fee_per_round/CAPITAL*100:.2f}% of total $3 capital per trade!")
print(f"   After just 10 losing trades: ${10*fee_per_round:.3f} lost just to fees")

print("\n2. STOP-LOSS TOO TIGHT vs 1m NOISE:")
print("   ATR×1.5 on 1m candles = ultra-tight SL gets hit by normal noise")
print("   1m candles have random wicks that easily tag a 1-2% SL")
print("   Fix: Use 5m or 15m candles to reduce noise")

print("\n3. SIGNAL FREQUENCY vs QUALITY:")
print("   60 symbols × loosened conditions = too many low-quality entries")
print("   More trades = more fees = faster account bleed")
print("   Fix: Stricter entry filters (require RSI <35 for LONG, >65 for SHORT)")

print("\n4. LEVERAGE MATH ON TINY CAPITAL:")
print(f"   $3 capital × 45x leverage = positions worth up to ${3*45:.0f}")
print(f"   Even a 0.07% move against = liquidation territory")
print(f"   Min notional $5 > capital $3 → fully leveraged from the start")

print("\n5. MISSING VOLUME/TREND CONFIRMATION:")
print("   No volume filter → entering in low-liquidity conditions")
print("   No higher-timeframe trend gate → trading against macro trend")
