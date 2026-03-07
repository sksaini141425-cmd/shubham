"""
ProfitBot Pro - Multi-Symbol Binance Futures Paper Trading Bot
Scans ALL top USDT Futures pairs simultaneously.
Everything displayed is NET of Binance fees.
"""
import time
import logging
import threading
import os
from bot.data_loader import DataLoader
from bot.strategy import SmartMoneyStrategy
from bot.paper_exchange import PaperExchange
from bot.notifier import TelegramNotifier
from bot.ai_brain import AIBrain
from dashboard import run_dashboard, dashboard_state

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MainBot")

# --- CONFIGURATION (loaded from environment variables for cloud safety) ---
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8774183137:AAF2O1EFz_2XjtF2LHA3ALmIuRvuTEBLtmM')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '8506152391')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'AIzaSyDD473_cCMhXzb9s8iX1U3IWcuz8uYKjbg')
INITIAL_CAPITAL = float(os.environ.get('INITIAL_CAPITAL', '2.98'))
LEVERAGE = int(os.environ.get('LEVERAGE', '45'))
TIMEFRAME = '1m'
TOP_N_SYMBOLS = int(os.environ.get('TOP_N_SYMBOLS', '20'))
MIN_VOLUME_USD = float(os.environ.get('MIN_VOLUME_USD', '50000000'))
DASHBOARD_PORT = int(os.environ.get('PORT', '5000'))  # Render sets PORT automatically
BINANCE_FEE = 0.0005  # 0.05% taker fee (same for all Binance USDM)
# -------------------------------------------------------------------------

# Shared bot state
bot_running = {"value": True}

# Per-symbol state for dashboard
symbol_states = {}
symbol_states_lock = threading.Lock()


def scan_symbol(symbol, data_loader, strategy, exchange, notifier):
    """
    Runs the trading loop for ONE symbol in its own thread.
    Uses the per-symbol min notional and fees from Binance exchangeInfo.
    All PnL is fee-inclusive (net profit after Binance fees).
    """
    logger.info(f"[{symbol}] Scanner started.")
    exchange.symbol = symbol

    # Fetch per-symbol Binance rules
    info = data_loader.get_symbol_info(symbol)
    min_notional = info['min_notional']           # e.g. $5 for DOGE, $100 for BTC
    taker_fee = info['taker_fee']                 # 0.05% for all USDM
    step_size = info['step_size']                 # lot size precision
    exchange.taker_fee = taker_fee
    exchange.maker_fee = info['maker_fee']

    logger.info(f"[{symbol}] Rules — Min Notional: ${min_notional} | Taker Fee: {taker_fee*100:.3f}%")

    while True:
        try:
            if not bot_running["value"]:
                time.sleep(10)
                continue

            # 1. Fetch candles
            data_list = data_loader.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=100)
            if not data_list:
                time.sleep(15)
                continue

            current_price = data_list[-1]['close']
            latest_time = data_list[-1]['timestamp']

            # 2. Calculate indicators + signals
            data_list = strategy.calculate_indicators(data_list)
            data_list = strategy.generate_signals(data_list)

            if not data_list or 'signal' not in data_list[-1]:
                time.sleep(15)
                continue

            latest_signal = data_list[-1]['signal']
            sma = data_list[-1].get('SMA', current_price)

            # 3. Unrealized PnL (net of open fee + estimated close fee)
            upnl_gross = exchange.get_unrealized_pnl(current_price)
            close_fee = exchange.position_size * current_price * taker_fee if exchange.is_in_position else 0
            upnl_net = upnl_gross - close_fee

            # Update dashboard state
            with symbol_states_lock:
                symbol_states[symbol] = {
                    "price": round(current_price, 6),
                    "signal": latest_signal,
                    "direction": exchange.position_direction or "FLAT",
                    "entry": round(exchange.entry_price, 6) if exchange.is_in_position else 0,
                    "upnl": round(upnl_net, 6),
                    "min_notional": min_notional,
                    "fee_pct": f"{taker_fee*100:.3f}%"
                }

            # 4. Manage open position
            if exchange.is_in_position and 'ATR' in data_list[-1] and data_list[-1]['ATR'] is not None:
                entry_val = exchange.position_size * exchange.entry_price
                upnl_pct = upnl_net / entry_val if entry_val > 0 else 0
                
                # Retrieve current ATR for dynamic SL/TP calculation
                current_atr = data_list[-1]['ATR']
                atr_pct = (current_atr / current_price)
                
                # Default Stop Loss: 1.5x ATR, but cap at max 2% Net Loss
                default_sl_pct = min(-0.02, -(atr_pct * 1.5))
                
                # Fetch dynamically updated trailing SL for this position, or initialize to default SL
                with symbol_states_lock:
                    if 'trailing_sl_pct' not in symbol_states[symbol]:
                        symbol_states[symbol]['trailing_sl_pct'] = default_sl_pct
                    
                    sl_pct = symbol_states[symbol]['trailing_sl_pct']

                # Trailing Take-Profit Logic
                # Move the SL up as profit increases to let winners run
                # Step 1: Break-even (0% SL) once profit reaches 0.5%
                if upnl_pct >= 0.005 and sl_pct < 0.0:
                    sl_pct = 0.0
                
                # Step 2: Lock in 50% of the profit if it rockets up
                # e.g. If upnl_pct is 3%, set SL to 1.5% profit
                if upnl_pct >= 0.015:
                    potential_new_sl = upnl_pct * 0.5 
                    if potential_new_sl > sl_pct:
                        sl_pct = potential_new_sl
                        
                with symbol_states_lock:
                    symbol_states[symbol]['trailing_sl_pct'] = sl_pct

                close_position = False
                
                # Hit Dynamic Stop-Loss / Trailing Profit Stop
                if upnl_pct <= sl_pct:
                    if sl_pct > 0:
                        logger.warning(f"[{symbol}] TRAILING PROFIT STOP HIT at {sl_pct*100:.2f}% (NET)")
                    else:
                        logger.warning(f"[{symbol}] STOP LOSS HIT at {sl_pct*100:.2f}% (NET)")
                    close_position = True

                # Trend-Reversal Exit (Emergency Eject)
                if not close_position:
                    if exchange.position_direction == 'LONG' and latest_signal == 'SHORT':
                        close_position = True
                        logger.warning(f"[{symbol}] Reversal signal (LONG->SHORT). Closing.")
                    elif exchange.position_direction == 'SHORT' and latest_signal == 'LONG':
                        close_position = True
                        logger.warning(f"[{symbol}] Reversal signal (SHORT->LONG). Closing.")

                if close_position:
                    gross_pnl = exchange.get_unrealized_pnl(current_price)
                    close_fee_cost = exchange.position_size * current_price * taker_fee
                    net_pnl = gross_pnl - close_fee_cost  # TRUE net profit after fees
                    entry_price = exchange.entry_price
                    notional = exchange.position_size * entry_price
                    net_pnl_pct = (net_pnl / notional * 100) if notional > 0 else 0

                    exchange.execute_market_order('CLOSE', exchange.position_size, current_price, latest_time)

                    # Clear trailing state
                    with symbol_states_lock:
                        if 'trailing_sl_pct' in symbol_states[symbol]:
                            del symbol_states[symbol]['trailing_sl_pct']

                    emoji = "✅" if net_pnl > 0 else "❌"
                    msg = (
                        f"{emoji} *{symbol} Trade Closed*\n"
                        f"Entry: `${entry_price:.4f}` → Exit: `${current_price:.4f}`\n"
                        f"Net PnL (after fees): `{'+'if net_pnl>=0 else ''}{net_pnl:.6f} USDT` ({net_pnl_pct:+.2f}%)\n"
                        f"Balance: `${exchange.cash:.6f} USDT`\n"
                        f"📊 Dashboard: http://localhost:{DASHBOARD_PORT}"
                    )
                    notifier.send_message(msg)

            # 5. Open new position using PER-SYMBOL min_notional
            if not exchange.is_in_position and latest_signal in ['LONG', 'SHORT']:
                # Use capital leverage to meet THIS symbol's minimum notional
                target_notional = max(min_notional * 1.05, min_notional + 0.1)  # 5% buffer above minimum
                req_leverage = target_notional / exchange.cash if exchange.cash > 0 else LEVERAGE
                actual_leverage = max(LEVERAGE, min(125, int(req_leverage + 1)))
                strategy.leverage = actual_leverage

                # Round size to valid step size for this symbol
                raw_size = target_notional / current_price
                size = data_loader.round_step_size(raw_size, step_size)
                if size <= 0:
                    size = info['min_qty']  # fallback to minimum

                actual_notional = size * current_price
                open_fee = actual_notional * taker_fee

                if exchange.cash * actual_leverage >= actual_notional:
                    success = exchange.execute_market_order(latest_signal, size, current_price, latest_time)
                    if success:
                        msg = (
                            f"🔔 *{symbol} — New {latest_signal}*\n"
                            f"Entry: `${current_price:.6f}`\n"
                            f"Notional: `${actual_notional:.2f}` (min: ${min_notional}) at `{actual_leverage}x`\n"
                            f"Open Fee: `-${open_fee:.6f} USDT` ({taker_fee*100:.3f}%)\n"
                            f"📊 Dashboard: http://localhost:{DASHBOARD_PORT}"
                        )
                        notifier.send_message(msg)

        except Exception as e:
            logger.error(f"[{symbol}] Error: {e}")

        time.sleep(15)  # 15s between checks per symbol to respect rate limits


def telegram_listener(notifier, ai_brain):
    """Background thread listening for Telegram commands."""
    offset = None
    logger.info("Telegram Command Listener started...")

    while True:
        try:
            updates = notifier.get_updates(offset=offset)
            for update in updates:
                offset = update.get("update_id") + 1
                msg = update.get("message", {})
                text = msg.get("text", "").lower().strip()
                chat_id = msg.get("chat", {}).get("id")

                if str(chat_id) != str(notifier.chat_id):
                    continue

                if text == "/status":
                    with symbol_states_lock:
                        lines = [f"📊 *Live Scanner Status* — {len(symbol_states)} symbols\n"]
                        # Show positions first
                        in_pos = [(s, d) for s, d in symbol_states.items() if d['direction'] != 'FLAT']
                        if in_pos:
                            lines.append("*🔥 Open Positions:*")
                            for sym, d in in_pos:
                                pnl_str = f"{'+'if d['upnl']>=0 else ''}{d['upnl']:.6f}"
                                lines.append(f"• {sym} `{d['direction']}` @ `${d['entry']:.4f}` | uPnL (net): `{pnl_str}`")
                        else:
                            lines.append("_No open positions. Scanning..._")
                        lines.append(f"\n📊 Dashboard: http://localhost:{DASHBOARD_PORT}")
                        notifier.send_message("\n".join(lines))

                elif text == "/symbols":
                    with symbol_states_lock:
                        syms = list(symbol_states.keys())
                    notifier.send_message(f"🌐 *Scanning {len(syms)} markets:*\n`{'`, `'.join(syms)}`")

                elif text == "/stop":
                    bot_running["value"] = False
                    notifier.send_message("🛑 *All scanners paused.* Send `/start` to resume.")

                elif text == "/start":
                    bot_running["value"] = True
                    notifier.send_message("🚀 *All scanners resumed!* Scanning the market...")

                else:
                    with symbol_states_lock:
                        active = [(s, d) for s, d in symbol_states.items() if d['direction'] != 'FLAT']
                    context = (
                        f"Scanning {len(symbol_states)} Binance Futures markets. "
                        f"Capital: ${INITIAL_CAPITAL}. "
                        f"Open positions: {len(active)}. "
                        f"Strategy: Smart Money Multi-Indicator Confirmation (RSI, MACD, BB). "
                        f"All PnL shown is NET of Binance fees (0.05% per side). "
                        f"Trading status: {'Active' if bot_running['value'] else 'Stopped'}."
                    )
                    ai_reply = ai_brain.generate_reply(text, context=context)
                    if ai_reply:
                        notifier.send_message(ai_reply)
                    else:
                        notifier.send_message("🤔 Try `/status`, `/symbols`, `/stop`, or `/start`!")

        except Exception as e:
            logger.error(f"Listener Error: {e}")
        time.sleep(5)


def run_paper_trading():
    logger.info("🤖 ProfitBot Pro — Multi-Symbol Scanner Starting...")

    # Initialize shared components
    data_loader = DataLoader(exchange_id='binanceusdm', testnet=False)
    notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    ai_brain = AIBrain(GEMINI_API_KEY)

    # 1. Fetch top symbols dynamically
    logger.info("Fetching top Binance Futures symbols by volume...")
    symbols = data_loader.get_top_futures_symbols(top_n=TOP_N_SYMBOLS, min_volume_usd=MIN_VOLUME_USD)
    logger.info(f"Will scan {len(symbols)} symbols: {symbols}")

    # 2. Start Dashboard
    dashboard_thread = threading.Thread(
        target=run_dashboard, kwargs={"host": "0.0.0.0", "port": DASHBOARD_PORT}, daemon=True
    )
    dashboard_thread.start()
    logger.info(f"📊 Dashboard: http://localhost:{DASHBOARD_PORT}")

    # 3. Start Telegram Listener
    tg_thread = threading.Thread(target=telegram_listener, args=(notifier, ai_brain), daemon=True)
    tg_thread.start()

    # 4. Send startup notification
    notifier.send_message(
        f"🚀 *ProfitBot Pro — Multi-Scanner Online!*\n"
        f"📡 Scanning *{len(symbols)} markets* simultaneously\n"
        f"💰 Capital: `${INITIAL_CAPITAL} USDT` (paper)\n"
        f"🛡️ Smart Money: RSI + MACD + ATR Trailing SL\n"
        f"💸 All PnL shown after Binance fees\n"
        f"📊 Dashboard: `http://localhost:{DASHBOARD_PORT}`\n\n"
        f"Markets: `{'`, `'.join(symbols[:10])}`... and {len(symbols)-10} more!"
    )

    # 5. Create one strategy + exchange per symbol and start threads
    symbol_threads = []
    for symbol in symbols:
        strategy = SmartMoneyStrategy(leverage=LEVERAGE)
        exchange = PaperExchange(initial_capital=INITIAL_CAPITAL, taker_fee=BINANCE_FEE)
        exchange.symbol = symbol

        t = threading.Thread(
            target=scan_symbol,
            args=(symbol, data_loader, strategy, exchange, notifier),
            daemon=True,
            name=f"Scanner-{symbol}"
        )
        t.start()
        symbol_threads.append(t)
        logger.info(f"[{symbol}] Scanner thread launched.")
        time.sleep(0.3)  # Stagger starts to avoid API rate limits

    # 6. Main thread: update dashboard state from symbol_states
    logger.info("All scanners running. Updating dashboard...")
    try:
        while True:
            with symbol_states_lock:
                dashboard_state["symbols"] = dict(symbol_states)
            dashboard_state["bot_status"] = "RUNNING 🟢" if bot_running["value"] else "STOPPED 🛑"
            time.sleep(5)

    except KeyboardInterrupt:
        bot_running["value"] = False
        logger.info("Bot stopped by user.")


if __name__ == "__main__":
    run_paper_trading()
