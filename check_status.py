import sys
import os
try:
    import google.generativeai
    from bot.data_loader import DataLoader
    from bot.strategy import SmartMoneyStrategy, RSDTraderStrategy
    from bot.signal_loader import SignalLoader
    from bot.binance_exchange import BinanceExchange
    from bot.notifier import TelegramNotifier
    from bot.ai_brain import AIBrain
    from bot.signal_intelligence import SignalIntelligence
    print("READY")
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
