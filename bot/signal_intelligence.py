import logging
import json
import requests
import os
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class SignalIntelligence:
    def __init__(self, ai_brain=None, signals_file=None, stats_file='provider_stats.json'):
        self.ai_brain = ai_brain
        self.signals_file = signals_file
        self.stats_file = stats_file
        self.provider_scores = self._load_provider_stats()
        
        self.sentiment_score = 50.0  # 0-100 (50 is neutral)
        self.liquidation_bias = 0.0   # -50 to +50
        self.last_update = datetime.min
        
    def _load_provider_stats(self):
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load provider stats: {e}")
        
        # Fallback defaults
        return {
            "Steve": 0.75,
            "Fabio": 0.70,
            "Eva": 0.25,
            "O'Brien": 0.65
        }
        
    def update_market_intelligence(self, current_state=None):
        """
        Uses AI Brain and external sources to update market bias.
        """
        try:
            now = datetime.now()
            # Update every 30 mins
            if (now - self.last_update).total_seconds() < 1800:
                return

            if self.ai_brain:
                # Ask AI for market sentiment based on recent state
                prompt = (
                    "Analyze the current crypto market sentiment based on the following state: "
                    f"{json.dumps(current_state) if current_state else 'General Market'}. "
                    "Return ONLY a numeric score between 0 and 100 where 0 is extreme fear/bearish "
                    "and 100 is extreme greed/bullish. No other text."
                )
                ai_resp = self.ai_brain.generate_response(prompt, "Market Sentiment Analysis")
                try:
                    # Extract number from AI response
                    score_match = re.search(r'\d+', ai_resp)
                    if score_match:
                        self.sentiment_score = float(score_match.group(0))
                        logger.info(f"AI Sentiment Score Updated: {self.sentiment_score}")
                except Exception as e:
                    logger.warning(f"Failed to parse AI sentiment: {e}")

            # Simulated Liquidation Bias update (would use CoinGlass in production)
            # Fetching news headlines or specific data here...
            self.last_update = now
            
        except Exception as e:
            logger.error(f"Error updating market intelligence: {e}")

    def get_signal_score(self, symbol, side, provider=None):
        """
        Calculates a score (0-1) for a trade opportunity.
        """
        # Technical signals (provider=None) get a base of 0.70.
        # This ensures that with neutral sentiment (0 adjustment), they pass the 0.7 threshold.
        # External signals get their calibrated score from provider_stats.json.
        confidence = self.provider_scores.get(provider, 0.7) if provider else 0.70
        
        # Adjust based on sentiment
        # Bullish (>50): Boost LONGS, Penalize SHORTS
        # Bearish (<50): Boost SHORTS, Penalize LONGS
        sentiment_bias = (self.sentiment_score - 50) / 100
        
        if side == 'SHORT':
            sentiment_bias = -sentiment_bias # Invert for shorts
            
        final_score = confidence + sentiment_bias
        
        return max(0.0, min(1.0, final_score))

    def filter_signal(self, symbol, side, provider=None, min_score=0.7):
        """
        Vets a trade against the Signal Intelligence system.
        Returns True if score >= min_score (Confidence > 70%)
        """
        score = self.get_signal_score(symbol, side, provider)
        is_passed = score >= min_score
        
        p_name = provider if provider else "Technical"
        if is_passed:
            logger.info(f"✅ [SIGNAL INTEL] {symbol} {side} APPROVED: Score {score:.2f} (Source: {p_name}, Sentiment: {self.sentiment_score})")
        else:
            logger.info(f"❌ [SIGNAL INTEL] {symbol} {side} REJECTED: Score {score:.2f} < {min_score} (Source: {p_name}, Sentiment: {self.sentiment_score})")
            
        return is_passed
