import threading

# Shared state between main bot loop and dashboard
dashboard_state = {
    "bot_status": "STARTING",
    "entries_allowed": True,
    "last_update": "",
    "symbols": {},
    "profile_name": "default",
    "log_file": "trade_log.json",
    "initial_capital": 3.00
}

manual_close_requests = set()
manual_open_requests = {} # symbol -> side (LONG/SHORT)
set_entries_state = [None]  # None = no request, True = enable, False = disable
clear_history_requested = [False]
panic_close_all_requested = [False]
reset_account_requested = [False]
