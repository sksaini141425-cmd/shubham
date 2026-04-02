"""
Market confluence strategy driven by price structure plus manual crowding data.

Price action comes from live candles. Funding, positioning, open interest, and
macro bias come from a local JSON file so the strategy can encode a human market
read without pretending to scrape unstable third-party sites.
"""
import json
import logging
import os
from datetime import datetime, timezone

from .strategy import calculate_atr, calculate_ema, calculate_macd, calculate_rsi

logger = logging.getLogger(__name__)


class MarketConfluenceStrategy:
    """
    A discretionary-style BTC confluence strategy turned into explicit rules.

    Required alignment for a trade:
    1. Price trigger at a key 24h level.
    2. Funding rate at an extreme.
    3. Retail positioning at an extreme.

    Optional filters improve confidence:
    - Fear and Greed
    - Open interest behavior
    - Manual macro/news bias
    """

    def __init__(self, leverage=5):
        self.leverage = min(max(int(leverage or 5), 1), 10)
        self.risk_per_trade = 0.01
        self.order_type = "market"

        self.entry_timeframe = "5m"
        self.structure_timeframe = "1h"
        self.required_history = {
            self.entry_timeframe: 300,
            self.structure_timeframe: 48,
        }

        self.ema_period = 20
        self.atr_period = 14
        self.level_tolerance_pct = 0.0035
        self.break_buffer_pct = 0.0015
        self.rsi_bullish_floor = 42
        self.rsi_bearish_ceiling = 58
        self.max_holding_hours = 6
        self.min_notional = 5.0

        self.funding_negative_threshold = float(
            os.environ.get("CONFLUENCE_NEG_FUNDING", "-0.00025")
        )
        self.funding_positive_threshold = float(
            os.environ.get("CONFLUENCE_POS_FUNDING", "0.00025")
        )
        self.retail_long_crowded_pct = float(
            os.environ.get("CONFLUENCE_RETAIL_LONG_CROWDED", "65")
        )
        self.retail_short_crowded_pct = float(
            os.environ.get("CONFLUENCE_RETAIL_SHORT_CROWDED", "35")
        )
        self.extreme_fear_threshold = float(
            os.environ.get("CONFLUENCE_EXTREME_FEAR", "20")
        )
        self.extreme_greed_threshold = float(
            os.environ.get("CONFLUENCE_EXTREME_GREED", "80")
        )
        self.oi_capitulation_threshold = float(
            os.environ.get("CONFLUENCE_OI_CAPITULATION", "-1.0")
        )
        self.oi_build_threshold = float(
            os.environ.get("CONFLUENCE_OI_BUILD", "1.0")
        )

        project_root = os.path.dirname(os.path.dirname(__file__))
        self.context_file = os.environ.get(
            "MARKET_CONTEXT_FILE",
            os.path.join(project_root, "market_context.json"),
        )

        self.use_strategy_position_sizing = True
        self.use_strategy_position_management = True
        self._latest_signal_context = {}

        logger.info(
            "Market Confluence Strategy initialized with %sx leverage using context file %s",
            self.leverage,
            self.context_file,
        )

    def fetch_market_data(self, symbol, data_loader):
        symbol = (symbol or "").upper()
        entry_data = data_loader.fetch_ohlcv(
            symbol,
            timeframe=self.entry_timeframe,
            limit=self.required_history[self.entry_timeframe],
        )
        structure_data = data_loader.fetch_ohlcv(
            symbol,
            timeframe=self.structure_timeframe,
            limit=self.required_history[self.structure_timeframe],
        )

        if not entry_data or not structure_data:
            logger.warning("[%s] Missing candles for confluence scan", symbol)
            return None

        return {
            "symbol": symbol,
            "timeframes": {
                self.entry_timeframe: [dict(candle) for candle in entry_data],
                self.structure_timeframe: [dict(candle) for candle in structure_data],
            },
            "context": self._load_market_context(symbol),
        }

    def calculate_indicators(self, market_data):
        if not market_data:
            return []

        symbol = (market_data.get("symbol") or "").upper()
        timeframes = market_data.get("timeframes") or {}
        entry_data = timeframes.get(self.entry_timeframe) or []
        structure_data = timeframes.get(self.structure_timeframe) or []
        context = market_data.get("context") or {}

        if len(entry_data) < max(self.ema_period * 3, 60) or len(structure_data) < 24:
            return []

        closes = [candle["close"] for candle in entry_data]
        ema_values = calculate_ema(closes, self.ema_period)
        rsi_values = calculate_rsi(entry_data, 14)
        macd_values, macd_signal_values, macd_hist_values = calculate_macd(entry_data)
        atr_values = calculate_atr(entry_data, self.atr_period)

        structure_window = structure_data[-24:]
        computed_support = min(candle["low"] for candle in structure_window)
        computed_resistance = max(candle["high"] for candle in structure_window)
        support_level = context.get("support_level") or computed_support
        resistance_level = context.get("resistance_level") or computed_resistance

        latest_1h = structure_data[-1]
        previous_1h = structure_data[-2] if len(structure_data) > 1 else latest_1h
        start_24h = structure_window[0]
        price_change_1h_pct = self._pct_change(previous_1h["close"], latest_1h["close"])
        price_change_24h_pct = self._pct_change(start_24h["open"], latest_1h["close"])

        for index, candle in enumerate(entry_data):
            candle["SYMBOL"] = symbol
            candle["EMA_20"] = ema_values[index] if index < len(ema_values) else None
            candle["RSI"] = rsi_values[index] if index < len(rsi_values) else None
            candle["MACD"] = macd_values[index] if index < len(macd_values) else None
            candle["MACD_Signal"] = (
                macd_signal_values[index] if index < len(macd_signal_values) else None
            )
            candle["MACD_Hist"] = (
                macd_hist_values[index] if index < len(macd_hist_values) else None
            )
            candle["ATR"] = atr_values[index] if index < len(atr_values) else None
            candle["SUPPORT_LEVEL"] = support_level
            candle["RESISTANCE_LEVEL"] = resistance_level
            candle["LOW_24H"] = computed_support
            candle["HIGH_24H"] = computed_resistance
            candle["PRICE_CHANGE_1H_PCT"] = price_change_1h_pct
            candle["PRICE_CHANGE_24H_PCT"] = price_change_24h_pct
            candle["CONTEXT_AVAILABLE"] = context.get("available", False)
            candle["CONTEXT_SYMBOL"] = context.get("symbol")
            candle["CONTEXT_SYMBOL_MATCH"] = context.get("symbol_matches", True)
            candle["FEAR_GREED_INDEX"] = context.get("fear_greed_index")
            candle["FEAR_GREED_PREVIOUS"] = context.get("fear_greed_previous")
            candle["RETAIL_LONG_RATIO_PCT"] = context.get("retail_long_ratio_pct")
            candle["FUNDING_RATE"] = context.get("funding_rate")
            candle["OI_CHANGE_1H_PCT"] = context.get("open_interest_change_pct_1h")
            candle["NEWS_BIAS"] = context.get("news_bias", "neutral")
            candle["MARKET_NOTES"] = context.get("notes", "")

        return entry_data

    def generate_signals(self, data_list):
        if not data_list or len(data_list) < 3:
            return data_list

        latest = data_list[-1]
        previous = data_list[-2]
        latest["signal"] = "NONE"
        latest["signal_strength"] = 0
        latest["signal_reason"] = "No setup"

        self._latest_signal_context = {
            "support": latest.get("SUPPORT_LEVEL"),
            "resistance": latest.get("RESISTANCE_LEVEL"),
            "invalidation_level": None,
            "setup_type": None,
        }

        if not latest.get("CONTEXT_AVAILABLE"):
            latest["signal_reason"] = (
                f"Market context missing ({os.path.basename(self.context_file)})"
            )
            return data_list

        if not latest.get("CONTEXT_SYMBOL_MATCH", True):
            latest["signal_reason"] = (
                f"Context symbol {latest.get('CONTEXT_SYMBOL')} does not match {latest.get('SYMBOL')}"
            )
            return data_list

        price = latest["close"]
        support = latest.get("SUPPORT_LEVEL")
        resistance = latest.get("RESISTANCE_LEVEL")
        atr_value = latest.get("ATR") or 0.0
        ema_value = latest.get("EMA_20")
        rsi_value = latest.get("RSI")
        macd_hist = latest.get("MACD_Hist")
        previous_hist = previous.get("MACD_Hist")
        price_change_1h_pct = latest.get("PRICE_CHANGE_1H_PCT")

        level_buffer = max(price * self.level_tolerance_pct, atr_value * 0.75)
        break_buffer = max(price * self.break_buffer_pct, atr_value * 0.35)

        bullish_momentum = (
            ema_value is not None
            and rsi_value is not None
            and macd_hist is not None
            and price > ema_value
            and price > previous.get("close", price)
            and rsi_value >= self.rsi_bullish_floor
            and macd_hist >= 0
            and (previous_hist is None or macd_hist >= previous_hist)
        )
        bearish_momentum = (
            ema_value is not None
            and rsi_value is not None
            and macd_hist is not None
            and price < ema_value
            and price < previous.get("close", price)
            and rsi_value <= self.rsi_bearish_ceiling
            and macd_hist <= 0
            and (previous_hist is None or macd_hist <= previous_hist)
        )

        near_support = bool(
            support
            and (
                abs(price - support) <= level_buffer
                or latest["low"] <= support + level_buffer
            )
        )
        near_resistance = bool(
            resistance
            and (
                abs(price - resistance) <= level_buffer
                or latest["high"] >= resistance - level_buffer
            )
        )

        support_bounce = bool(
            support
            and near_support
            and price >= support
            and latest["low"] <= support + level_buffer
            and bullish_momentum
        )
        support_breakdown = bool(
            support
            and price < support - break_buffer
            and bearish_momentum
        )
        resistance_rejection = bool(
            resistance
            and near_resistance
            and price <= resistance
            and latest["high"] >= resistance - level_buffer
            and bearish_momentum
        )

        long_ratio = latest.get("RETAIL_LONG_RATIO_PCT")
        funding_rate = latest.get("FUNDING_RATE")
        fear_greed = latest.get("FEAR_GREED_INDEX")
        fear_greed_previous = latest.get("FEAR_GREED_PREVIOUS")
        oi_change = latest.get("OI_CHANGE_1H_PCT")
        news_bias = (latest.get("NEWS_BIAS") or "neutral").strip().lower()

        crowd_long = long_ratio is not None and long_ratio <= self.retail_short_crowded_pct
        crowd_short = long_ratio is not None and long_ratio >= self.retail_long_crowded_pct
        funding_long = (
            funding_rate is not None and funding_rate <= self.funding_negative_threshold
        )
        funding_short = (
            funding_rate is not None and funding_rate >= self.funding_positive_threshold
        )

        fear_reversal = (
            fear_greed is not None
            and fear_greed <= self.extreme_fear_threshold
            and (
                fear_greed_previous is None
                or fear_greed > fear_greed_previous
            )
        )
        greed_blowoff = (
            fear_greed is not None and fear_greed >= self.extreme_greed_threshold
        )
        capitulation_long = (
            oi_change is not None
            and price_change_1h_pct is not None
            and oi_change <= self.oi_capitulation_threshold
            and price_change_1h_pct < 0
        )
        continuation_short = (
            oi_change is not None
            and price_change_1h_pct is not None
            and oi_change >= self.oi_build_threshold
            and price_change_1h_pct < 0
        )

        macro_long_ok = news_bias not in {"bearish", "risk_off"}
        macro_short_ok = news_bias not in {"bullish", "risk_on"}

        if support_bounce and funding_long and crowd_long and macro_long_ok:
            strength = 3 + int(fear_reversal) + int(capitulation_long) + int(news_bias == "bullish")
            latest["signal"] = "LONG"
            latest["signal_strength"] = min(strength, 5)
            latest["signal_reason"] = ", ".join(
                self._compact_reasons(
                    [
                        f"Support bounce near {support:.2f}",
                        f"Funding {funding_rate:.6f} <= {self.funding_negative_threshold:.6f}",
                        f"Retail longs {long_ratio:.1f}% <= {self.retail_short_crowded_pct:.1f}%",
                        (
                            f"Fear and Greed {fear_greed:.1f} with uptick"
                            if fear_reversal and fear_greed is not None
                            else None
                        ),
                        (
                            f"Open interest {oi_change:+.2f}% with price capitulation"
                            if capitulation_long and oi_change is not None
                            else None
                        ),
                        (
                            f"News bias {news_bias}"
                            if news_bias == "bullish"
                            else None
                        ),
                    ]
                )
            )
            self._latest_signal_context = {
                "support": support,
                "resistance": resistance,
                "invalidation_level": support,
                "setup_type": "support_bounce",
            }
        elif (support_breakdown or resistance_rejection) and funding_short and crowd_short and macro_short_ok:
            invalidation_level = resistance if resistance_rejection and resistance else support
            price_reason = (
                f"Resistance rejection near {resistance:.2f}"
                if resistance_rejection and resistance
                else f"Support break below {support:.2f}"
            )
            strength = 3 + int(continuation_short) + int(greed_blowoff) + int(news_bias == "bearish")
            latest["signal"] = "SHORT"
            latest["signal_strength"] = min(strength, 5)
            latest["signal_reason"] = ", ".join(
                self._compact_reasons(
                    [
                        price_reason,
                        f"Funding {funding_rate:.6f} >= {self.funding_positive_threshold:.6f}",
                        f"Retail longs {long_ratio:.1f}% >= {self.retail_long_crowded_pct:.1f}%",
                        (
                            f"Open interest {oi_change:+.2f}% confirming downside build"
                            if continuation_short and oi_change is not None
                            else None
                        ),
                        (
                            f"Fear and Greed {fear_greed:.1f} in greed zone"
                            if greed_blowoff and fear_greed is not None
                            else None
                        ),
                        (
                            f"News bias {news_bias}"
                            if news_bias == "bearish"
                            else None
                        ),
                    ]
                )
            )
            self._latest_signal_context = {
                "support": support,
                "resistance": resistance,
                "invalidation_level": invalidation_level,
                "setup_type": "resistance_rejection" if resistance_rejection else "support_breakdown",
            }
        else:
            bias_side = self._preferred_side(long_ratio)
            latest["signal_reason"] = self._build_no_trade_reason(
                bias_side=bias_side,
                support_bounce=support_bounce,
                support_breakdown=support_breakdown,
                resistance_rejection=resistance_rejection,
                funding_long=funding_long,
                funding_short=funding_short,
                crowd_long=crowd_long,
                crowd_short=crowd_short,
                macro_long_ok=macro_long_ok,
                macro_short_ok=macro_short_ok,
            )

        latest["trend"] = "BULLISH" if latest["signal"] == "LONG" else "BEARISH" if latest["signal"] == "SHORT" else "NEUTRAL"
        latest["volatility"] = "HIGH" if atr_value and price and (atr_value / price) > 0.008 else "NORMAL"
        return data_list

    def calculate_position_size(self, account_balance, entry_price, stop_loss_price):
        if account_balance <= 0 or entry_price <= 0 or stop_loss_price <= 0:
            return 0.0

        stop_distance = abs(entry_price - stop_loss_price)
        if stop_distance <= 0:
            return 0.0

        risk_amount = account_balance * self.risk_per_trade
        size_by_risk = risk_amount / stop_distance

        max_notional = account_balance * self.leverage
        max_size_by_leverage = max_notional / entry_price if entry_price > 0 else 0.0
        size = min(size_by_risk, max_size_by_leverage)

        if size * entry_price < self.min_notional:
            min_size = self.min_notional / entry_price
            if min_size <= max_size_by_leverage:
                size = min_size
            else:
                return 0.0

        return round(size, 6)

    def calculate_stop_loss(self, entry_price, side, atr=None):
        if entry_price <= 0:
            return None

        atr_distance = atr * 1.25 if atr else entry_price * 0.006
        invalidation = self._latest_signal_context.get("invalidation_level")
        cushion = max((atr or entry_price * 0.003) * 0.35, entry_price * 0.001)

        if side == "LONG":
            structural_stop = (
                invalidation - cushion if invalidation is not None else entry_price - atr_distance
            )
            return min(entry_price - atr_distance, structural_stop)

        structural_stop = (
            invalidation + cushion if invalidation is not None else entry_price + atr_distance
        )
        return max(entry_price + atr_distance, structural_stop)

    def calculate_take_profit(self, entry_price, side, atr=None):
        if entry_price <= 0:
            return None

        stop_loss = self.calculate_stop_loss(entry_price, side, atr)
        if stop_loss is None:
            return None

        risk_distance = abs(entry_price - stop_loss)
        if risk_distance <= 0:
            return None

        support = self._latest_signal_context.get("support")
        resistance = self._latest_signal_context.get("resistance")
        cushion = max((atr or entry_price * 0.003) * 0.25, entry_price * 0.001)

        if side == "LONG":
            rr_target = entry_price + (risk_distance * 2.0)
            structural_target = (
                resistance - cushion
                if resistance is not None and resistance > entry_price
                else None
            )
            if structural_target is not None:
                return min(rr_target, structural_target)
            return rr_target

        rr_target = entry_price - (risk_distance * 2.0)
        structural_target = (
            support + cushion if support is not None and support < entry_price else None
        )
        if structural_target is not None:
            return max(rr_target, structural_target)
        return rr_target

    def should_exit_position(self, position, current_data, entry_time, current_time):
        if not position or not current_data:
            return False, "No position context"

        current_price = current_data.get("close")
        entry_price = position.get("entry_price", 0)
        side = position.get("side")
        stop_loss = position.get("stop_loss")
        take_profit = position.get("take_profit")

        if current_price is None or entry_price <= 0 or side not in {"LONG", "SHORT"}:
            return False, "Invalid exit inputs"

        holding_hours = self._holding_hours(entry_time, current_time)

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

        if side == "LONG" and current_data.get("signal") == "SHORT":
            return True, "Opposite confluence signal"
        if side == "SHORT" and current_data.get("signal") == "LONG":
            return True, "Opposite confluence signal"

        invalidation = self._latest_signal_context.get("invalidation_level")
        if invalidation is not None:
            if side == "LONG" and current_price < invalidation:
                return True, "Lost support invalidation level"
            if side == "SHORT" and current_price > invalidation:
                return True, "Lost downside invalidation level"

        return False, "Holding"

    def get_strategy_info(self):
        return {
            "name": "Market Confluence",
            "version": "1.0",
            "description": "Price structure plus funding, retail crowding, and macro context",
            "parameters": {
                "entry_timeframe": self.entry_timeframe,
                "structure_timeframe": self.structure_timeframe,
                "risk_per_trade": f"{self.risk_per_trade * 100:.1f}%",
                "max_holding_hours": self.max_holding_hours,
                "funding_negative_threshold": self.funding_negative_threshold,
                "funding_positive_threshold": self.funding_positive_threshold,
                "retail_long_crowded_pct": self.retail_long_crowded_pct,
                "retail_short_crowded_pct": self.retail_short_crowded_pct,
                "context_file": self.context_file,
            },
            "optimized_for": "BTC-style reversal and breakdown confluence setups",
        }

    def _load_market_context(self, symbol):
        symbol = (symbol or "").upper()
        payload = {}

        if os.path.exists(self.context_file):
            try:
                with open(self.context_file, "r", encoding="utf-8") as handle:
                    payload = json.load(handle) or {}
            except Exception as exc:
                logger.error("Failed to parse market context file %s: %s", self.context_file, exc)
                payload = {}

        if isinstance(payload.get("symbols"), dict):
            global_defaults = {k: v for k, v in payload.items() if k != "symbols"}
            symbol_payload = payload["symbols"].get(symbol, {})
            if not isinstance(symbol_payload, dict):
                symbol_payload = {}
            payload = {**global_defaults, **symbol_payload}

        context_symbol = str(payload.get("symbol", "") or "").upper() or None

        return {
            "available": bool(payload),
            "symbol": context_symbol,
            "symbol_matches": context_symbol in {None, "", symbol},
            "support_level": self._coerce_float(
                payload.get("support_level", payload.get("support"))
            ),
            "resistance_level": self._coerce_float(
                payload.get("resistance_level", payload.get("resistance"))
            ),
            "fear_greed_index": self._coerce_float(payload.get("fear_greed_index")),
            "fear_greed_previous": self._coerce_float(payload.get("fear_greed_previous")),
            "retail_long_ratio_pct": self._coerce_float(
                payload.get("retail_long_ratio_pct", payload.get("long_ratio_pct"))
            ),
            "funding_rate": self._coerce_float(payload.get("funding_rate")),
            "open_interest_change_pct_1h": self._coerce_float(
                payload.get("open_interest_change_pct_1h")
            ),
            "news_bias": str(payload.get("news_bias", "neutral") or "neutral").strip().lower(),
            "notes": str(payload.get("notes", "") or "").strip(),
        }

    def _build_no_trade_reason(
        self,
        bias_side,
        support_bounce,
        support_breakdown,
        resistance_rejection,
        funding_long,
        funding_short,
        crowd_long,
        crowd_short,
        macro_long_ok,
        macro_short_ok,
    ):
        reasons = []

        if bias_side == "LONG":
            if not support_bounce:
                reasons.append("long price trigger missing")
            if not funding_long:
                reasons.append("long funding not extreme enough")
            if not crowd_long:
                reasons.append("retail not short enough for a squeeze")
            if not macro_long_ok:
                reasons.append("macro/news bias blocks longs")
        elif bias_side == "SHORT":
            if not (support_breakdown or resistance_rejection):
                reasons.append("short price trigger missing")
            if not funding_short:
                reasons.append("short funding not extreme enough")
            if not crowd_short:
                reasons.append("retail longs not crowded enough")
            if not macro_short_ok:
                reasons.append("macro/news bias blocks shorts")
        else:
            if not support_bounce and not support_breakdown and not resistance_rejection:
                reasons.append("price not at a qualified support or resistance trigger")
            if not funding_long and not funding_short:
                reasons.append("funding not at an extreme")
            if not crowd_long and not crowd_short:
                reasons.append("retail positioning not extreme")

        return ", ".join(reasons) if reasons else "No confluence"

    def _preferred_side(self, long_ratio):
        if long_ratio is None:
            return None
        if long_ratio >= 50:
            return "SHORT"
        return "LONG"

    def _compact_reasons(self, reasons):
        return [reason for reason in reasons if reason]

    def _pct_change(self, start_value, end_value):
        if start_value in {None, 0} or end_value is None:
            return None
        return ((end_value - start_value) / start_value) * 100.0

    def _coerce_float(self, value):
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _holding_hours(self, entry_time, current_time):
        entry_dt = self._coerce_datetime(entry_time)
        current_dt = self._coerce_datetime(current_time)
        if entry_dt is None or current_dt is None or current_dt < entry_dt:
            return 0.0
        return (current_dt - entry_dt).total_seconds() / 3600.0

    def _coerce_datetime(self, value):
        if value is None:
            return None
        if isinstance(value, datetime):
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
                return None
        return None
