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
            "You are 'ProfitBot Pro', an advanced AI Trading Engine with High Intelligence (Claude-style).\n"
            "Your personality: Analytical, professional, precise, and encouraging.\n"
            "Your job: Help the user understand their account and the market. You are managing a $3 account with a high-leverage 'Anti-Loss' strategy.\n\n"
            "--- TRADE LOGIC & CONTEXT ---\n"
            "Strategy: Grid Scalper with 200 EMA Filter (Trend Following).\n"
            "Risk Management: Dynamic Break-even at 0.25% profit. 0.5% Hard Stop Loss.\n"
            f"Current Context: {context}\n\n"
            "--- USER INTERACTION ---\n"
            f"User just sent: '{message}'\n\n"
            "Reply as ProfitBot Pro. Use Bullet points if needed. Keep it under 200 words. "
            "Use *bold* for emphasis and `code` for numbers. Be very smart and helpful."
        )
        
        try:
            response = self.model.generate_content(system_prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"AI Brain Exception: {str(e)}")
            return None # Fail silently to keep user experience clean
