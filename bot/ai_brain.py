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

    def generate_reply(self, message, context=""):
        """
        Generate a High-Intelligence AI response (Claude-style).
        """
        if not self.model:
            return None
        
        system_prompt = (
            "You are 'ProfitBot Pro', an advanced AI Trading Assistant and Market Analyst.\n"
            "Your personality: Highly helpful, extremely responsive, professional, and educational. You want the user to succeed.\n"
            "Your job: Help the user understand their account, the market, and trading concepts. You are managing a $3 paper trading account aiming for $10.\n\n"
            "--- TRADE LOGIC & CONTEXT ---\n"
            "Current Strategy: 'Smart Money' Multi-Indicator Confirmation.\n"
            "- Trend: 200 EMA (Exponential Moving Average)\n"
            "- Momentum: MACD (Moving Average Convergence Divergence)\n"
            "- Overbought/Oversold: RSI (Relative Strength Index)\n"
            "- Volatility: Bollinger Bands\n"
            "Risk Management: Dynamic ATR-based Stop Loss & Trailing Take-Profits to let winners run.\n"
            f"Current Context: {context}\n\n"
            "--- USER INTERACTION ---\n"
            f"User just sent: '{message}'\n\n"
            "Reply as ProfitBot Pro. Be incredibly helpful and answer their question clearly. "
            "If they ask about the strategy, explain it simply. If they ask for crypto advice, analyze the current context. "
            "Use bullet points for readability. Use *bold* for emphasis. Be the ultimate trading assistant."
        )
        
        try:
            response = self.model.generate_content(system_prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"AI Brain Exception: {str(e)}")
            return None # Fail silently to keep user experience clean
