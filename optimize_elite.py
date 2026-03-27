import itertools
import math
import sys

from bot.data_loader import DataLoader
from bot.strategy import calculate_ema, calculate_rsi, calculate_macd, calculate_sma


def calc_indicators(candles):
    closes = [c["close"] for c in candles]
    volumes = [c["volume"] for c in candles]
    ema50 = calculate_ema(closes, 50)
    ema200 = calculate_ema(closes, 200)
    rsi = calculate_rsi(candles, 14)
    _, _, hist = calculate_macd(candles)
    vol_sma = calculate_sma(volumes, 10)
    out = []
    for i, c in enumerate(candles):
        d = dict(c)
        d["EMA_50"] = ema50[i]
        d["EMA_200"] = ema200[i]
        d["RSI"] = rsi[i]
        d["MACD_Hist"] = hist[i]
        d["VOL_SMA"] = vol_sma[i]
        out.append(d)
    return out


def signal_elite(d, prev, rsi_long, rsi_short, require_ema200, vol_mult):
    price = d["close"]
    rsi = d.get("RSI")
    macd = d.get("MACD_Hist")
    prev_macd = prev.get("MACD_Hist")
    ema50 = d.get("EMA_50")
    ema200 = d.get("EMA_200")
    vol = d.get("volume")
    vol_sma = d.get("VOL_SMA")
    if None in (rsi, macd, prev_macd, ema50, ema200, vol_sma):
        return "NONE"
    if vol_mult and vol < (vol_sma * vol_mult):
        return "NONE"
    if price > ema50 and (not require_ema200 or price > ema200) and rsi < rsi_long and macd > prev_macd:
        return "LONG"
    if price < ema50 and (not require_ema200 or price < ema200) and rsi > rsi_short and macd < prev_macd:
        return "SHORT"
    return "NONE"


def backtest(candles, rsi_long, rsi_short, tp_pct, sl_pct, require_ema200, vol_mult, fee=0.0005):
    if len(candles) < 400:
        return 0, 0, 0.0
    in_pos = False
    side = None
    entry = 0.0
    wins = 0
    trades = 0
    net_ret = 0.0

    for i in range(201, len(candles) - 1):
        d = candles[i]
        prev = candles[i - 1]
        sig = signal_elite(d, prev, rsi_long, rsi_short, require_ema200, vol_mult)
        if not in_pos and sig in ("LONG", "SHORT"):
            in_pos = True
            side = sig
            entry = d["close"]
            trades += 1
            continue

        if in_pos:
            nxt = candles[i + 1]
            if side == "LONG":
                tp = entry * (1 + tp_pct)
                sl = entry * (1 - sl_pct)
                if nxt["low"] <= sl:
                    exit_px = sl
                elif nxt["high"] >= tp:
                    exit_px = tp
                else:
                    continue
                gross = (exit_px - entry) / entry
            else:
                tp = entry * (1 - tp_pct)
                sl = entry * (1 + sl_pct)
                if nxt["high"] >= sl:
                    exit_px = sl
                elif nxt["low"] <= tp:
                    exit_px = tp
                else:
                    continue
                gross = (entry - exit_px) / entry

            net = gross - fee - fee
            net_ret += net
            if net > 0:
                wins += 1
            in_pos = False
            side = None
            entry = 0.0

    return trades, wins, net_ret


def main():
    dl = DataLoader(exchange_id="bybit")
    symbols = dl.get_top_futures_symbols(top_n=20, min_volume_usd=20000000, offset=0)
    if not symbols:
        print("No symbols fetched")
        sys.exit(1)

    candles_by_symbol = {}
    for s in symbols:
        c = dl.fetch_ohlcv(s, timeframe="1m", limit=2000)
        if not c:
            continue
        candles_by_symbol[s] = calc_indicators(c)

    grid = list(
        itertools.product(
            [45, 47, 49],
            [51, 53, 55],
            [0.0006, 0.0009, 0.0012],
            [0.0012, 0.0018, 0.0024],
            [True, False],
            [0.0, 1.0, 1.05],
        )
    )

    best = None
    best_score = -math.inf
    for rsi_long, rsi_short, tp, sl, req200, vol_mult in grid:
        total_trades = 0
        total_wins = 0
        total_ret = 0.0
        for sym, candles in candles_by_symbol.items():
            t, w, r = backtest(candles, rsi_long, rsi_short, tp, sl, req200, vol_mult)
            total_trades += t
            total_wins += w
            total_ret += r

        wr = (total_wins / total_trades * 100.0) if total_trades else 0.0
        if total_trades < 40:
            continue
        score = wr * 1000.0 + total_ret * 10000.0 + total_trades
        if score > best_score:
            best_score = score
            best = (wr, total_trades, total_ret, rsi_long, rsi_short, tp, sl, req200, vol_mult)

    if not best:
        print("No candidate met minimum trades")
        return

    wr, total_trades, total_ret, rsi_long, rsi_short, tp, sl, req200, vol_mult = best
    print("BEST")
    print("win_rate", round(wr, 2))
    print("trades", total_trades)
    print("net_ret_pct", round(total_ret * 100.0, 2))
    print("ELITE_RSI_LONG", rsi_long)
    print("ELITE_RSI_SHORT", rsi_short)
    print("TP_PCT", tp)
    print("SL_PCT", sl)
    print("ELITE_REQUIRE_EMA200", req200)
    print("ELITE_VOL_MULT", vol_mult)


if __name__ == "__main__":
    main()

