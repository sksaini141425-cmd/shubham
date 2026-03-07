from bot.notifier import TelegramNotifier

# CONFIG - Same as main.py
TELEGRAM_BOT_TOKEN = '8774183137:AAF2O1EFz_2XjtF2LHA3ALmIuRvuTEBLtmM'
TELEGRAM_CHAT_ID = 8506152391

def send_demo():
    notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    
    # 1. Entry Demo
    msg_entry = (
        f"🔔 *New LONG Trade!*\n"
        f"Symbol: `BTCUSDT`\n"
        f"Notional: `$131.00` | Lev: `44x`\n"
        f"Price: `$62450.5`"
    )
    notifier.send_message(msg_entry)
    
    # 2. Exit Demo (Detailed)
    msg_exit = (
        f"✅ *Trade Closed (DEMO REPORT)*\n"
        f"Entry: `$62450.5`\n"
        f"Exit: `$62762.7`\n"
        f"Net PnL: `+$0.52` (+17.20%)\n"
        f"New Balance: `$3.52`"
    )
    notifier.send_message(msg_exit)
    
    print("Demo messages sent to Telegram!")

if __name__ == "__main__":
    send_demo()
