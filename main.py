"""
ProfitBot Pro - Multi-Symbol Binance Futures Paper Trading Bot
Scans ALL top USDT Futures pairs simultaneously.
Everything displayed is NET of Binance fees.
"""
import time
import logging
import threading
from datetime import datetime
import os
from bot.data_loader import DataLoader
from bot.strategy import SmartMoneyStrategy
from bot.paper_exchange import PaperExchange, PaperAccount
from bot.notifier import TelegramNotifier
from bot.ai_brain import AIBrain
from dashboard import run_dashboard, dashboard_state, manual_close_requests, clear_history_requested, set_entries_state, panic_close_all_requested, reset_account_requested
import json
import argparse

# --- CLI ARGUMENTS ---
parser = argparse.ArgumentParser(description="ProfitBot Pro")
parser.add_argument("--profile", type=str, default="default", help="Profile name for this bot instance")
parser.add_argument("--port", type=int, default=int(os.environ.get('PORT', '5000')), help="Port for the dashboard")
parser.add_argument("--capital", type=float, default=None, help="Initial capital for this profile")
args = parser.parse_args()

PROFILE = args.profile if args.profile != "default" else os.getenv("BOT_PROFILE", "default")
DASHBOARD_PORT = args.port
STATE_FILE = f"bot_state_{PROFILE}.json" if PROFILE != "default" else "bot_state.json"
TRADE_LOG_FILE = f"trade_log_{PROFILE}.json" if PROFILE != "default" else "trade_log.json"

# Update dashboard initial capital early
dashboard_state["initial_capital"] = args.capital if args.capital is not None else float(os.getenv("INITIAL_CAPITAL", "10.00"))
dashboard_state["max_trades"] = 5 # Default for optimized logic

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MainBot")

# --- CONFIGURATION (loaded from environment variables for cloud safety) ---
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8774183137:AAF2O1EFz_2XjtF2LHA3ALmIuRvuTEBLtmM')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '8506152391')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '') # Set ONLY in Render Environment Variables, NEVER hardcode here!
TESTNET = True
# Priority: CLI Arg > Env Var > Default ($10.00)
INITIAL_CAPITAL = args.capital if args.capital is not None else float(os.getenv("INITIAL_CAPITAL", "10.00"))
LEVERAGE = int(os.environ.get('LEVERAGE', '45'))
TIMEFRAME = '5m'
TOP_N_SYMBOLS = int(os.environ.get('TOP_N_SYMBOLS', '60'))
MIN_VOLUME_USD = float(os.environ.get('MIN_VOLUME_USD', '1000000'))
# DASHBOARD_PORT handled by argparse above
BINANCE_FEE = 0.0005  # 0.05% taker fee (same for all Binance USDM)
MAX_CONCURRENT_TRADES = 5  # Reduced to 5 for better capital allocation on small accounts
MAX_TRADE_HOLD_MINUTES = int(os.environ.get('MAX_TRADE_HOLD_MINUTES', '180'))
TAKE_PROFIT_PCT = float(os.environ.get('TAKE_PROFIT_PCT', '0.03'))  # Increased to 3.0% TP
# -------------------------------------------------------------------------

# Shared bot state
bot_running = {"value": True}
allow_new_trades = {"value": True}

# Per-symbol state for dashboard
symbol_states = {}
symbol_states_lock = threading.Lock()

# Global concurrent-trade limiter
active_trades_lock = threading.Lock()
active_trades = {}  # symbol -> datetime of entry (UTC)

def save_bot_state():
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({"allow_new_trades": allow_new_trades["value"]}, f)
    except Exception as e:
        logger.error(f"Failed to save bot state: {e}")

def load_bot_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                allow_new_trades["value"] = data.get("allow_new_trades", True)
                logger.info(f"Loaded bot state: allow_new_trades={allow_new_trades['value']}")
        except Exception as e:
            logger.error(f"Failed to load bot state: {e}")

def safe_send_message(notifier, text):
    """Wrapped notifier call to prevent network/timeout errors from crashing threads."""
    try:
        notifier.send_message(text)
    except Exception as e:
        logger.error(f"Telegram Notification Error: {e}")

def sync_active_trades(global_account, max_concurrent):
    """
    On startup, reconstruct the active_trades list from the trade log.
    If a trade was OPENED but not CLOSED in the log, we assume it's active.
    """
    with active_trades_lock:
        active_trades.clear()
        # Find unmatched 'OPEN' actions in the log
        # Action names in PaperExchange are 'LONG', 'SHORT' for open and 'CLOSE (LONG/SHORT)' for close
        open_signals = {} # symbol -> entry_time
        for trade in global_account.trade_history:
            action = trade.get('action', '')
            symbol = trade.get('symbol')
            if action in ['LONG', 'SHORT']:
                open_signals[symbol] = trade.get('timestamp')
            elif action.startswith('CLOSE'):
                if symbol in open_signals:
                    del open_signals[symbol]
        
        for symbol, t_str in open_signals.items():
            try:
                # Approximate entry time if possible
                t_dt = datetime.fromisoformat(t_str) if t_str else datetime.utcnow()
                active_trades[symbol] = t_dt
            except:
                active_trades[symbol] = datetime.utcnow()
        
        if active_trades:
            logger.info(f"Synced {len(active_trades)} active trades from history log.")


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
            data_list = data_loader.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=250)
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
            last_candle = data_list[-1]
            
            # Compute TP/SL levels if in position
            sl_price = None
            tp_price = None
            if exchange.is_in_position:
                with symbol_states_lock:
                    tsl_pct = symbol_states.get(symbol, {}).get('trailing_sl_pct', -0.02)
                if exchange.position_direction == 'LONG':
                    sl_price = round(exchange.entry_price * (1 + tsl_pct), 6)
                    tp_price = round(exchange.entry_price * 1.03, 6)  # 3% TP target
                elif exchange.position_direction == 'SHORT':
                    sl_price = round(exchange.entry_price * (1 - tsl_pct), 6)
                    tp_price = round(exchange.entry_price * 0.97, 6)
            
            with symbol_states_lock:
                symbol_states[symbol] = {
                    "price": round(current_price, 6),
                    "signal": latest_signal,
                    "direction": exchange.position_direction or "FLAT",
                    "entry": round(exchange.entry_price, 6) if exchange.is_in_position else 0,
                    "size": exchange.position_size if exchange.is_in_position else 0,
                    "upnl": round(upnl_net, 6),
                    "min_notional": min_notional,
                    "fee_pct": f"{taker_fee*100:.3f}%",
                    # Indicator values
                    "rsi": round(last_candle.get('RSI', 0) or 0, 2),
                    "macd": round(last_candle.get('MACD', 0) or 0, 6),
                    "macd_signal": round(last_candle.get('MACD_Signal', 0) or 0, 6),
                    "macd_hist": round(last_candle.get('MACD_Hist', 0) or 0, 6),
                    "ema200": round(last_candle.get('EMA_200', 0) or 0, 6),
                    "atr": round(last_candle.get('ATR', 0) or 0, 6),
                    "bb_upper": round(last_candle.get('BB_Upper', 0) or 0, 6),
                    "bb_middle": round(last_candle.get('BB_Middle', 0) or 0, 6),
                    "bb_lower": round(last_candle.get('BB_Lower', 0) or 0, 6),
                    # TP/SL
                    "sl_price": sl_price,
                    "tp_price": tp_price,
                    # Recent candles for charting (last 60)
                    "candles": [{
                        "t": c['timestamp'],
                        "o": c['open'], "h": c['high'],
                        "l": c['low'],  "c": c['close']
                    } for c in data_list[-60:]]
                }

            # 4. Manage open position
            if exchange.is_in_position and 'ATR' in data_list[-1] and data_list[-1]['ATR'] is not None:
                entry_val = exchange.position_size * exchange.entry_price
                upnl_pct = upnl_net / entry_val if entry_val > 0 else 0
                
                # Retrieve current ATR for dynamic SL/TP calculation
                current_atr = data_list[-1]['ATR']
                atr_pct = (current_atr / current_price)
                
                # Default Stop Loss: 1.5% Max Net Loss (Aggressive for $10)
                default_sl_pct = max(-0.015, -(atr_pct * 1.5)) 
                
                # Fetch dynamically updated trailing SL for this position, or initialize to default SL
                with symbol_states_lock:
                    if 'trailing_sl_pct' not in symbol_states[symbol]:
                        symbol_states[symbol]['trailing_sl_pct'] = default_sl_pct
                    
                    sl_pct = symbol_states[symbol]['trailing_sl_pct']

                # Trailing Take-Profit Logic
                # Move the SL up as profit increases to let winners run
                # Step 1: Break-even + tiny profit (+0.1%) once profit reaches 0.5%
                if upnl_pct >= 0.005 and sl_pct < 0.001:
                    sl_pct = 0.001
                
                # Step 2: Lock in 50% of profit once profit reaches 1.0%
                if upnl_pct >= 0.010:
                    potential_new_sl = upnl_pct * 0.5 
                    if potential_new_sl > sl_pct:
                        sl_pct = potential_new_sl
                
                # Step 3: Lock in more profit once it hits 1.5%
                if upnl_pct >= 0.015:
                    potential_new_sl = upnl_pct * 0.65
                    if potential_new_sl > sl_pct:
                        sl_pct = potential_new_sl
                        
                with symbol_states_lock:
                    symbol_states[symbol]['trailing_sl_pct'] = sl_pct

                close_position = False
                close_reason = ""
                
                # --- MANUAL EXIT ---
                if symbol in manual_close_requests:
                    close_position = True
                    close_reason = "Manual Exit via Dashboard 🖱️"
                    logger.info(f"[{symbol}] {close_reason}")
                    manual_close_requests.remove(symbol)
                
                # --- HARD TAKE-PROFIT ---
                if upnl_pct >= TAKE_PROFIT_PCT:
                    close_position = True
                    close_reason = f"TAKE PROFIT HIT at {upnl_pct*100:.2f}% (NET) 🎯"
                    logger.info(f"[{symbol}] {close_reason} (Price: {current_price})")

                # --- MAX HOLD TIME SAFETY EXIT ---
                if not close_position:
                    with active_trades_lock:
                        entry_time = active_trades.get(symbol)
                    if entry_time:
                        hold_minutes = (datetime.utcnow() - entry_time).total_seconds() / 60
                        if hold_minutes >= MAX_TRADE_HOLD_MINUTES:
                            close_position = True
                            close_reason = f"MAX HOLD TIME ({MAX_TRADE_HOLD_MINUTES}m) reached ⏰"
                            logger.warning(f"[{symbol}] {close_reason}")

                # --- HIT DYNAMIC STOP-LOSS / TRAILING PROFIT STOP ---
                if not close_position and upnl_pct <= sl_pct:
                    close_position = True
                    if sl_pct > 0:
                        close_reason = f"TRAILING PROFIT STOP HIT at {sl_pct*100:.2f}% (NET)"
                        logger.warning(f"[{symbol}] {close_reason}")
                    else:
                        close_reason = f"STOP LOSS HIT at {sl_pct*100:.2f}% (NET)"
                        logger.warning(f"[{symbol}] {close_reason} (Price: {current_price}, SL: {sl_price})")

                # --- TREND-REVERSAL EXIT ---
                if not close_position:
                    if exchange.position_direction == 'LONG' and latest_signal == 'SHORT':
                        close_position = True
                        close_reason = "Reversal signal (LONG->SHORT)"
                        logger.warning(f"[{symbol}] {close_reason}. Closing.")
                    elif exchange.position_direction == 'SHORT' and latest_signal == 'LONG':
                        close_position = True
                        close_reason = "Reversal signal (SHORT->LONG)"
                        logger.warning(f"[{symbol}] {close_reason}. Closing.")

                if close_position:
                    gross_pnl = exchange.get_unrealized_pnl(current_price)
                    close_fee_cost = exchange.position_size * current_price * taker_fee
                    net_pnl = gross_pnl - close_fee_cost  # TRUE net profit after fees
                    entry_price = exchange.entry_price
                    notional = exchange.position_size * entry_price
                    net_pnl_pct = (net_pnl / notional * 100) if notional > 0 else 0

                    exchange.execute_market_order('CLOSE', exchange.position_size, current_price, latest_time)

                    # Remove from global active trades tracker
                    with active_trades_lock:
                        active_trades.pop(symbol, None)

                    # Clear trailing state
                    with symbol_states_lock:
                        if 'trailing_sl_pct' in symbol_states[symbol]:
                            del symbol_states[symbol]['trailing_sl_pct']

                    emoji = "✅" if net_pnl > 0 else "❌"
                    msg = (
                        f"{emoji} *{symbol} Trade Closed*\n"
                        f"Reason: _{close_reason}_\n"
                        f"Entry: `${entry_price:.4f}` → Exit: `${current_price:.4f}`\n"
                        f"Net PnL (after fees): `{'+'if net_pnl>=0 else ''}{net_pnl:.6f} USDT` ({net_pnl_pct:+.2f}%)\n"
                        f"Realized Balance: `${exchange.cash:.6f} USDT`\n"
                        f"📊 Dashboard: http://localhost:{DASHBOARD_PORT}"
                    )
                    safe_send_message(notifier, msg)

            # 5. Open new position
            if not exchange.is_in_position and latest_signal in ['LONG', 'SHORT']:
                with active_trades_lock:
                    if not allow_new_trades["value"]:
                        pass # Paused
                    elif len(active_trades) >= MAX_CONCURRENT_TRADES:
                        # User Request: If limit reached, log that we are waiting and re-validating on current data
                        if time.time() % 30 < 1: # Log once every ~30s to avoid spam
                            logger.info(f"[{symbol}] Slot limit (10/10) reached. Signal {latest_signal} active at ${current_price}. Re-validating in 1s...")
                        pass 
                    else:
                        # Inside the lock and inside the check!
                        current_bal = exchange.cash
                        min_qty = info.get('min_qty', 0.001)
                        min_entry_cost = min_qty * current_price
                        
                        target_notional = max(min_notional * 1.05, min_entry_cost * 1.05)
                        target_notional = max(target_notional, 5.05) # Binance typical min

                        # How much capital do we want to risk on this one trade?
                        capital_to_risk = current_bal / MAX_CONCURRENT_TRADES
                        
                        if capital_to_risk < 0.01:
                            logger.warning(f"[{symbol}] Skipping: Capital per trade too small (${capital_to_risk:.2f})")
                        else:
                            # Dynamic Leverage Calculation
                            req_leverage = target_notional / capital_to_risk
                            actual_leverage = max(1, min(75, int(req_leverage + 1)))

                            if actual_leverage > 75:
                                logger.warning(f"[{symbol}] Skipping: Requires {actual_leverage}x leverage (Max 75x) for ${target_notional:.2f} notional.")
                            else:
                                raw_size = target_notional / current_price
                                size = data_loader.round_step_size(raw_size, step_size)
                                if size <= 0: size = info['min_qty']

                                actual_notional = size * current_price
                                open_fee = actual_notional * taker_fee
                                close_fee_est = actual_notional * taker_fee
                                total_fees = open_fee + close_fee_est

                                # Pre-trade Profitability Check
                                expected_gross_profit = actual_notional * TAKE_PROFIT_PCT
                                expected_net_profit = expected_gross_profit - total_fees

                                if expected_net_profit <= 0:
                                    logger.warning(f"[{symbol}] Skipping: Unprofitable mathematically. Expected net profit: ${expected_net_profit:.4f} (Fees: ${total_fees:.4f})")
                                elif current_bal * actual_leverage >= actual_notional:
                                    strategy.leverage = actual_leverage
                                    success = exchange.execute_market_order(latest_signal, size, current_price, latest_time)
                                    if success:
                                        active_trades[symbol] = datetime.utcnow()
                                        safe_send_message(notifier,
                                            f"🔔 *{symbol} — New {latest_signal}* ({len(active_trades)}/{MAX_CONCURRENT_TRADES} slots)\n"
                                            f"Entry: `${current_price:.4f}` | Notional: `${actual_notional:.2f}`\n"
                                            f"Lev: `{actual_leverage}x` | Risking: `${(actual_notional/actual_leverage):.2f}`\n"
                                            f"Fee: `-${open_fee:.6f}`\n"
                                            f"📊 Dashboard: http://localhost:{DASHBOARD_PORT}"
                                        )

        except Exception as e:
            logger.error(f"[{symbol}] Error: {e}")

        time.sleep(1)  # Minimal sleep for zero-delay hyperscaling (1s)


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
                                # Calculate percentage uPnL for Telegram
                                entry_val = d['size'] * d['entry']
                                upnl_pct = (d['upnl'] / entry_val * 100) if entry_val > 0 else 0
                                lines.append(f"• {sym} `{d['direction']}` @ `${d['entry']:.4f}` | uPnL: `{pnl_str}` ({upnl_pct:+.2f}%)")
                        else:
                            lines.append("_No open positions. Scanning..._")
                        lines.append(f"\n📊 Dashboard: http://localhost:{DASHBOARD_PORT}")
                        safe_send_message(notifier, "\n".join(lines))

                elif text == "/symbols":
                    with symbol_states_lock:
                        syms = list(symbol_states.keys())
                    safe_send_message(notifier, f"🌐 *Scanning {len(syms)} markets:*\n`{'`, `'.join(syms)}`")

                elif text == "/stop":
                    bot_running["value"] = False
                    save_bot_state() # PERSIST
                    safe_send_message(notifier, "🛑 *All scanners paused.* Send `/start` to resume.")

                elif text == "/start":
                    bot_running["value"] = True
                    save_bot_state() # PERSIST
                    safe_send_message(notifier, "🚀 *All scanners resumed!* Scanning the market...")

                elif text == "/pause_entries":
                    allow_new_trades["value"] = False
                    save_bot_state() # PERSIST
                    safe_send_message(notifier, "⏸️ *New trade entries PAUSED.* Scanner still tracking open positions.")

                elif text == "/resume_entries":
                    allow_new_trades["value"] = True
                    save_bot_state() # PERSIST
                    safe_send_message(notifier, "▶️ *New trade entries RESUMED!* Bot will now enter new positions.")

                elif text in ["hi", "hii", "hello", "hey", "/help", "help", "try", "/try"]:
                    safe_send_message(notifier,
                        "👋 *Hello! I am ProfitBot Pro.*\n\n"
                        "Here is what you can tell me to do:\n"
                        "• `/status` - View live PnL and active trades.\n"
                        "• `/symbols` - See what coins I am scanning.\n"
                        "• `/stop` - Pause the bot (no new entries).\n"
                        "• `/start` - Resume scanning the market.\n"
                        "• `/pause_entries` - Stop entering NEW trades.\n"
                        "• `/resume_entries` - Allow new trades again.\n"
                        "• Or just ask me a question about my strategy!"
                    )

                else:
                    with symbol_states_lock:
                        # Build a highly detailed live state report for the AI
                        active_positions = [(s, d) for s, d in symbol_states.items() if d['direction'] != 'FLAT']
                        scanning_count = len(symbol_states)
                        
                        context_lines = [
                            f"Live Trading Status: Active (Scanning {scanning_count} pairs)",
                            f"Paper Capital: ${INITIAL_CAPITAL} USDT",
                            f"Total Open Positions: {len(active_positions)}"
                        ]
                        
                        if active_positions:
                            context_lines.append("\n--- OPEN POSITIONS ---")
                            total_upnl = 0
                            for sym, data in active_positions:
                                pnl = data.get('upnl', 0)
                                total_upnl += pnl
                                sign = "+" if pnl >= 0 else ""
                                context_lines.append(
                                    f"• {sym}: {data['direction']} at ${data['entry']:.5f} | "
                                    f"Current Price: ${data['price']:.5f} | "
                                    f"Net PnL: {sign}${pnl:.4f} | "
                                    f"Trailing SL: {data.get('trailing_sl_pct', 0) * 100:.2f}%"
                                )
                            context_lines.append(f"\nTotal Unrealized Net PnL: ${total_upnl:.4f}")
                        else:
                            context_lines.append("No positions open right now.")
                            
                        context = "\n".join(context_lines)

                    # Pass chat_id to maintain memory per-user
                    ai_reply = ai_brain.generate_reply(text, context=context, chat_id=str(chat_id))
                    
                    if ai_reply:
                        safe_send_message(notifier, ai_reply)
                    else:
                        safe_send_message(notifier, "🤔 Try `/status`, `/symbols`, `/stop`, or `/start`!")

        except Exception as e:
            logger.error(f"Listener Error: {e}")
        time.sleep(5)


def run_paper_trading():
    logger.info("🤖 ProfitBot Pro — Multi-Symbol Scanner Starting...")

    # Initialize shared components
    data_loader = DataLoader(exchange_id='binanceusdm', testnet=TESTNET)
    notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    ai_brain = AIBrain(GEMINI_API_KEY)
    global_account = PaperAccount(initial_capital=INITIAL_CAPITAL, log_file=TRADE_LOG_FILE)

    # 1. Fetch top symbols dynamically
    logger.info("Fetching top Binance Futures symbols by volume...")
    symbols = data_loader.get_top_futures_symbols(top_n=TOP_N_SYMBOLS, min_volume_usd=MIN_VOLUME_USD)
    logger.info(f"Will scan {len(symbols)} symbols: {symbols}")

    # 0. Load persisted state
    load_bot_state()
    sync_active_trades(global_account, MAX_CONCURRENT_TRADES)

    # 1. Start Dashboard
    dashboard_thread = threading.Thread(
        target=run_dashboard, 
        kwargs={
            "host": "0.0.0.0", 
            "port": DASHBOARD_PORT, 
            "log_file": TRADE_LOG_FILE, 
            "profile_name": PROFILE
        }, 
        daemon=True
    )
    dashboard_thread.start()
    logger.info(f"📊 Dashboard: http://localhost:{DASHBOARD_PORT}")

    # 3. Start Telegram Listener
    tg_thread = threading.Thread(target=telegram_listener, args=(notifier, ai_brain), daemon=True)
    tg_thread.start()

    # 4. Send startup notification
    safe_send_message(notifier,
        f"🚀 *ProfitBot Pro — Multi-Scanner Online!*\n"
        f"📡 Scanning *{len(symbols)} markets* simultaneously\n"
        f"💰 Capital: `${INITIAL_CAPITAL} USDT`\n"
        f"🛠️ Settings: `{'ON' if allow_new_trades['value'] else 'OFF'}` Entries\n"
        f"📊 Dashboard: `http://localhost:{DASHBOARD_PORT}`"
    )

    # 5. Create threads
    symbol_threads = []
    logger.info(f"Starting scanners for {len(symbols)} symbols...")
    for symbol in symbols:
        strategy = SmartMoneyStrategy(leverage=LEVERAGE)
        exchange = PaperExchange(initial_capital=INITIAL_CAPITAL, taker_fee=BINANCE_FEE)
        exchange.shared_account = global_account
        exchange.symbol = symbol

        # Resume state if this symbol was in an open trade
        with active_trades_lock:
            if symbol in active_trades:
                # Find the open trade in history to get entry price and size
                for trade in reversed(global_account.trade_history):
                    if trade.get('symbol') == symbol and trade.get('action') in ['LONG', 'SHORT']:
                        exchange.position_direction = trade['action']
                        exchange.position_size = trade['size']
                        exchange.entry_price = trade['price']
                        logger.info(f"[{symbol}] Resumed {exchange.position_direction} position from log.")
                        break

        t = threading.Thread(
            target=scan_symbol,
            args=(symbol, data_loader, strategy, exchange, notifier),
            daemon=True,
            name=f"Scanner-{symbol}"
        )
        t.start()
        symbol_threads.append(t)
        time.sleep(0.05) 

    logger.info("All scanners running. ProfitBot Pro is LIVE.")

    # 6. Main thread: update dashboard state from symbol_states
    logger.info("All scanners running. Updating dashboard...")
    try:
        while True:
            with symbol_states_lock:
                dashboard_state["symbols"] = dict(symbol_states)
                # Compute total unrealized PnL across ALL open positions for real-time balance
                total_upnl = sum(
                    s.get('upnl', 0) for s in symbol_states.values()
                    if s.get('direction', 'FLAT') != 'FLAT'
                )
                dashboard_state["trades"] = list(global_account.trade_history)
            with active_trades_lock:
                open_count = len(active_trades)
            # Pass live balance (realized cash + unrealized PnL) and trade slot info to dashboard
            dashboard_state["total_upnl"] = round(total_upnl, 6)
            dashboard_state["realized_cash"] = round(global_account.get_cash(), 6)
            dashboard_state["live_balance"] = round(global_account.get_cash() + total_upnl, 6)
            dashboard_state["initial_capital"] = INITIAL_CAPITAL
            dashboard_state["open_trade_count"] = open_count
            dashboard_state["max_trades"] = MAX_CONCURRENT_TRADES
            dashboard_state["bot_status"] = "RUNNING 🟢" if bot_running["value"] else "STOPPED 🛑"
            dashboard_state["entries_allowed"] = allow_new_trades["value"]

            # -- Handle Dashboard Toggle Request --
            if set_entries_state[0] is not None:
                new_val = set_entries_state[0]
                set_entries_state[0] = None
                if allow_new_trades["value"] != new_val:
                    allow_new_trades["value"] = new_val
                    save_bot_state() # PERSIST
                    state_str = "RESUMED ▶️" if allow_new_trades["value"] else "PAUSED ⏸️"
                    safe_send_message(notifier, f"📢 *Dashboard Update:* New trade entries {state_str}")
                    logger.info(f"Entry control set via dashboard: {state_str}")

            # -- Handle History Clear Request --
            if clear_history_requested[0]:
                with global_account.lock:
                    global_account.trade_history = []
                    if os.path.exists(TRADE_LOG_FILE):
                        try:
                            with open(TRADE_LOG_FILE, "w") as f:
                                json.dump([], f)
                        except: pass
                clear_history_requested[0] = False
                logger.info("Trade history cleared in memory and on disk.")

            # -- Handle Panic Close All Request --
            if panic_close_all_requested[0]:
                with active_trades_lock:
                    for sym in active_trades:
                        manual_close_requests.add(sym)
                panic_close_all_requested[0] = False
                logger.warning("PANIC: Closing all active trades from dashboard request!")
                safe_send_message(notifier, "🚨 *PANIC BUTTON PRESSED* 🚨\nClosing all active trades immediately!")

            # -- Handle Reset Account Request --
            if reset_account_requested[0]:
                with global_account.lock:
                    global_account.cash = INITIAL_CAPITAL
                    global_account.trade_history = []
                    if os.path.exists(TRADE_LOG_FILE):
                        try:
                            with open(TRADE_LOG_FILE, "w") as f:
                                json.dump([], f)
                        except: pass
                
                with active_trades_lock:
                    for sym in active_trades:
                        manual_close_requests.add(sym)
                    active_trades.clear()
                
                reset_account_requested[0] = False
                logger.warning(f"♻️ ACCOUNT RESET to ${INITIAL_CAPITAL:.2f} requested from dashboard!")
                safe_send_message(notifier, f"♻️ *ACCOUNT RESET*\nBalance is now ${INITIAL_CAPITAL:.2f} USDT. All history cleared. Any stuck trades will be closed.")

            time.sleep(5)

    except KeyboardInterrupt:
        bot_running["value"] = False
        logger.info("Bot stopped by user.")


if __name__ == "__main__":
    run_paper_trading()
