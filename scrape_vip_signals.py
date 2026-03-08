import asyncio
from telethon import TelegramClient
from datetime import datetime, timedelta, timezone
import json
import logging

logging.basicConfig(level=logging.WARNING)

api_id = 39875378
api_hash = '92717c7a488899c00f45bcc53f2a8b86'
session_name = 'userbot_session'

# Target group names (fuzzier to catch emojis and weird characters)
TARGET_GROUPS = [
    "David", 
    "PERFECT TRADER",
    "RSD GOLD",
    "O'Brien Crypto",
    "Жак",
    "Crypto Master",
    "Ванга",
    "Profit_Flux",
    "tTrade",
    "Profit Trade & Analytics",
    "Профессор Альткоин",
    "Alex Fisher",
    "Мадина",
    "Trade in Coins",
    "Nargiza Trade",
    "GG Invest",
    "XAUUSD SIGNAL SQUAD XPERTS",
    "Magic Trader",
    "Gold Global"
]

async def main():
    print("-------------------------------------------------")
    print("📱 Logging into Telegram... Please follow the prompts!")
    print("You will need to enter your phone number (+1...)")
    print("and the login code Telegram sends you.")
    print("-------------------------------------------------")
    
    async with TelegramClient(session_name, api_id, api_hash) as client:
        print("\n✅ Successfully logged in! Finding your VIP groups...")
        
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(days=7)
        
        scraped_signals = []
        found_groups = 0
        
        async for dialog in client.iter_dialogs():
            name = dialog.name
            
            # Match group names
            if any(target.lower() in name.lower() for target in TARGET_GROUPS):
                found_groups += 1
                messages_found = 0
                print(f"📥 Found: '{name}' | Scraping last 24h...")
                
                # Fetch new to old
                async for msg in client.iter_messages(dialog):
                    if msg.date < start_time:
                        break # Stopped reached 24 hour mark
                    
                    if msg.text:
                        text_lower = msg.text.lower()
                        # Filter to save memory: MUST contain signal-like words
                        if any(k in text_lower for k in ['buy', 'sell', 'tp', 'sl', 'entry', 'risk', 'profit']):
                            scraped_signals.append({
                                'group': name,
                                'date': msg.date.isoformat(),
                                'text': msg.text
                            })
                            messages_found += 1
                
                print(f"   -> Saved {messages_found} signals from '{name}'")
        
        # Save to JSON for the AI to analyze
        import os
        filename = os.path.join(os.getcwd(), 'vip_signals.json')
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(scraped_signals, f, indent=4, ensure_ascii=False)
            
        print("\n=================================================")
        print(f"🎉 DONE! Successfully scraped {len(scraped_signals)} signals!")
        print(f"Data saved to: {filename}")
        print("Please tell the AI assistant you are finished.")
        print("=================================================")

if __name__ == '__main__':
    asyncio.run(main())
