import requests
import logging

logger = logging.getLogger("TelegramNotifier")

class TelegramNotifier:
    def __init__(self, bot_token=None, chat_id=None):
        """
        Initialize with Telegram Bot token and Chat ID.
        Get yours via @BotFather and @userinfobot on Telegram.
        """
        self.token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage" if self.token else None

    def send_message(self, text):
        if not self.token or not self.chat_id:
            logger.warning("Telegram credentials not set. Skipping message.")
            return False
        
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        
        try:
            # Note: verify=False is a workaround for local SSL protocol errors
            response = requests.post(self.base_url, json=payload, timeout=10, verify=False)
            if response.status_code == 200:
                logger.info(f"Telegram alert sent: {text[:30]}...")
                return True
            else:
                logger.error(f"Failed to send Telegram: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Telegram Error: {e}")
            return False

    def get_updates(self, offset=None):
        """
        Poll Telegram for new messages.
        """
        if not self.token: return []
        url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        params = {"timeout": 10, "offset": offset}
        try:
            # verify=False is used to bypass local SSL handshake failures
            response = requests.get(url, params=params, timeout=15, verify=False)
            if response.status_code == 200:
                return response.json().get("result", [])
            return []
        except Exception as e:
            logger.error(f"Poll Error: {e}")
            return []
