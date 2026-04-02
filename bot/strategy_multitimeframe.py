"""
Multi-Timeframe Scalper Strategy
Uses multiple timeframes for trend confirmation and volatility analysis.
Optimized for BTCUSDT with dynamic risk management.
"""
import logging
from datetime import datetime, timezone
from .strategy import calculate_ema, calculate_adx, calculate_stochastic_rsi, calculate_atr, calculate_rsi
from .multitimeframe_data_loader import MultiTimeframeDataLoader

logger = logging.getLogger(__name__)


class MultiTimeframeScalperStrategy:
    """
    Multi-Timeframe Scalper Strategy
    Requires 1h/4h/1d trend alignment, 15m ADX confirmation,
    1m Stoch RSI entries, and 5m ATR-based exits.
    Optionally uses DeepSeek for AI trade validation.
    """

    def __init__(self, leverage=3, signal_intel=None):
        self.initial_capital = 5.0
        self.leverage = min(max(int(leverage or 3), 1), 5)
        self.risk_per_trade = 0.02
        
        # Initialize multi-timeframe data loader
        self.mt_loader = MultiTimeframeDataLoader()
        self.signal_intel = signal_intel
        
        self.trend_timeframes = ["1h", "4h"] # Removed 1d for more frequent entries
        self.entry_timeframe = "1m"
        self.volatility_timeframe = "15m"
        self.atr_timeframe = "5m"

        self.ema_period = 20
        self.trend_condition = "price_above_ema"

        self.adx_period = 14
        self.adx_threshold = 20 # Lowered from 25 to capture more trends

        self.stoch_rsi = {
            "period": 14,
            "smooth_k": 3,
            "smooth_d": 3,
            "oversold": 20,
            "overbought": 80,
        }

        self.atr_period = 14
        self.stop_loss_atr_mult = 2.0
        self.take_profit_atr_mult = 4.0

        self.order_type = "limit"
        self.exchange = "binance_futures"
        self.pair = None # Make dynamic to scan all symbols

        self.avoid_hours = []  # Empty for paper testing (originally [12, 13, 14])
        
        logger.info(f"Multi-Timeframe Scalper initialized with {self.leverage}x leverage")
        logger.info(f"Timeframes: Trend {self.trend_timeframes}, Entry {self.entry_timeframe}, Volatility {self.volatility_timeframe}")

        self.use_strategy_position_sizing = True
        self.use_strategy_position_management = True
        self.max_holding_hours = 4
        self.min_notional = 5.0 # Lowered from 10.0 for smaller accounts ($3 balance)

        self.required_history = {
            self.entry_timeframe: 250,
            self.atr_timeframe: max(80, self.atr_period * 6),
            self.volatility_timeframe: max(80, self.adx_period * 6),
            "1h": max(80, self.ema_period * 4),
            "4h": max(80, self.ema_period * 4),
        }

        logger.info(
            "Multi-Timeframe Scalper initialized: %sx leverage, pair=%s",
            self.leverage,
            self.pair,
        )

    def fetch_market_data(self, symbol, data_loader):
        """Fetch all required timeframes for live scanning."""
        target_symbol = self.pair or symbol
        timeframes = {}
        for timeframe, limit in self.required_history.items():
            candles = data_loader.fetch_ohlcv(target_symbol, timeframe=timeframe, limit=limit)
            if not candles:
                logger.warning("[%s] Missing %s candles for multi-timeframe scan", target_symbol, timeframe)
                return None
            timeframes[timeframe] = [dict(c) for c in candles]

        return {
            "symbol": target_symbol,
            "timeframes": timeframes,
        }

    def calculate_indicators(self, market_data):
        """Calculate indicators across all required timeframes."""
        normalized = self._normalize_market_data(market_data)
        if not normalized:
            return []

        entry_data = normalized["timeframes"].get(self.entry_timeframe, [])
        if not entry_data:
            return []

        atr_data = normalized["timeframes"].get(self.atr_timeframe, [])
        volatility_data = normalized["timeframes"].get(self.volatility_timeframe, [])
        trend_context = {}

        self._annotate_entry_indicators(entry_data)
        latest_atr = self._annotate_atr(atr_data)
        latest_adx = self._annotate_adx(volatility_data)

        for timeframe in self.trend_timeframes:
            trend_context[timeframe] = self._annotate_trend(normalized["timeframes"].get(timeframe, []), timeframe)

        latest = entry_data[-1]
        latest["ATR"] = latest_atr
        latest["ADX"] = latest_adx
        latest["ENTRY_TIMEFRAME"] = self.entry_timeframe
        latest["VOLATILITY_TIMEFRAME"] = self.volatility_timeframe
        latest["ATR_TIMEFRAME"] = self.atr_timeframe
        latest["ORDER_TYPE"] = self.order_type
        latest["PAIR"] = normalized.get("symbol", self.pair)

        bullish_alignment = all(ctx["trend"] == "UP" for ctx in trend_context.values())
        bearish_alignment = all(ctx["trend"] == "DOWN" for ctx in trend_context.values())

        latest["BULLISH_ALIGNMENT"] = bullish_alignment
        latest["BEARISH_ALIGNMENT"] = bearish_alignment
        latest["TREND_ALIGNMENT"] = (
            "BULLISH" if bullish_alignment else "BEARISH" if bearish_alignment else "MIXED"
        )

        for timeframe, context in trend_context.items():
            suffix = timeframe.upper()
            latest[f"TREND_{suffix}"] = context["trend"]
            latest[f"PRICE_{suffix}"] = context["price"]
            latest[f"EMA_{self.ema_period}_{suffix}"] = context["ema"]

        return entry_data

    def generate_signals(self, data_list):
        """Generate entry signals from aligned multi-timeframe context."""
        if not data_list or len(data_list) < max(self.stoch_rsi["period"] * 3, 50):
            return data_list

        latest = data_list[-1]
        latest["signal"] = "NONE"
        latest["signal_strength"] = 0

        candle_time = self._ensure_utc_datetime(latest.get("timestamp"))
        if candle_time.hour in self.avoid_hours:
            latest["signal_reason"] = f"Session filter active ({candle_time.hour:02d}:00 UTC)"
            return data_list

        adx = latest.get("ADX")
        stoch_k = latest.get("STOCH_RSI_K")
        stoch_d = latest.get("STOCH_RSI_D")
        bullish_alignment = latest.get("BULLISH_ALIGNMENT", False)
        bearish_alignment = latest.get("BEARISH_ALIGNMENT", False)

        volatility_ok = adx is not None and adx >= self.adx_threshold
        long_trigger = (
            stoch_k is not None
            and stoch_d is not None
            and stoch_k <= self.stoch_rsi["oversold"]
            and stoch_k >= stoch_d
        )
        short_trigger = (
            stoch_k is not None
            and stoch_d is not None
            and stoch_k >= self.stoch_rsi["overbought"]
            and stoch_k <= stoch_d
        )

        reasons = []
        if bullish_alignment and volatility_ok and long_trigger:
            latest["signal"] = "LONG"
            latest["signal_strength"] = 4
            reasons.append("1h/4h/1d trend aligned bullish")
            reasons.append(f"15m ADX {adx:.2f} >= {self.adx_threshold}")
            reasons.append(
                f"1m Stoch RSI K/D {stoch_k:.2f}/{stoch_d:.2f} in oversold zone"
            )
        elif bearish_alignment and volatility_ok and short_trigger:
            latest["signal"] = "SHORT"
            latest["signal_strength"] = 4
            reasons.append("1h/4h/1d trend aligned bearish")
            reasons.append(f"15m ADX {adx:.2f} >= {self.adx_threshold}")
            reasons.append(
                f"1m Stoch RSI K/D {stoch_k:.2f}/{stoch_d:.2f} in overbought zone"
            )
        else:
            if not bullish_alignment and not bearish_alignment:
                reasons.append("Trend alignment missing across 1h/4h/1d")
            if not volatility_ok:
                adx_text = f"{adx:.2f}" if adx is not None else "n/a"
                reasons.append(f"15m ADX below threshold ({adx_text} < {self.adx_threshold})")
            if not long_trigger and not short_trigger:
                if stoch_k is None or stoch_d is None:
                    reasons.append("1m Stoch RSI not ready")
                else:
                    reasons.append(f"1m Stoch RSI K/D {stoch_k:.2f}/{stoch_d:.2f} not in trigger zone")

        latest["signal_reason"] = ", ".join(reasons) if reasons else "No setup"
        latest["trend"] = latest["TREND_ALIGNMENT"]
        latest["volatility"] = "HIGH" if volatility_ok else "LOW"

        # AI VALIDATION (DeepSeek Integration)
        if latest["signal"] != "NONE" and self.signal_intel and self.signal_intel.ai_brain:
            logger.info(f"[{latest.get('PAIR')}] 🤖 Validating {latest['signal']} with AI...")
            
            # Prep context for AI
            market_state = {
                "latest": latest,
                "trends": {tf: latest.get(f"TREND_{tf.upper()}") for tf in self.trend_timeframes}
            }
            
            ai_decision = self.signal_intel.get_deepseek_trade_analysis(latest.get('PAIR'), market_state)
            
            if ai_decision:
                ai_signal = ai_decision.get("signal", "hold").upper()
                ai_confidence = ai_decision.get("confidence", 0)
                
                if ai_signal == "ENTRY" and ai_confidence >= 0.7:
                    logger.info(f"[{latest.get('PAIR')}] ✅ AI APPROVED: {ai_decision.get('justification')}")
                    latest["ai_validation"] = "APPROVED"
                    latest["ai_justification"] = ai_decision.get("justification")
                    # Optionally override signal with AI side if different
                    latest["signal"] = ai_decision.get("side", latest["signal"]).upper()
                else:
                    logger.info(f"[{latest.get('PAIR')}] ❌ AI REJECTED: {ai_decision.get('justification')} (Confidence: {ai_confidence})")
                    latest["signal"] = "NONE"
                    latest["signal_reason"] = f"AI Rejected: {ai_decision.get('justification')}"
                    latest["ai_validation"] = "REJECTED"

        return data_list

    def calculate_position_size(self, account_balance, entry_price, stop_loss_price):
        """Risk 2% of equity while respecting fixed leverage."""
        if account_balance <= 0 or entry_price <= 0 or stop_loss_price <= 0:
            return 0.0

        # Calculate technical risk size (2% of equity)
        stop_distance = abs(entry_price - stop_loss_price)
        if stop_distance <= 0: return 0.0
        
        risk_amount = account_balance * self.risk_per_trade
        size_by_risk = risk_amount / stop_distance

        # Calculate max buying power (Leverage limit)
        # For small accounts (<$10), we allow up to 10x leverage to hit min notional
        effective_leverage = self.leverage
        if account_balance < 10.0:
            effective_leverage = max(effective_leverage, 10)
            
        max_notional = account_balance * effective_leverage
        max_size_by_leverage = max_notional / entry_price if entry_price > 0 else 0.0
        
        # Start with the risk-based size
        position_size = size_by_risk
        
        # ENSURE MINIMUM NOTIONAL (The "Bumping" Logic)
        min_size = self.min_notional / entry_price
        if position_size < min_size:
            # If we are below minimum, we MUST use the minimum size to trade
            if min_size <= max_size_by_leverage:
                position_size = min_size
            else:
                # If even 10x leverage isn't enough to hit $5.00, we can't trade
                return 0.0

        # Final check against hard cap
        position_size = min(position_size, max_size_by_leverage)

        return round(position_size, 6)

    def calculate_stop_loss(self, entry_price, side, atr=None):
        """ATR-based stop with a fixed-price fallback."""
        if entry_price <= 0:
            return None

        if atr is not None and atr > 0:
            distance = atr * self.stop_loss_atr_mult
            return entry_price - distance if side == "LONG" else entry_price + distance

        return entry_price * (0.99 if side == "LONG" else 1.01)

    def calculate_take_profit(self, entry_price, side, atr=None):
        """ATR-based target with a fixed-price fallback."""
        if entry_price <= 0:
            return None

        if atr is not None and atr > 0:
            distance = atr * self.take_profit_atr_mult
            return entry_price + distance if side == "LONG" else entry_price - distance

        return entry_price * (1.02 if side == "LONG" else 0.98)

    def should_exit_position(self, position, current_data, entry_time, current_time):
        """Exit when ATR target/stop hits, trend alignment breaks, or max hold time expires."""
        if not position or not current_data:
            return False, "No position context"

        current_price = current_data.get("close")
        entry_price = position.get("entry_price", 0)
        side = position.get("side")
        stop_loss = position.get("stop_loss")
        take_profit = position.get("take_profit")

        if current_price is None or entry_price <= 0 or side not in {"LONG", "SHORT"}:
            return False, "Invalid exit inputs"

        entry_dt = self._ensure_utc_datetime(entry_time)
        current_dt = self._ensure_utc_datetime(current_time)
        holding_hours = (current_dt - entry_dt).total_seconds() / 3600 if current_dt >= entry_dt else 0

        if stop_loss:
            if side == "LONG" and current_price <= stop_loss:
                return True, f"Stop loss hit at {current_price:.2f}"
            if side == "SHORT" and current_price >= stop_loss:
                return True, f"Stop loss hit at {current_price:.2f}"

        if take_profit:
            if side == "LONG" and current_price >= take_profit:
                return True, f"Take profit hit at {current_price:.2f}"
            if side == "SHORT" and current_price <= take_profit:
                return True, f"Take profit hit at {current_price:.2f}"

        if holding_hours >= self.max_holding_hours:
            return True, f"Time exit after {holding_hours:.2f} hours"

        if side == "LONG" and not current_data.get("BULLISH_ALIGNMENT", False):
            return True, "Bullish alignment lost"
        if side == "SHORT" and not current_data.get("BEARISH_ALIGNMENT", False):
            return True, "Bearish alignment lost"

        return False, "Holding"

    def get_strategy_info(self):
        """Return strategy metadata for the dashboard."""
        return {
            "name": "Multi-Timeframe Scalper",
            "version": "2.0",
            "description": "1m BTCUSDT scalper with 1h/4h/1d trend alignment and ATR exits",
            "parameters": {
                "initial_capital": self.initial_capital,
                "leverage": self.leverage,
                "risk_per_trade": f"{self.risk_per_trade * 100:.1f}%",
                "pair": self.pair,
                "exchange": self.exchange,
                "order_type": self.order_type,
                "trend_timeframes": self.trend_timeframes,
                "entry_timeframe": self.entry_timeframe,
                "volatility_timeframe": self.volatility_timeframe,
                "atr_timeframe": self.atr_timeframe,
                "ema_period": self.ema_period,
                "adx_threshold": self.adx_threshold,
                "stoch_rsi": dict(self.stoch_rsi),
                "stop_loss_atr_mult": self.stop_loss_atr_mult,
                "take_profit_atr_mult": self.take_profit_atr_mult,
                "avoid_hours": list(self.avoid_hours),
            },
            "optimized_for": "BTCUSDT on Binance futures-style execution",
        }

    def analyze_market_sentiment(self, data_list):
        """Convert current alignment into a simple sentiment score."""
        if not data_list:
            return 50.0

        latest = data_list[-1]
        adx = latest.get("ADX") or 0
        sentiment = 50.0

        if latest.get("BULLISH_ALIGNMENT"):
            sentiment += 15
        elif latest.get("BEARISH_ALIGNMENT"):
            sentiment -= 15

        sentiment += min(adx / 2, 10)
        return max(0.0, min(100.0, sentiment))

    def get_market_bias(self, data_list):
        """Return signed bias from trend alignment and ADX strength."""
        if not data_list:
            return 0.0

        latest = data_list[-1]
        adx = latest.get("ADX") or 0
        if latest.get("BULLISH_ALIGNMENT"):
            return min(50.0, 20.0 + adx / 2)
        if latest.get("BEARISH_ALIGNMENT"):
            return max(-50.0, -(20.0 + adx / 2))
        return 0.0

    def update_signal_intelligence(self, data_list, signal_intel):
        """Expose strategy sentiment to the signal intelligence module."""
        if not signal_intel or not data_list:
            return

        try:
            signal_intel.sentiment_score = self.analyze_market_sentiment(data_list)
            signal_intel.liquidation_bias = self.get_market_bias(data_list)
        except Exception as exc:
            logger.error("Error updating signal intelligence: %s", exc)

    def _normalize_market_data(self, market_data):
        if not market_data:
            return None

        if isinstance(market_data, dict) and "timeframes" in market_data:
            return market_data

        if isinstance(market_data, list):
            entry_data = [dict(candle) for candle in market_data]
            timeframes = {self.entry_timeframe: entry_data}
            for timeframe in {self.atr_timeframe, self.volatility_timeframe, *self.trend_timeframes}:
                if timeframe == self.entry_timeframe:
                    continue
                timeframes[timeframe] = self._resample_candles(entry_data, timeframe)

            return {
                "symbol": self.pair,
                "timeframes": timeframes,
            }

        return None

    def _annotate_entry_indicators(self, data_list):
        raw_values, k_values, d_values, rsi_values = self._calculate_stoch_rsi_components(data_list)
        for index, candle in enumerate(data_list):
            candle["RSI"] = rsi_values[index] if index < len(rsi_values) else None
            candle["STOCH_RSI_RAW"] = raw_values[index] if index < len(raw_values) else None
            candle["STOCH_RSI_K"] = k_values[index] if index < len(k_values) else None
            candle["STOCH_RSI_D"] = d_values[index] if index < len(d_values) else None
            candle["STOCH_RSI"] = candle["STOCH_RSI_K"]

    def _annotate_atr(self, data_list):
        if not data_list:
            return None

        atr_values = calculate_atr(data_list, self.atr_period)
        for index, candle in enumerate(data_list):
            candle["ATR"] = atr_values[index] if index < len(atr_values) else None
        return data_list[-1].get("ATR")

    def _annotate_adx(self, data_list):
        if not data_list:
            return None

        adx_values = calculate_adx(data_list, self.adx_period)
        for index, candle in enumerate(data_list):
            candle["ADX"] = adx_values[index] if index < len(adx_values) else None
        return data_list[-1].get("ADX")

    def _annotate_trend(self, data_list, timeframe):
        if not data_list:
            return {"timeframe": timeframe, "trend": "UNKNOWN", "price": None, "ema": None}

        closes = [candle["close"] for candle in data_list]
        ema_values = calculate_ema(closes, self.ema_period)
        latest_price = closes[-1]
        latest_ema = ema_values[-1] if ema_values else None

        if latest_ema is None:
            trend = "UNKNOWN"
        else:
            trend = "UP" if latest_price >= latest_ema else "DOWN"

        return {
            "timeframe": timeframe,
            "trend": trend,
            "price": latest_price,
            "ema": latest_ema,
        }

    def _calculate_stoch_rsi_components(self, data_list):
        period = self.stoch_rsi["period"]
        smooth_k = self.stoch_rsi["smooth_k"]
        smooth_d = self.stoch_rsi["smooth_d"]

        rsi_values = calculate_rsi(data_list, period)
        raw_values = [None] * len(data_list)

        for index in range(period - 1, len(rsi_values)):
            current_rsi = rsi_values[index]
            if current_rsi is None:
                continue

            rsi_window = rsi_values[index - period + 1:index + 1]
            valid_rsi = [value for value in rsi_window if value is not None]
            if not valid_rsi:
                continue

            highest_rsi = max(valid_rsi)
            lowest_rsi = min(valid_rsi)

            if highest_rsi == lowest_rsi:
                raw_values[index] = 50.0
            else:
                raw_values[index] = ((current_rsi - lowest_rsi) / (highest_rsi - lowest_rsi)) * 100

        k_values = self._smooth_optional_series(raw_values, smooth_k)
        d_values = self._smooth_optional_series(k_values, smooth_d)
        return raw_values, k_values, d_values, rsi_values

    def _smooth_optional_series(self, values, period):
        if period <= 1:
            return list(values)

        smoothed = [None] * len(values)
        for index in range(period - 1, len(values)):
            window = values[index - period + 1:index + 1]
            if any(value is None for value in window):
                continue
            smoothed[index] = sum(window) / period
        return smoothed

    def _resample_candles(self, data_list, timeframe):
        if not data_list:
            return []

        sample_ts = data_list[0].get("timestamp")
        resampled = []
        current_bucket = None
        current_candle = None

        sorted_data = sorted(data_list, key=lambda candle: self._ensure_utc_datetime(candle.get("timestamp")))
        for candle in sorted_data:
            candle_time = self._ensure_utc_datetime(candle.get("timestamp"))
            bucket_start = self._bucket_start(candle_time, timeframe)

            if bucket_start != current_bucket:
                if current_candle:
                    resampled.append(current_candle)

                current_bucket = bucket_start
                current_candle = {
                    "timestamp": self._cast_timestamp(bucket_start, sample_ts),
                    "open": candle["open"],
                    "high": candle["high"],
                    "low": candle["low"],
                    "close": candle["close"],
                    "volume": float(candle.get("volume", 0) or 0),
                }
                continue

            current_candle["high"] = max(current_candle["high"], candle["high"])
            current_candle["low"] = min(current_candle["low"], candle["low"])
            current_candle["close"] = candle["close"]
            current_candle["volume"] += float(candle.get("volume", 0) or 0)

        if current_candle:
            resampled.append(current_candle)

        return resampled

    def _bucket_start(self, dt_value, timeframe):
        if timeframe.endswith("m"):
            minutes = int(timeframe[:-1])
            bucket_minute = (dt_value.minute // minutes) * minutes
            return dt_value.replace(minute=bucket_minute, second=0, microsecond=0)

        if timeframe.endswith("h"):
            hours = int(timeframe[:-1])
            bucket_hour = (dt_value.hour // hours) * hours
            return dt_value.replace(hour=bucket_hour, minute=0, second=0, microsecond=0)

        if timeframe.endswith("d"):
            days = int(timeframe[:-1])
            ordinal = dt_value.toordinal()
            bucket_ordinal = ordinal - ((ordinal - 1) % days)
            bucket = datetime.fromordinal(bucket_ordinal)
            return datetime(bucket.year, bucket.month, bucket.day)

        return dt_value.replace(second=0, microsecond=0)

    def _cast_timestamp(self, dt_value, sample_timestamp):
        if isinstance(sample_timestamp, datetime):
            return dt_value

        if isinstance(sample_timestamp, (int, float)):
            factor = 1000 if sample_timestamp > 10_000_000_000 else 1
            return int(dt_value.timestamp() * factor)

        return dt_value

    def _ensure_utc_datetime(self, value):
        if isinstance(value, datetime):
            if value.tzinfo is not None:
                return value.astimezone(timezone.utc).replace(tzinfo=None)
            return value

        if isinstance(value, (int, float)):
            timestamp = value / 1000 if value > 10_000_000_000 else value
            return datetime.utcfromtimestamp(timestamp)

        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is not None:
                    return parsed.astimezone(timezone.utc).replace(tzinfo=None)
                return parsed
            except ValueError:
                pass

        return datetime.utcnow()
