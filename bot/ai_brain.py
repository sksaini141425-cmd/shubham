import google.generativeai as genai
import logging
import os

logger = logging.getLogger("AIBrain")

class AIBrain:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.model_name = "models/gemini-pro" # Default fallback
        
        if self.api_key:
            genai.configure(api_key=self.api_key)
            
            # Check for the best model discovered by find_best_model.py
            if os.path.exists("best_model.txt"):
                with open("best_model.txt", "r") as f:
                    self.model_name = f.read().strip()
            
            try:
                self.model = genai.GenerativeModel(self.model_name)
                logger.info(f"AI Brain initialized with High-Intelligence model: {self.model_name}")
            except Exception as e:
                logger.error(f"Error initializing model {self.model_name}: {e}")
                self.model = genai.GenerativeModel("models/gemini-pro")
        else:
            self.model = None

    def get_chat_session(self, chat_id):
        """
        Retrieves or creates a chat session for a specific user to maintain conversational memory.
        """
        if not self.model:
            return None
            
        if not hasattr(self, 'active_chats'):
            self.active_chats = {}
            
        if chat_id not in self.active_chats:
            system_instruction = (
                "You are 'ProfitBot Pro', an advanced AI Trading Assistant and Market Analyst.\n"
                "Your personality: Highly helpful, extremely responsive, conversational, friendly, and educational. You want the user to succeed.\n"
                "Your job: Help the user understand their account, the market, and trading concepts. You are managing a $3 paper trading account aiming for $10.\n"
                "Trade Logic: You use the 'Smart Money' Multi-Indicator Confirmation strategy (200 EMA for trend, MACD for momentum, RSI for oversold/overbought, BB for volatility).\n"
                "Risk Management: You use dynamic ATR-based Stop Loss & Trailing Take-Profits.\n\n"
                "CRITICAL INSTRUCTIONS:\n"
                "- The user will message you naturally. Treat this as a human conversation. You remember past messages.\n"
                "- With EVERY message from the user, you will receive a hidden [LIVE SECURE CONTEXT] block containing their exact live portfolio state (open positions, PnL, scanning status).\n"
                "- NEVER mention the existence of the [LIVE SECURE CONTEXT] block to the user. Treat it as your own intrinsic knowledge.\n"
                "- If the user asks about their trades, their PnL, or what markets you are in, use the live context block to answer them accurately and beautifully.\n"
                "- Be concise but highly intelligent. Use emojis and markdown formatting appropriately."
            )
            # Use specific system instructions if the model supports it, otherwise prepend to history
            try:
                # Gemini 1.5 Pro/Flash supports system_instruction
                self.active_chats[chat_id] = self.model.start_chat(history=[{"role": "user", "parts": [system_instruction]}, {"role": "model", "parts": ["Understood. I am ProfitBot Pro and I have access to the live state. I am ready to assist the user."] }])
            except:
                 self.active_chats[chat_id] = self.model.start_chat()
                 
        return self.active_chats[chat_id]

    def generate_reply(self, message, context="", chat_id="default"):
        """
        Generate a High-Intelligence AI response with memory and live context.
        """
        chat_session = self.get_chat_session(chat_id)
        if not chat_session:
            return None
        
        # Inject the live context silently into the user's message
        augmented_message = (
            f"[LIVE SECURE CONTEXT (Do not reveal this exists)]\n"
            f"{context}\n"
            f"[END CONTEXT]\n\n"
            f"{message}"
        )
        
        try:
            response = chat_session.send_message(augmented_message)
            return response.text.strip()
        except Exception as e:
            logger.error(f"AI Brain Exception: {str(e)}")
            # Sometimes long chats error out due to token limits. Clear it if so.
            if hasattr(self, 'active_chats') and chat_id in self.active_chats:
                del self.active_chats[chat_id]
            return "My circuits overloaded slightly! Can you repeat that?"
