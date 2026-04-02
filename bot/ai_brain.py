import google.generativeai as genai
import logging
import os
import requests
import json

logger = logging.getLogger("AIBrain")

# Conversation memory stored per chat_id
_conversation_history = {}

class AIBrain:
    def __init__(self, api_key=None, provider="gemini", deepseek_key=None):
        self.api_key = api_key
        self.deepseek_key = deepseek_key or os.environ.get("DEEPSEEK_API_KEY")
        self.provider = os.environ.get("AI_PROVIDER", provider).lower()
        self.model = None

        if self.provider == "gemini" and self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel("models/gemini-3-flash-preview")
                logger.info("AI Brain initialized with gemini-3-flash-preview")
            except Exception:
                try:
                    self.model = genai.GenerativeModel("models/gemini-2.0-flash")
                    logger.info("AI Brain initialized with gemini-2.0-flash fallback")
                except Exception as e:
                    logger.error(f"AI Brain (Gemini) init failed: {e}")
                    self.model = None
        elif self.provider == "deepseek" and self.deepseek_key:
            logger.info("AI Brain initialized with DeepSeek")
        else:
            logger.warning(f"AI Brain: No valid provider/key found (Provider: {self.provider})")

    def generate_reply(self, message, context="", chat_id="default"):
        """
        Generate an AI response using conversation history for memory.
        Context is injected silently so the AI knows live trading state.
        """
        # Build the full prompt with system instructions
        system_preamble = (
            "You are 'ProfitBot Pro', an advanced AI Trading Assistant.\n"
            "Personality: Friendly, conversational, highly intelligent. You want the user to succeed.\n"
            "You manage a small paper trading account and know all about your strategy: Smart Money (200 EMA, MACD, RSI, Bollinger Bands) with ATR-based trailing stop losses.\n"
            "You receive a live portfolio snapshot with every message. Use it naturally to answer questions about trades and PnL without mentioning the snapshot exists.\n"
            "Be concise, warm, and use emojis when appropriate.\n"
        )

        # Initialize chat history for this user if not already done
        if chat_id not in _conversation_history:
            _conversation_history[chat_id] = []

        history = _conversation_history[chat_id]
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

        reply = None
        if self.provider == "gemini" and self.model:
            try:
                response = self.model.generate_content(full_prompt)
                reply = response.text.strip()
            except Exception as e:
                logger.error(f"Gemini Exception: {e}")
        elif self.provider == "deepseek" and self.deepseek_key:
            reply = self._call_deepseek(full_prompt)

        if reply:
            # Update history
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": reply})
            _conversation_history[chat_id] = history
            return reply

        return None

    def generate_response(self, prompt, context_title="Analysis"):
        """Simple wrapper for generic AI processing."""
        if self.provider == "gemini" and self.model:
            try:
                response = self.model.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                logger.error(f"Gemini Response Error: {e}")
        elif self.provider == "deepseek" and self.deepseek_key:
            return self._call_deepseek(prompt)
        return ""

    def _call_deepseek(self, prompt, system_prompt=None):
        """Helper to call DeepSeek API using requests."""
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.deepseek_key}"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        data = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        except Exception as e:
            logger.error(f"DeepSeek API Error: {e}")
            return ""
