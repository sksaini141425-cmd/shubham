#!/usr/bin/env python3
"""
Backtest harness for the Market Confluence strategy.

Because the live strategy depends on external crowding/funding/news context,
this script supports two modes:

1. static: reuse the current market_context.json snapshot across the whole test.
2. proxy: derive approximate funding/crowding/fear context from price/volume.

`proxy` is not a true historical replication of the live discretionary inputs.
It is a structured approximation to measure whether the ruleset can produce and
manage trades over historical candles.
"""
import argparse
import json
import math
from collections import Counter
from datetime import datetime, timedelta, timezone

import requests
import urllib3

from bot.data_loader import DataLoader
from bot.strategy import calculate_ema, calculate_rsi
from bot.strategy_confluence import MarketConfluenceStrategy

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BINANCE_FUTURES_BASE = "https://fapi.binance.com/fapi/v1"
TAKER_FEE = 0.0005


def parse_args():
    parser = argparse.ArgumentParser(description="Backtest Market Confluence strategy")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--days", type=int, default=20)
    parser.add_argument("--mode", choices=["static", "proxy"], default="proxy")
    parser.add_argument("--capital", type=float, default=5.0)
    parser.add_argument("--leverage", type=int, default=5)
    parser.add_argument("--risk_per_trade", type=float, default=None, help="Override strategy risk, e.g. 0.02")
    parser.add_argument("--output", default="confluence_backtest_results.json")
    return parser.parse_args()


def fetch_binance_klines(symbol, interval, days, limit=1500):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    all_rows = []
    current = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    step_ms = interval_to_ms(interval)

    while current < end_ms:
        response = requests.get(
            f"{BINANCE_FUTURES_BASE}/klines",
            params={
                "symbol": symbol,
                "interval": interval,
                "limit": limit,
                "startTime": current,
                "endTime": end_ms,
            },
            timeout=20,
            verify=False,
        )
        response.raise_for_status()
        rows = response.json()
        if not rows:
            break

        for row in rows:
            all_rows.append(
                {
                    "timestamp": int(row[0]),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                }
            )

        next_start = int(rows[-1][0]) + step_ms
        if next_start <= current:
            break
        current = next_start

    return all_rows


def interval_to_ms(interval):
    mapping = {
        "5m": 5 * 60 * 1000,
        "1h": 60 * 60 * 1000,
    }
    return mapping[interval]


def build_static_context(strategy, symbol):
    context = strategy._load_market_context(symbol)
    context["available"] = bool(context)
    return context


def build_proxy_context(symbol, structure_slice):
    closes_1h = [candle["close"] for candle in structure_slice]
    rsi_1h = calculate_rsi(structure_slice, 14)[-1]

    ret_8h = 0.0
    if len(structure_slice) >= 8 and structure_slice[-8]["close"]:
        ret_8h = (
            (structure_slice[-1]["close"] - structure_slice[-8]["close"])
            / structure_slice[-8]["close"]
            * 100.0
        )

    volume_window = structure_slice[-8:]
    avg_volume = (
        sum(candle["volume"] for candle in volume_window) / len(volume_window)
        if volume_window
        else 0.0
    )
    latest_volume = structure_slice[-1]["volume"]
    oi_change_proxy = (
        ((latest_volume - avg_volume) / avg_volume) * 100.0 if avg_volume else None
    )

    # Proxy heuristics:
    # - funding follows recent directional stretch
    # - retail long ratio follows 1h RSI crowding
    # - fear/greed follows recent directional pressure
    funding_rate = max(-0.0006, min(0.0006, ret_8h * 0.00015))
    retail_long_ratio_pct = max(
        20.0,
        min(80.0, 50.0 + ((rsi_1h - 50.0) * 1.3 if rsi_1h is not None else 0.0)),
    )
    fear_greed_index = max(5.0, min(95.0, 50.0 + (ret_8h * 4.0)))
    fear_greed_previous = max(5.0, min(95.0, 50.0 + ((ret_8h - 0.4) * 4.0)))

    return {
        "available": True,
        "symbol": symbol,
        "symbol_matches": True,
        "support_level": None,
        "resistance_level": None,
        "fear_greed_index": fear_greed_index,
        "fear_greed_previous": fear_greed_previous,
        "retail_long_ratio_pct": retail_long_ratio_pct,
        "funding_rate": funding_rate,
        "open_interest_change_pct_1h": oi_change_proxy,
        "news_bias": "neutral",
        "notes": "price-derived proxy context",
    }


def to_datetime(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def simulate_backtest(args):
    symbol = args.symbol.upper()
    print(f"Fetching {args.days} days of {symbol} candles from Binance Futures...")
    candles_5m = fetch_binance_klines(symbol, "5m", args.days)
    candles_1h = fetch_binance_klines(symbol, "1h", args.days)
    print(f"Fetched {len(candles_5m)} x 5m candles and {len(candles_1h)} x 1h candles.")

    loader = DataLoader(exchange_id="binance")
    strategy = MarketConfluenceStrategy(leverage=args.leverage)
    if args.risk_per_trade is not None:
        strategy.risk_per_trade = float(args.risk_per_trade)

    symbol_info = loader.get_symbol_info(symbol)
    min_notional = symbol_info["min_notional"]
    step_size = symbol_info["step_size"]

    equity = args.capital
    peak_equity = equity
    equity_curve = []
    trades = []
    block_reasons = Counter()
    signal_reasons = Counter()
    signal_count = Counter()
    position = None

    h1_index = 0
    static_context = build_static_context(strategy, symbol) if args.mode == "static" else None

    for i in range(300, len(candles_5m)):
        candle = candles_5m[i]
        current_time = to_datetime(candle["timestamp"])

        while h1_index + 1 < len(candles_1h) and candles_1h[h1_index + 1]["timestamp"] <= candle["timestamp"]:
            h1_index += 1

        structure_slice = candles_1h[max(0, h1_index - 47):h1_index + 1]
        if len(structure_slice) < 24:
            continue

        entry_slice = candles_5m[max(0, i - 299):i + 1]
        context = static_context or build_proxy_context(symbol, structure_slice)
        market_data = {
            "symbol": symbol,
            "timeframes": {
                "5m": [dict(row) for row in entry_slice],
                "1h": [dict(row) for row in structure_slice],
            },
            "context": context,
        }

        processed = strategy.calculate_indicators(market_data)
        if not processed:
            equity_curve.append({"timestamp": current_time.isoformat(), "equity": equity})
            continue

        processed = strategy.generate_signals(processed)
        latest = processed[-1]
        signal = latest.get("signal", "NONE")
        signal_reason = latest.get("signal_reason", "No reason")
        signal_count[signal] += 1
        if signal != "NONE":
            signal_reasons[signal_reason] += 1

        if position is not None:
            exit_price = None
            exit_reason = None

            if position["side"] == "LONG":
                stop_hit = candle["low"] <= position["stop_loss"]
                target_hit = candle["high"] >= position["take_profit"]
                if stop_hit and target_hit:
                    exit_price = position["stop_loss"]
                    exit_reason = "SL and TP touched same candle (conservative SL)"
                elif stop_hit:
                    exit_price = position["stop_loss"]
                    exit_reason = "Stop loss hit intrabar"
                elif target_hit:
                    exit_price = position["take_profit"]
                    exit_reason = "Take profit hit intrabar"
            else:
                stop_hit = candle["high"] >= position["stop_loss"]
                target_hit = candle["low"] <= position["take_profit"]
                if stop_hit and target_hit:
                    exit_price = position["stop_loss"]
                    exit_reason = "SL and TP touched same candle (conservative SL)"
                elif stop_hit:
                    exit_price = position["stop_loss"]
                    exit_reason = "Stop loss hit intrabar"
                elif target_hit:
                    exit_price = position["take_profit"]
                    exit_reason = "Take profit hit intrabar"

            if exit_price is None:
                should_exit, reason = strategy.should_exit_position(
                    position,
                    latest,
                    position["entry_time"],
                    current_time,
                )
                if should_exit:
                    exit_price = candle["close"]
                    exit_reason = reason

            if exit_price is not None:
                gross_pnl = (
                    (exit_price - position["entry_price"]) * position["size"]
                    if position["side"] == "LONG"
                    else (position["entry_price"] - exit_price) * position["size"]
                )
                entry_fee = position["entry_price"] * position["size"] * TAKER_FEE
                exit_fee = exit_price * position["size"] * TAKER_FEE
                net_pnl = gross_pnl - entry_fee - exit_fee
                equity += net_pnl

                trades.append(
                    {
                        "side": position["side"],
                        "entry_time": position["entry_time"].isoformat(),
                        "exit_time": current_time.isoformat(),
                        "entry_price": position["entry_price"],
                        "exit_price": exit_price,
                        "size": position["size"],
                        "notional": position["entry_price"] * position["size"],
                        "gross_pnl": round(gross_pnl, 6),
                        "net_pnl": round(net_pnl, 6),
                        "exit_reason": exit_reason,
                        "signal_reason": position["signal_reason"],
                    }
                )
                position = None

        if position is None and signal in {"LONG", "SHORT"}:
            entry_price = latest["close"]
            stop_loss = strategy.calculate_stop_loss(entry_price, signal, latest.get("ATR"))
            take_profit = strategy.calculate_take_profit(entry_price, signal, latest.get("ATR"))
            size = strategy.calculate_position_size(equity, entry_price, stop_loss)
            size = loader.round_step_size(size, step_size)
            notional = size * entry_price

            if size <= 0:
                block_reasons["size_zero"] += 1
            elif notional < min_notional:
                block_reasons["below_min_notional"] += 1
            elif take_profit is None or stop_loss is None:
                block_reasons["invalid_tp_or_sl"] += 1
            else:
                position = {
                    "side": signal,
                    "entry_time": current_time,
                    "entry_price": entry_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "size": size,
                    "signal_reason": signal_reason,
                }

        mark_equity = equity
        if position is not None:
            unrealized = (
                (candle["close"] - position["entry_price"]) * position["size"]
                if position["side"] == "LONG"
                else (position["entry_price"] - candle["close"]) * position["size"]
            )
            estimated_close_fee = candle["close"] * position["size"] * TAKER_FEE
            mark_equity = equity + unrealized - estimated_close_fee

        peak_equity = max(peak_equity, mark_equity)
        drawdown_pct = ((peak_equity - mark_equity) / peak_equity * 100.0) if peak_equity else 0.0
        equity_curve.append(
            {
                "timestamp": current_time.isoformat(),
                "equity": round(mark_equity, 6),
                "drawdown_pct": round(drawdown_pct, 4),
            }
        )

    if position is not None:
        final_candle = candles_5m[-1]
        current_time = to_datetime(final_candle["timestamp"])
        exit_price = final_candle["close"]
        gross_pnl = (
            (exit_price - position["entry_price"]) * position["size"]
            if position["side"] == "LONG"
            else (position["entry_price"] - exit_price) * position["size"]
        )
        entry_fee = position["entry_price"] * position["size"] * TAKER_FEE
        exit_fee = exit_price * position["size"] * TAKER_FEE
        net_pnl = gross_pnl - entry_fee - exit_fee
        equity += net_pnl
        trades.append(
            {
                "side": position["side"],
                "entry_time": position["entry_time"].isoformat(),
                "exit_time": current_time.isoformat(),
                "entry_price": position["entry_price"],
                "exit_price": exit_price,
                "size": position["size"],
                "notional": position["entry_price"] * position["size"],
                "gross_pnl": round(gross_pnl, 6),
                "net_pnl": round(net_pnl, 6),
                "exit_reason": "Forced close at end of backtest",
                "signal_reason": position["signal_reason"],
            }
        )

    wins = sum(1 for trade in trades if trade["net_pnl"] > 0)
    losses = sum(1 for trade in trades if trade["net_pnl"] < 0)
    max_drawdown = max((point["drawdown_pct"] for point in equity_curve), default=0.0)

    result = {
        "symbol": symbol,
        "days": args.days,
        "mode": args.mode,
        "capital": args.capital,
        "leverage": args.leverage,
        "risk_per_trade": strategy.risk_per_trade,
        "min_notional": min_notional,
        "signals": dict(signal_count),
        "signal_reasons_top": signal_reasons.most_common(10),
        "blocked_entries": dict(block_reasons),
        "executed_trades": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate_pct": round((wins / len(trades) * 100.0), 2) if trades else 0.0,
        "starting_equity": args.capital,
        "ending_equity": round(equity, 6),
        "return_pct": round(((equity - args.capital) / args.capital * 100.0), 2) if args.capital else 0.0,
        "max_drawdown_pct": round(max_drawdown, 2),
        "assumptions": {
            "static_mode": "Reuses the current market_context.json snapshot for every historical candle.",
            "proxy_mode": "Derives funding, retail crowding, fear/greed, and OI proxies from historical price/volume. This is an inference, not real historical sentiment data.",
            "execution": "Single BTC position at a time, 0.05% taker fee per side, conservative intrabar exits when both TP and SL touch the same candle.",
        },
        "trades": trades,
    }

    return result


def main():
    args = parse_args()
    result = simulate_backtest(args)

    print("\n=== Confluence Backtest Summary ===")
    print(f"Mode: {result['mode']}")
    print(f"Period: last {result['days']} days")
    print(f"Capital: ${result['capital']:.2f}")
    print(f"Risk per trade: {result['risk_per_trade'] * 100:.2f}%")
    print(f"Signals: {result['signals']}")
    print(f"Blocked entries: {result['blocked_entries']}")
    print(f"Executed trades: {result['executed_trades']}")
    print(f"Win rate: {result['win_rate_pct']:.2f}%")
    print(f"Return: {result['return_pct']:.2f}%")
    print(f"Ending equity: ${result['ending_equity']:.2f}")
    print(f"Max drawdown: {result['max_drawdown_pct']:.2f}%")

    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
    print(f"Saved detailed results to {args.output}")


if __name__ == "__main__":
    main()
