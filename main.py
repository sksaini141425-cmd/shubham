"""
ProfitBot Pro - Multi-Symbol Binance Futures Paper Trading Bot
Scans ALL top USDT Futures pairs simultaneously.
Everything displayed is NET of Binance fees.
"""
import os
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(__file__), '.env')
loaded = load_dotenv(env_path, override=True)
print(f"DEBUG: .env file loaded from {env_path}: {loaded}")

import time
import logging
import threading
import warnings
from urllib3.exceptions import InsecureRequestWarning

# Suppress insecure request warnings
warnings.simplefilter('ignore', InsecureRequestWarning)
from datetime import datetime
import os
from bot.data_loader import DataLoader
from bot.strategy import SmartMoneyStrategy, RSDTraderStrategy, EliteScalperStrategy, Scalper70Strategy, HyperScalper25Strategy, DiamondSniperStrategy
from bot.signal_loader import SignalLoader
from bot.binance_exchange import BinanceExchange
from bot.mexc_exchange import MEXCExchange
from bot.bybit_exchange import BybitExchange
from bot.paper_exchange import PaperExchange, PaperAccount
from bot.notifier import TelegramNotifier
try:
    from bot.ai_brain import AIBrain
except ImportError:
    AIBrain = None
from bot.signal_intelligence import SignalIntelligence
from dashboard import run_dashboard, dashboard_state, manual_close_requests, clear_history_requested, set_entries_state, panic_close_all_requested, reset_account_requested
import json
import argparse

# --- CLI ARGUMENTS ---
parser = argparse.ArgumentParser(description="ProfitBot Pro")
parser.add_argument("--profile", type=str, default="default", help="Profile name for this bot instance")
parser.add_argument("--port", type=int, default=int(os.environ.get('PORT', '5000')), help="Port for the dashboard")
parser.add_argument("--capital", type=float, default=None, help="Initial capital for this profile")
parser.add_argument("--symbols_offset", type=int, default=0, help="Offset for market scanning")
parser.add_argument("--strategy", type=str, default="smart_money", help="Strategy to use: smart_money, rsd")
parser.add_argument("--max_trades", type=int, default=None, help="Maximum concurrent trades")
parser.add_argument("--leverage", type=int, default=None, help="Leverage for this bot instance")
parser.add_argument("--exchange", type=str, default=os.environ.get('EXCHANGE', 'bybit'), help="Exchange to use: binance, mexc, bybit")
args = parser.parse_args()

PROFILE = args.profile if args.profile != "default" else os.getenv("BOT_PROFILE", "default")
DASHBOARD_PORT = args.port
STATE_FILE = f"bot_state_{PROFILE}.json" if PROFILE != "default" else "bot_state.json"
TRADE_LOG_FILE = f"trade_log_{PROFILE}.json" if PROFILE != "default" else "trade_log.json"


# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MainBot")

# --- CONFIGURATION (loaded from environment variables for cloud safety) ---
# IMPORTANT: do not hardcode secrets in code (safe for uploads).
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '') # Set ONLY in Render Environment Variables, NEVER hardcode here!
TESTNET = os.environ.get('USE_TESTNET', 'false').lower() == 'true'
# Priority: CLI Arg > Env Var > Default ($10.00)
INITIAL_CAPITAL = args.capital if args.capital is not None else float(os.getenv("INITIAL_CAPITAL", "10.00"))
SYMBOLS_OFFSET = args.symbols_offset if args.symbols_offset is not None else int(os.getenv("SYMBOLS_OFFSET", "0"))
# Priority: CLI Arg > Env Var > Default (45)
LEVERAGE = args.leverage if args.leverage is not None else int(os.environ.get('LEVERAGE', '45'))
TIMEFRAME = '5m'
TOP_N_SYMBOLS = int(os.environ.get('TOP_N_SYMBOLS', '60'))
MIN_VOLUME_USD = float(os.environ.get('MIN_VOLUME_USD', '1000000'))
# DASHBOARD_PORT handled by argparse above
BINANCE_FEE = 0.0005  # 0.05% taker fee (same for all Binance USDM)
USE_REAL_EXCHANGE = os.environ.get('USE_REAL_EXCHANGE', 'false').lower() == 'true'
EXCHANGE_NAME = args.exchange.lower() if args.exchange else os.environ.get('EXCHANGE', 'binance').lower()
BINANCE_API_KEY = os.environ.get('BINANCE_API_KEY', '').strip()
BINANCE_API_SECRET = os.environ.get('BINANCE_API_SECRET', '').strip()
MEXC_API_KEY = os.environ.get('MEXC_API_KEY', '').strip()
MEXC_API_SECRET = os.environ.get('MEXC_API_SECRET', '').strip()
BYBIT_API_KEY = os.environ.get('BYBIT_API_KEY', '').strip()
BYBIT_API_SECRET = os.environ.get('BYBIT_API_SECRET', '').strip()
MAX_CONCURRENT_TRADES = args.max_trades if args.max_trades is not None else int(os.environ.get('MAX_CONCURRENT_TRADES', '15'))
# If MAX_CONCURRENT_TRADES is very high (e.g. 999), we treat it as 'unlimited' 
# and use a fixed capital partition for sizing.
IS_UNLIMITED = MAX_CONCURRENT_TRADES >= 500
MAX_TRADE_HOLD_MINUTES = 180
TAKE_PROFIT_PCT = float(os.environ.get('TAKE_PROFIT_PCT', '0.03'))

print(f"DEBUG: USE_REAL_EXCHANGE={USE_REAL_EXCHANGE}")
print(f"DEBUG: BINANCE_API_KEY_LEN={len(BINANCE_API_KEY)}")
print(f"DEBUG: BINANCE_API_SECRET_LEN={len(BINANCE_API_SECRET)}")
# -------------------------------------------------------------------------

# Update dashboard state for this profile
dashboard_state["profile_name"] = PROFILE
dashboard_state["initial_capital"] = INITIAL_CAPITAL
dashboard_state["max_trades"] = MAX_CONCURRENT_TRADES
dashboard_state["log_file"] = TRADE_LOG_FILE
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
            elif action.startswith('CLOSE') or action.startswith('LIQUIDATION'):
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


def scan_symbol(symbol, data_loader, strategy, exchange, notifier, signal_intel):
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
            data_list = data_loader.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=1000)
            if not data_list:
                time.sleep(15)
                continue

            current_price = data_list[-1]['close']
            latest_time = data_list[-1]['timestamp']

            # 2. Calculate indicators + signals
            try:
                data_list = strategy.calculate_indicators(data_list)
                data_list = strategy.generate_signals(data_list)
            except Exception as e:
                logger.error(f"[{symbol}] Indicator/Signal Error: {e}")
                time.sleep(15)
                continue

            if not data_list or 'signal' not in data_list[-1]:
                time.sleep(15)
                continue

            latest_signal = data_list[-1]['signal']
            sma = data_list[-1].get('SMA', current_price)

            # 3. Unrealized PnL (net of open fee + estimated close fee)
            upnl_gross = exchange.get_unrealized_pnl(current_price)
            
            # 3b. Real-time Liquidation Check
            if exchange.check_liquidation(current_price, latest_time):
                # Remove from active trades
                with active_trades_lock:
                    if symbol in active_trades:
                        del active_trades[symbol]
                time.sleep(1)
                continue

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
            close_position = False
            close_reason = ""

            if exchange.is_in_position:
                # 4a. Check Manual Exit first (Highest Priority - ignores technical data)
                if symbol in manual_close_requests:
                    close_position = True
                    close_reason = "Manual Exit via Dashboard 🖱️ (FORCE)"
                    logger.info(f"[{symbol}] {close_reason}")
                    manual_close_requests.remove(symbol)

                # 4b. Technical Exits (Requires Indicators)
                if not close_position and 'ATR' in data_list[-1] and data_list[-1]['ATR'] is not None:
                    entry_val = exchange.position_size * exchange.entry_price
                    upnl_pct = upnl_net / entry_val if entry_val > 0 else 0
                    
                    # Retrieve current ATR for dynamic SL/TP calculation
                    current_atr = data_list[-1]['ATR']
                    atr_pct = (current_atr / current_price)
                    
                    # Default Stop Loss: 1.5% Max Net Loss
                    default_sl_pct = max(-0.015, -(atr_pct * 3.0)) 
                    
                    with symbol_states_lock:
                        if 'trailing_sl_pct' not in symbol_states[symbol]:
                            symbol_states[symbol]['trailing_sl_pct'] = default_sl_pct
                        sl_pct = symbol_states[symbol]['trailing_sl_pct']

                    # Trailing Take-Profit Logic (Professional Growth Settings)
                    if upnl_pct >= 0.004 and sl_pct < 0.001:
                        sl_pct = 0.001 # Lock in break-even + fees
                    if upnl_pct >= 0.008:
                        potential_new_sl = upnl_pct * 0.5 
                        if potential_new_sl > sl_pct: sl_pct = potential_new_sl
                    if upnl_pct >= 0.012:
                        potential_new_sl = upnl_pct * 0.70 # Tighter trail for small accounts
                        if potential_new_sl > sl_pct: sl_pct = potential_new_sl
                            
                    with symbol_states_lock:
                        symbol_states[symbol]['trailing_sl_pct'] = sl_pct

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
                        else:
                            close_reason = f"STOP LOSS HIT at {sl_pct*100:.2f}% (NET)"
                        logger.warning(f"[{symbol}] {close_reason}")

                    # --- TREND-REVERSAL EXIT ---
                    if not close_position:
                        if exchange.position_direction == 'LONG' and latest_signal == 'SHORT':
                            close_position = True
                            close_reason = "Reversal signal (LONG->SHORT)"
                        elif exchange.position_direction == 'SHORT' and latest_signal == 'LONG':
                            close_position = True
                            close_reason = "Reversal signal (SHORT->LONG)"
                        if close_position:
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

            # 4. Update Market Intelligence periodically
            signal_intel.update_market_intelligence()

            # 5. Open new position
            if not exchange.is_in_position and latest_signal in ['LONG', 'SHORT']:
                try_open_position(symbol, latest_signal, current_price, exchange, data_loader, signal_intel, notifier, latest_time)

        except Exception as e:
            logger.error(f"[{symbol}] Error: {e}")

        time.sleep(1)  # Minimal sleep for zero-delay hyperscaling (1s)


def try_open_position(symbol, side, current_price, exchange, data_loader, signal_intel, notifier, timestamp, provider=None):
    """Shared logic for opening a position from any source (technical or external)."""
    with active_trades_lock:
        # 1. Filter Check (Signal Intel)
        if not signal_intel.filter_signal(symbol, side, provider=provider, min_score=0.7):
            return False

        # 2. General Limits
        if not allow_new_trades["value"]:
            return False
            
        if not IS_UNLIMITED and len(active_trades) >= MAX_CONCURRENT_TRADES:
            if time.time() % 30 < 1:
                logger.info(f"[{symbol}] Limit reached ({len(active_trades)}). Skipping {side}.")
            return False

        if symbol in active_trades:
            return False

        # 3. Market Info for sizing
        info = data_loader.get_symbol_info(symbol)
        if not info: return False
        
        step_size = info.get('step_size', 0.001)
        min_notional = info.get('min_notional', 5.0)
        taker_fee = 0.0005 # Default

        # 4. Sizing logic for low capital ($3.00)
        current_bal = exchange.cash
        
        # If balance is low, we prioritize opening AT LEAST one trade
        # rather than splitting $3 into 15 tiny pieces ($0.20 each) which is untradable.
        min_required_margin = min_notional / 20.0 # Estimate margin for 20x
        
        if IS_UNLIMITED:
            capital_to_risk = INITIAL_CAPITAL / 10
        else:
            # Smart Sizing: Use 1/MAX or enough to meet min_notional, whichever is bigger
            partition = current_bal / MAX_CONCURRENT_TRADES
            # If partition is too small to trade, use a bigger chunk (up to 50% of balance)
            capital_to_risk = max(partition, min(current_bal * 0.5, min_required_margin * 1.2))

        if capital_to_risk < 0.10: return False

        # Calculate exact leverage needed for $3 balance
        # If balance is $3 and min_notional is $5, we need at least 1.66x leverage.
        # We target a bit above min_notional (1.1x) to avoid order rejection.
        target_notional = max(min_notional * 1.1, 5.5) # Minimum target notional
        
        # Calculate leverage: Notional / Capital
        required_lev = int(target_notional / capital_to_risk) + 1
        
        # Stay within safe limits (up to 50x for low capital is realistic, 75x is aggressive)
        actual_leverage = max(1, min(50, required_lev))
        
        # Re-calculate notional based on leverage
        target_notional = capital_to_risk * actual_leverage * 0.95 # Use 95% of power
        
        raw_size = target_notional / current_price
        size = data_loader.round_step_size(raw_size, step_size)
        
        # Final validation
        if (size * current_price) < min_notional:
            # Try one last push: increase leverage if possible
            if actual_leverage < 75:
                actual_leverage = min(75, actual_leverage + 5)
                target_notional = capital_to_risk * actual_leverage * 0.95
                raw_size = target_notional / current_price
                size = data_loader.round_step_size(raw_size, step_size)

        # Detailed logging for user visibility
        logger.info(f"[{symbol}] Low-Cap Sizing: Min Notional ${min_notional} | Using {actual_leverage}x leverage for ${capital_to_risk:.2f} capital")

        if size <= 0: return False

        # 5. Execute
        success = exchange.execute_market_order(side, size, current_price, timestamp)
        if success:
            active_trades[symbol] = datetime.utcnow()
            safe_send_message(notifier,
                f"🚀 *{symbol} — {'Elite ' if provider else ''}{side}*\n"
                f"Source: `{provider if provider else 'Technical'}`\n"
                f"Entry: `${current_price:.4f}` | Notional: `${(size*current_price):.2f}`\n"
                f"Risking: `${((size*current_price)/actual_leverage):.2f}` ({actual_leverage}x)\n"
            )
            return True
            
    return False


def external_signal_loop(signal_loader, signal_intel, data_loader, notifier, global_account):
    """Background thread that scans vip_signals.json and executes them if they pass intel filter."""
    logger.info("📡 External Signal Watcher started...")
    processed_dates = set()
    
    while bot_running["value"]:
        try:
            # Check for signals from last 5 minutes
            new_ext_signals = signal_loader.get_new_signals(window_minutes=5)
            for s in new_ext_signals:
                sig_id = f"{s['symbol']}_{s['side']}_{s['original_date']}"
                if sig_id in processed_dates: continue
                processed_dates.add(sig_id)

                symbol = s['symbol']
                provider = s['provider']
                
                # Check Signal Intelligence filter (Smart Money Score)
                if signal_intel.filter_signal(symbol, s['side'], provider=provider, min_score=0.7):
                    # For external execution, we create a temporary exchange wrapper
                    # that shares the global account.
                    temp_exchange = PaperExchange(initial_capital=global_account.initial_capital)
                    temp_exchange.shared_account = global_account
                    
                    # Fetch current price for execution
                    ticker = data_loader.get_ticker(symbol)
                    if ticker:
                        curr_p = ticker['last']
                        success = try_open_position(symbol, s['side'], curr_p, temp_exchange, data_loader, signal_intel, notifier, datetime.utcnow(), provider=provider)
                        if success:
                            logger.info(f"🏆 Successfully executed external signal for {symbol}")
            
            time.sleep(15) # Scan more frequently (15s)
        except Exception as e:
            logger.error(f"Error in external signal loop: {e}")
            time.sleep(10)


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

    global args
    # --- Initialize Components ---
    data_loader = DataLoader(exchange_id='binanceusdm', testnet=TESTNET)
    notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    ai_brain = AIBrain(GEMINI_API_KEY) if AIBrain and GEMINI_API_KEY else None
    signal_intel = SignalIntelligence(ai_brain=ai_brain)
    signal_loader = SignalLoader()
    dashboard_state["use_real_exchange"] = USE_REAL_EXCHANGE
    global_account = PaperAccount(initial_capital=INITIAL_CAPITAL, log_file=TRADE_LOG_FILE)

    # 1. Fetch top symbols dynamically
    print(f"DIAGNOSTIC: TOP_N_SYMBOLS={TOP_N_SYMBOLS}, MIN_VOLUME_USD={MIN_VOLUME_USD}, SYMBOLS_OFFSET={SYMBOLS_OFFSET}", flush=True)
    logger.info(f"Fetching top Binance Futures symbols (n={TOP_N_SYMBOLS}, offset={SYMBOLS_OFFSET})...")
    symbols = data_loader.get_top_futures_symbols(top_n=TOP_N_SYMBOLS, min_volume_usd=MIN_VOLUME_USD, offset=SYMBOLS_OFFSET)
    print(f"DIAGNOSTIC: Fetched {len(symbols)} symbols", flush=True)
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

    # 4. Start External Signal Watcher
    ext_thread = threading.Thread(
        target=external_signal_loop, 
        args=(signal_loader, signal_intel, data_loader, notifier, global_account), 
        daemon=True
    )
    ext_thread.start()

    # 4. Send startup notification
    safe_send_message(notifier,
        f"🚀 *ProfitBot Pro — Multi-Scanner Online!*\n"
        f"📡 Scanning *{len(symbols)} markets* simultaneously\n"
        f"💰 Capital: `${INITIAL_CAPITAL} USDT`\n"
        f"🛠️ Settings: `{'ON' if allow_new_trades['value'] else 'OFF'}` Entries\n"
        f"📊 Dashboard: `http://localhost:{DASHBOARD_PORT}`"
    )

    # 5. Start Scanners
    symbol_threads = []
    
    # Initialize Master Real Exchange Client (to avoid rate limits)
    master_client = None
    if USE_REAL_EXCHANGE:
        try:
            if EXCHANGE_NAME == "bybit" and BYBIT_API_KEY and BYBIT_API_SECRET:
                import ccxt
                master_client = ccxt.bybit({
                    'apiKey': BYBIT_API_KEY,
                    'secret': BYBIT_API_SECRET,
                    'enableRateLimit': True,
                    'options': {
                        'defaultType': 'linear',
                        'adjustForTimeDifference': True,
                        'recvWindow': 10000,
                    }
                })
                if TESTNET: master_client.set_sandbox_mode(True)
                master_client.load_markets()
                logger.info(f"✅ Master BYBIT client initialized.")
            elif EXCHANGE_NAME == "mexc" and MEXC_API_KEY and MEXC_API_SECRET:
                import ccxt
                master_client = ccxt.mexc({
                    'apiKey': MEXC_API_KEY,
                    'secret': MEXC_API_SECRET,
                    'enableRateLimit': True,
                    'options': {
                        'defaultType': 'swap',
                        'adjustForTimeDifference': True,
                        'recvWindow': 10000,
                    }
                })
                if TESTNET:
                    master_client.urls['api']['swap'] = 'https://futures.testnet.mexc.com/api/v1'
                    master_client.urls['api']['public'] = 'https://futures.testnet.mexc.com/api/v1'
                    master_client.urls['api']['private'] = 'https://futures.testnet.mexc.com/api/v1'
                master_client.load_markets()
                logger.info(f"✅ Master MEXC client initialized.")
        except Exception as e:
            logger.error(f"❌ Failed to initialize master exchange client: {e}")

    logger.info(f"Starting scanners for {len(symbols)} symbols using strategy {args.strategy}...")
    for symbol in symbols:
        def thread_wrapper(sym, current_args, m_client):
            try:
                # Initialize per-thread components
                if current_args.strategy == "rsd":
                    strat = RSDTraderStrategy(leverage=LEVERAGE)
                elif current_args.strategy == "elite":
                    strat = EliteScalperStrategy(leverage=LEVERAGE)
                elif current_args.strategy == "scalper70":
                    strat = Scalper70Strategy(leverage=LEVERAGE)
                elif current_args.strategy == "hyper25":
                    strat = HyperScalper25Strategy(leverage=LEVERAGE)
                elif current_args.strategy == "diamond":
                    strat = DiamondSniperStrategy(leverage=LEVERAGE)
                else:
                    strat = SmartMoneyStrategy(leverage=LEVERAGE)
                
                if USE_REAL_EXCHANGE:
                    if EXCHANGE_NAME == "bybit" and BYBIT_API_KEY and BYBIT_API_SECRET:
                        exch = BybitExchange(
                            api_key=BYBIT_API_KEY, 
                            api_secret=BYBIT_API_SECRET, 
                            testnet=TESTNET,
                            symbol=sym,
                            client=m_client
                        )
                    elif EXCHANGE_NAME == "mexc" and MEXC_API_KEY and MEXC_API_SECRET:
                        exch = MEXCExchange(
                            api_key=MEXC_API_KEY, 
                            api_secret=MEXC_API_SECRET, 
                            testnet=TESTNET,
                            symbol=sym,
                            client=m_client
                        )
                    elif EXCHANGE_NAME == "binance" and BINANCE_API_KEY and BINANCE_API_SECRET:
                        ccxt_sym = f"{sym[:-4]}/{sym[-4:]}" if sym.endswith('USDT') else sym
                        exch = BinanceExchange(
                            api_key=BINANCE_API_KEY, 
                            api_secret=BINANCE_API_SECRET, 
                            testnet=TESTNET,
                            symbol=ccxt_sym
                        )
                    else:
                        logger.warning(f"No API keys for {EXCHANGE_NAME.upper()}. Using Paper Mode.")
                        exch = PaperExchange(initial_capital=INITIAL_CAPITAL, taker_fee=BINANCE_FEE)
                        exch.leverage = LEVERAGE
                else:
                    exch = PaperExchange(initial_capital=INITIAL_CAPITAL, taker_fee=BINANCE_FEE)
                    exch.leverage = LEVERAGE
                
                exch.shared_account = global_account
                # exch.symbol = sym # Removed to prevent overwriting exchange-specific symbol formatting

                # Resume state if this symbol was in an open trade
                with active_trades_lock:
                    if sym in active_trades:
                        for trade in reversed(global_account.trade_history):
                            if trade.get('symbol') == sym and trade.get('action') in ['LONG', 'SHORT']:
                                exch.position_direction = trade['action']
                                exch.position_size = trade['size']
                                exch.entry_price = trade['price']
                                exch.entry_time = trade.get('timestamp')
                                # Restore margin and fees for PaperExchange
                                if hasattr(exch, 'entry_margin'):
                                    exch.entry_margin = trade.get('margin_locked', 0.0)
                                if hasattr(exch, 'entry_fee_paid'):
                                    exch.entry_fee_paid = trade.get('fee', 0.0)
                                break

                scan_symbol(sym, data_loader, strat, exch, notifier, signal_intel)
            except Exception as e:
                logger.error(f"Thread for {sym} failed: {e}")

        t = threading.Thread(
            target=thread_wrapper,
            args=(symbol, args, master_client),
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
            dashboard_state["strategy_name"] = args.strategy

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
