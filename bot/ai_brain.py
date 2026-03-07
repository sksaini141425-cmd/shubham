import google.generativeai as genai
import logging
import os

logger = logging.getLogger("AIBrain")

# Conversation memory stored per chat_id
_conversation_history = {}

class AIBrain:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.model = None

        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel("gemini-1.5-flash")
                logger.info("AI Brain initialized with gemini-1.5-flash")
            except Exception:
                try:
                    self.model = genai.GenerativeModel("models/gemini-pro")
                    logger.info("AI Brain initialized with gemini-pro fallback")
                except Exception as e:
                    logger.error(f"AI Brain init failed: {e}")
                    self.model = None

    def generate_reply(self, message, context="", chat_id="default"):
        """
        Generate an AI response using conversation history for memory.
        Context is injected silently so the AI knows live trading state.
        """
        if not self.model:
            return None

        # Initialize chat history for this user if not already done
        if chat_id not in _conversation_history:
            _conversation_history[chat_id] = []

        history = _conversation_history[chat_id]

        # Build the full prompt with system instructions on the first message
        system_preamble = (
            "You are 'ProfitBot Pro', an advanced AI Trading Assistant.\n"
            "Personality: Friendly, conversational, highly intelligent. You want the user to succeed.\n"
            "You manage a small paper trading account and know all about your strategy: Smart Money (200 EMA, MACD, RSI, Bollinger Bands) with ATR-based trailing stop losses.\n"
            "You receive a live portfolio snapshot with every message. Use it naturally to answer questions about trades and PnL without mentioning the snapshot exists.\n"
            "Be concise, warm, and use emojis when appropriate.\n"
        )

        # Build the text prompt including conversation history
        history_text = ""
        for turn in history[-10:]:  # Keep last 10 turns to avoid token limit
            role = "User" if turn["role"] == "user" else "Assistant"
            history_text += f"{role}: {turn['content']}\n"

        full_prompt = (
            f"{system_preamble}\n"
            f"--- LIVE PORTFOLIO STATE ---\n{context}\n---\n\n"
            f"Previous conversation:\n{history_text}\n"
            f"User: {message}\n"
            f"Assistant:"
        )

        try:
            response = self.model.generate_content(full_prompt)
            reply = response.text.strip()

            # Update history
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": reply})
            _conversation_history[chat_id] = history

            return reply

        except Exception as e:
            logger.error(f"AI Brain Exception: {type(e).__name__}: {str(e)}")
            return None
