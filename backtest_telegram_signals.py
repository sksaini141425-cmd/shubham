import argparse
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from bot.data_loader import DataLoader


@dataclass(frozen=True)
class ParsedSignal:
    ts: datetime
    provider: str
    group: str
    symbol: str
    side: str  # LONG/SHORT
    entry: float | None
    tp: float | None
    sl: float | None


def parse_dt(s: str) -> datetime:
    if not s:
        raise ValueError("missing datetime")
    s = s.replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_symbol(raw: str) -> str | None:
    if not raw:
        return None
    s = raw.upper().replace("/", "").replace(" ", "")
    if s.endswith("USDT"):
        return s
    if s.endswith("USD") and not s.endswith("USDT"):
        base = s[:-3]
        if not base:
            return None
        return base + "USDT"
    return None


def parse_signal(text: str, group: str, dt: datetime) -> ParsedSignal | None:
    if not text:
        return None
    clean = text.replace("**", "").replace("__", "").replace("*", "")
    clean = re.sub(r"[🔴📉💠✔🟣🔟⚡✅💠💠💠]", " ", clean)
    up = clean.upper()
    if not any(x in up for x in ["STOP", "LOSS", "PROFIT", "TARGET", "TAKE", "TP", "SL"]):
        return None

    provider = "Unknown"
    if group:
        if "O'BRIEN" in group.upper():
            provider = "O'Brien"
        elif "RSD" in group.upper() or "RJD" in group.upper():
            provider = "RSD"

    sym = None
    m = re.search(r"([A-Z0-9]{2,12})/?USDT", up)
    if m:
        sym = m.group(1) + "USDT"
    if not sym:
        m = re.search(r"\b([A-Z]{2,6}USD)\b", up)
        if m:
            sym = normalize_symbol(m.group(1))
    if not sym:
        m = re.search(r"#([A-Z0-9]{2,10})\b", up)
        if m:
            sym = m.group(1) + "USDT"
    if not sym:
        return None

    side = None
    if "LONG" in up or "BUY" in up:
        side = "LONG"
    if "SHORT" in up or "SELL" in up:
        side = "SHORT"
    if side is None:
        return None

    entry = None
    tp = None
    sl = None
    lines = [ln.strip().upper() for ln in clean.split("\n") if ln.strip()]
    for ln in lines:
        nums = re.findall(r"\d+(?:\.\d+)?", ln.replace("$", ""))
        if not nums:
            continue
        val = float(nums[0])
        if any(x in ln for x in ["BUY", "ENTRY", "NOW"]):
            if entry is None:
                entry = val
        elif any(x in ln for x in ["STOP", "SL"]):
            if sl is None:
                sl = val
        elif any(x in ln for x in ["PROFIT", "TARGET", "TP", "TAKE"]):
            if tp is None:
                tp = val

    return ParsedSignal(ts=dt, provider=provider, group=group or "", symbol=sym, side=side, entry=entry, tp=tp, sl=sl)


def candle_hits_entry(c, entry: float) -> bool:
    return c["low"] <= entry <= c["high"]


def resolve_exit_one_candle(side: str, c, tp: float, sl: float) -> float | None:
    if side == "LONG":
        tp_hit = c["high"] >= tp
        sl_hit = c["low"] <= sl
        if tp_hit and sl_hit:
            return sl
        if sl_hit:
            return sl
        if tp_hit:
            return tp
        return None
    if side == "SHORT":
        tp_hit = c["low"] <= tp
        sl_hit = c["high"] >= sl
        if tp_hit and sl_hit:
            return sl
        if sl_hit:
            return sl
        if tp_hit:
            return tp
        return None
    return None


def calculate_atr(candles: list[dict], period: int = 14) -> list[float | None]:
    if len(candles) < period + 1:
        return [None] * len(candles)
    true_ranges = [None]
    for i in range(1, len(candles)):
        h = candles[i]["high"]
        l = candles[i]["low"]
        pc = candles[i - 1]["close"]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        true_ranges.append(tr)
    atr = [None] * period
    first = sum(true_ranges[1 : period + 1]) / period
    atr.append(first)
    for i in range(period + 1, len(true_ranges)):
        atr.append((atr[-1] * (period - 1) + true_ranges[i]) / period)
    return atr


def compute_tp_sl_prices(symbol: str, direction: str, entry_price: float, atr_value: float | None) -> tuple[float, float]:
    if symbol == "BTCUSDT":
        tp_points = 20.0
        sl_points = 40.0
    elif symbol == "ETHUSDT":
        tp_points = 2.5
        sl_points = 5.0
    else:
        tp_atr_mult = 0.6
        sl_atr_mult = 1.1
        min_tp_pct = 0.0008
        min_sl_pct = 0.0014
        base_tp = entry_price * min_tp_pct
        base_sl = entry_price * min_sl_pct
        if atr_value:
            base_tp = max(base_tp, atr_value * tp_atr_mult)
            base_sl = max(base_sl, atr_value * sl_atr_mult)
        tp_points = base_tp
        sl_points = base_sl
    if direction == "LONG":
        return entry_price + tp_points, entry_price - sl_points
    return entry_price - tp_points, entry_price + sl_points


def simulate_signal(dl: DataLoader, sig: ParsedSignal, hold_minutes: int, timeframe: str, mode: str) -> dict:
    start = sig.ts - timedelta(minutes=120)
    end = sig.ts + timedelta(minutes=hold_minutes)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    candles = dl.fetch_ohlcv(sig.symbol, timeframe=timeframe, limit=1000, start_ms=start_ms, end_ms=end_ms)
    if not candles:
        return {"status": "no_data"}

    atrs = calculate_atr(candles, 14)
    for i, c in enumerate(candles):
        c["ATR"] = atrs[i]

    in_pos = False
    entry_px = None
    entry_time = None

    for c in candles:
        c_dt = datetime.fromtimestamp(c["timestamp"] / 1000, tz=timezone.utc)
        if c_dt < sig.ts:
            continue

        if not in_pos:
            if mode == "exact":
                if sig.entry is None or sig.tp is None or sig.sl is None:
                    return {"status": "not_a_full_signal"}
                if candle_hits_entry(c, sig.entry):
                    in_pos = True
                    entry_px = sig.entry
                    entry_time = c_dt
            else:
                in_pos = True
                entry_px = c["close"]
                entry_time = c_dt
                tp_price, sl_price = compute_tp_sl_prices(sig.symbol, sig.side, entry_px, c.get("ATR"))
                if sig.side == "LONG":
                    sig_tp, sig_sl = tp_price, sl_price
                else:
                    sig_tp, sig_sl = tp_price, sl_price
                current_tp = sig_tp
                current_sl = sig_sl
            continue

        if mode == "exact":
            tp = sig.tp
            sl = sig.sl
        else:
            tp = current_tp
            sl = current_sl

        exit_px = resolve_exit_one_candle(sig.side, c, tp=tp, sl=sl)
        if exit_px is not None:
            exit_time = c_dt
            ret = (exit_px - entry_px) / entry_px if sig.side == "LONG" else (entry_px - exit_px) / entry_px
            win = exit_px == tp
            return {
                "status": "closed",
                "win": bool(win),
                "entry_time": entry_time.isoformat(),
                "exit_time": exit_time.isoformat(),
                "entry": float(entry_px),
                "exit": float(exit_px),
                "ret": float(ret),
            }

    return {"status": "no_exit"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--signals", default=r"C:\Users\sksai\vip_signals.json")
    ap.add_argument("--hours", type=float, default=10.0, help="Backtest window ending at last signal timestamp.")
    ap.add_argument("--hold_minutes", type=int, default=180)
    ap.add_argument("--timeframe", default="1m")
    ap.add_argument("--mode", choices=["exact", "direction"], default="direction")
    ap.add_argument("--notional", type=float, default=5.5)
    ap.add_argument("--fee", type=float, default=0.0005, help="Taker fee per side (e.g., 0.0005 = 0.05%%).")
    ap.add_argument("--max_signals", type=int, default=300)
    args = ap.parse_args()

    if not os.path.exists(args.signals):
        raise SystemExit(f"Signals file not found: {args.signals}")

    raw = json.load(open(args.signals, "r", encoding="utf-8"))
    parsed: list[ParsedSignal] = []
    for item in raw:
        try:
            dt = parse_dt(item.get("date", ""))
            p = parse_signal(item.get("text", ""), item.get("group", ""), dt)
            if p:
                parsed.append(p)
        except Exception:
            continue

    if not parsed:
        print("No parseable signals found in file.")
        return

    parsed.sort(key=lambda s: s.ts)
    last_ts = parsed[-1].ts
    window_start = last_ts - timedelta(hours=args.hours)
    window = [s for s in parsed if s.ts >= window_start]
    window = window[-args.max_signals :]

    dl = DataLoader(exchange_id="bybit")

    executed = 0
    closed = 0
    wins = 0
    no_entry = 0
    no_exit = 0
    no_data = 0
    net_pnl = 0.0

    for sig in window:
        res = simulate_signal(dl, sig, hold_minutes=args.hold_minutes, timeframe=args.timeframe, mode=args.mode)
        if res["status"] == "not_a_full_signal":
            no_entry += 1
            continue
        if res["status"] == "no_data":
            no_data += 1
            continue
        if res["status"] == "no_exit":
            executed += 1
            no_exit += 1
            continue
        if res["status"] == "closed":
            executed += 1
            closed += 1
            if res["win"]:
                wins += 1
            gross = res["ret"]
            net = gross - (args.fee * 2.0)
            net_pnl += args.notional * net
            continue

    wr = (wins / closed * 100.0) if closed else 0.0
    print("WINDOW_END_UTC", last_ts.isoformat())
    print("WINDOW_START_UTC", window_start.isoformat())
    print("signals_in_window", len(window))
    print("executed_entries", executed)
    print("closed_trades", closed)
    print("win_rate_pct", round(wr, 2))
    print("no_data", no_data)
    print("no_exit_within_hold", no_exit)
    print("assumed_notional", args.notional)
    print("assumed_fee_per_side", args.fee)
    print("net_pnl_usdt", round(net_pnl, 4))


if __name__ == "__main__":
    main()
