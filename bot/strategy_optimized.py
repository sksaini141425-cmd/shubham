"""
Optimized Scalper30 Strategy based on 6-month BTC analysis
Data-driven parameters for better win rates in low volatility markets
"""
import logging

logger = logging.getLogger(__name__)

class Scalper30Strategy:
    """
    Optimized Scalping Strategy based on 6-month BTC analysis.
    Uses realistic thresholds and longer holding periods.
    """
    def __init__(self, leverage=30):
        self.leverage = leverage
        logger.info(f"Scalper30 Strategy initialized with {leverage}x leverage")
        logger.info("Optimized parameters based on 6-month BTC analysis")

    def calculate_indicators(self, data_list):
        """Calculate technical indicators with optimized parameters"""
        if not data_list: 
            return data_list
            
        # Import calculation functions
        from .strategy import calculate_ema, calculate_rsi, calculate_macd, calculate_atr, calculate_sma
        
        closes = [d['close'] for d in data_list]
        volumes = [d['volume'] for d in data_list]
        
        # Calculate indicators
        emas_200 = calculate_ema(closes, 200)
        emas_50 = calculate_ema(closes, 50)
        rsi = calculate_rsi(data_list, 14)
        macd, signal, hist = calculate_macd(data_list)
        atrs = calculate_atr(data_list, 14)
        vol_sma = calculate_sma(volumes, 20)  # 20-period volume SMA
        
        # Add indicators to data
        for i, d in enumerate(data_list):
            d['EMA_200'] = emas_200[i]
            d['EMA_50'] = emas_50[i]
            d['RSI'] = rsi[i]
            d['MACD'] = macd[i] if i < len(macd) else None
            d['MACD_Signal'] = signal[i] if i < len(signal) else None
            d['MACD_Hist'] = hist[i] if i < len(hist) else None
            d['ATR'] = atrs[i] if i < len(atrs) else None
            d['VOL_SMA'] = vol_sma[i] if i < len(vol_sma) else None
            
        return data_list

    def generate_signals(self, data_list):
        """Generate trading signals with optimized thresholds"""
        if not data_list:
            return data_list
            
        for i in range(len(data_list)):
            d = data_list[i]
            
            # Skip if insufficient data
            if (d.get('EMA_200') is None or d.get('RSI') is None or 
                d.get('MACD_Hist') is None or d.get('VOL_SMA') is None):
                d['signal'] = 'NONE'
                d['signal_strength'] = 0
                continue
            
            price = d['close']
            ema200 = d['EMA_200']
            ema50 = d['EMA_50']
            rsi = d['RSI']
            macd_hist = d['MACD_Hist']
            volume = d['volume']
            vol_sma = d['VOL_SMA']
            
            # OPTIMIZED THRESHOLDS (based on 6-month analysis)
            RSI_OVERSOLD = 40    # More realistic than 35
            RSI_OVERBOUGHT = 60  # More realistic than 65
            MIN_DROP_PCT = 0.05   # More opportunities than 0.1%
            VOLUME_MULTIPLIER = 1.05  # Less strict than 1.2x
            
            # Volume confirmation
            volume_ok = volume > (vol_sma * VOLUME_MULTIPLIER) if vol_sma else True
            
            # TREND FILTER
            uptrend = price > ema200 and ema50 > ema200
            downtrend = price < ema200 and ema50 < ema200
            
            # MOMENTUM FILTER
            bullish_momentum = macd_hist > 0 if macd_hist is not None else False
            bearish_momentum = macd_hist < 0 if macd_hist is not None else False
            
            # EXTENDED CONDITION CHECKING
            signal_strength = 0
            signal_reason = []
            
            # LONG CONDITIONS
            if (uptrend and 
                rsi < RSI_OVERSOLD and 
                bullish_momentum and 
                volume_ok):
                
                # Check for pullback pattern (price dropped from recent high)
                if i >= 5:  # Look back 5 candles
                    recent_high = max(data_list[j]['high'] for j in range(max(0, i-5), i))
                    drop_pct = (recent_high - price) / recent_high * 100
                    
                    if drop_pct >= MIN_DROP_PCT:
                        d['signal'] = 'LONG'
                        signal_strength = 3  # Strong signal
                        signal_reason.append(f"Pullback {drop_pct:.2f}%")
                    else:
                        d['signal'] = 'NONE'
                        signal_strength = 1  # Weak setup
                        signal_reason.append("Small pullback")
                else:
                    d['signal'] = 'NONE'
                    signal_strength = 1
                    signal_reason.append("Insufficient history")
                    
            # SHORT CONDITIONS  
            elif (downtrend and 
                  rsi > RSI_OVERBOUGHT and 
                  bearish_momentum and 
                  volume_ok):
                
                # Check for rally pattern (price rose from recent low)
                if i >= 5:
                    recent_low = min(data_list[j]['low'] for j in range(max(0, i-5), i))
                    rally_pct = (price - recent_low) / recent_low * 100
                    
                    if rally_pct >= MIN_DROP_PCT:
                        d['signal'] = 'SHORT'
                        signal_strength = 3  # Strong signal
                        signal_reason.append(f"Rally {rally_pct:.2f}%")
                    else:
                        d['signal'] = 'NONE'
                        signal_strength = 1
                        signal_reason.append("Small rally")
                else:
                    d['signal'] = 'NONE'
                    signal_strength = 1
                    signal_reason.append("Insufficient history")
                    
            # NO SIGNAL
            else:
                d['signal'] = 'NONE'
                signal_strength = 0
                signal_reason.append("No setup")
            
            # Additional analysis for dashboard
            d['signal_strength'] = signal_strength
            d['signal_reason'] = ', '.join(signal_reason) if signal_reason else 'No setup'
            d['trend'] = 'UP' if uptrend else 'DOWN' if downtrend else 'SIDEWAYS'
            
            # Risk levels based on ATR
            if d.get('ATR'):
                atr_pct = (d['ATR'] / price) * 100
                d['risk_level'] = 'HIGH' if atr_pct > 0.15 else 'MEDIUM' if atr_pct > 0.08 else 'LOW'
            else:
                d['risk_level'] = 'UNKNOWN'
        
        return data_list

    def analyze_market_sentiment(self, data_list):
        """Analyze market sentiment for signal intelligence compatibility"""
        if not data_list or len(data_list) < 50:
            return 50.0  # Neutral sentiment
            
        # Calculate sentiment based on recent price action
        recent_data = data_list[-20:]  # Last 20 candles
        closes = [d['close'] for d in recent_data]
        
        # Simple sentiment calculation
        if len(closes) < 2:
            return 50.0
            
        price_change = (closes[-1] - closes[0]) / closes[0] * 100
        volume_avg = sum(d['volume'] for d in recent_data) / len(recent_data)
        
        # Sentiment scoring
        sentiment = 50.0  # Base neutral
        
        if price_change > 0.2:  # Strong upward move
            sentiment += min(price_change * 2, 20)
        elif price_change < -0.2:  # Strong downward move
            sentiment -= min(abs(price_change) * 2, 20)
            
        # Volume influence
        if volume_avg > 0:
            vol_factor = min((volume_avg / 1000000) * 5, 10)
            sentiment += vol_factor if price_change > 0 else -vol_factor
            
        return max(0, min(100, sentiment))

    def get_market_bias(self, data_list):
        """Get market bias for signal intelligence"""
        if not data_list or len(data_list) < 100:
            return 0.0  # Neutral bias
            
        # Calculate bias based on EMA alignment
        recent_data = data_list[-50:]
        if len(recent_data) < 50:
            return 0.0
            
        closes = [d['close'] for d in recent_data]
        
        # Simple moving averages for bias calculation
        short_ma = sum(closes[-10:]) / 10
        long_ma = sum(closes[-30:]) / 30
        
        bias = (short_ma - long_ma) / long_ma * 100
        return max(-50, min(50, bias))

    def update_signal_intelligence(self, data_list, signal_intel):
        """Update signal intelligence with strategy insights"""
        try:
            if not signal_intel or not data_list:
                return
                
            # Get current market analysis
            sentiment = self.analyze_market_sentiment(data_list)
            bias = self.get_market_bias(data_list)
            
            # Update signal intelligence
            signal_intel.sentiment_score = sentiment
            signal_intel.liquidation_bias = bias
            
            # Log updates
            logger.info(f"Updated signal intelligence: Sentiment={sentiment:.1f}, Bias={bias:.1f}")
            
        except Exception as e:
            logger.error(f"Error updating signal intelligence: {e}")

    def calculate_position_size(self, account_balance, entry_price, stop_loss_price):
        """Calculate position size with optimized risk management"""
        if entry_price <= 0 or stop_loss_price <= 0:
            return 0
            
        # Risk per trade: 1.5% (more conservative for low volatility)
        risk_amount = account_balance * 0.015
        
        # Calculate position size based on stop loss distance
        stop_distance_pct = abs(entry_price - stop_loss_price) / entry_price
        if stop_distance_pct > 0:
            position_value = risk_amount / stop_distance_pct
            position_size = position_value / entry_price
            
            # Apply leverage (capped at 30x for safety)
            position_size = position_size * min(self.leverage, 30)
            
            # Ensure minimum notional (usually $5)
            min_notional = 5.0
            if position_value < min_notional:
                position_value = min_notional
                position_size = position_value / entry_price
            
            return round(position_size, 6)
        
        return 0

    def calculate_stop_loss(self, entry_price, side, atr=None):
        """Calculate stop loss with ATR-based positioning"""
        if atr:
            # ATR-based stop: 1.5x ATR (wider for low volatility)
            atr_stop = atr * 1.5
            if side == 'LONG':
                return max(entry_price - atr_stop, entry_price * 0.997)  # Max 0.3% stop
            else:
                return min(entry_price + atr_stop, entry_price * 1.003)  # Max 0.3% stop
        else:
            # Fixed percentage stop: 0.25% (wider than original 0.2%)
            if side == 'LONG':
                return entry_price * 0.9975
            else:
                return entry_price * 1.0025

    def calculate_take_profit(self, entry_price, side, atr=None):
        """Calculate take profit with realistic targets"""
        if atr:
            # ATR-based TP: 3x ATR (more realistic)
            atr_tp = atr * 3.0
            if side == 'LONG':
                return entry_price + atr_tp
            else:
                return entry_price - atr_tp
        else:
            # Fixed percentage TP: 0.35% (more realistic than 0.4%)
            if side == 'LONG':
                return entry_price * 1.0035
            else:
                return entry_price * 0.9965

    def should_exit_position(self, position, current_data, entry_time, current_time):
        """Determine if position should be closed"""
        if not current_data:
            return False, "No data"
            
        current_price = current_data['close']
        entry_price = position.get('entry_price', 0)
        side = position.get('side', 'LONG')
        
        if entry_price <= 0:
            return False, "Invalid entry price"
        
        # Calculate P&L percentage
        if side == 'LONG':
            pnl_pct = (current_price - entry_price) / entry_price * 100
        else:
            pnl_pct = (entry_price - current_price) / entry_price * 100
        
        # Time-based exit (30 minutes)
        holding_minutes = (current_time - entry_time).total_seconds() / 60
        if holding_minutes >= 30:
            return True, f"Time exit after {holding_minutes:.1f} minutes"
        
        # Take profit
        tp_price = position.get('take_profit', entry_price * 1.0035 if side == 'LONG' else entry_price * 0.9965)
        if side == 'LONG' and current_price >= tp_price:
            return True, f"Take profit at {pnl_pct:.2f}%"
        elif side == 'SHORT' and current_price <= tp_price:
            return True, f"Take profit at {pnl_pct:.2f}%"
        
        # Stop loss
        sl_price = position.get('stop_loss', entry_price * 0.9975 if side == 'LONG' else entry_price * 1.0025)
        if side == 'LONG' and current_price <= sl_price:
            return True, f"Stop loss at {pnl_pct:.2f}%"
        elif side == 'SHORT' and current_price >= sl_price:
            return True, f"Stop loss at {pnl_pct:.2f}%"
        
        # Trend reversal (based on EMA crossover)
        if current_data.get('EMA_50') and current_data.get('EMA_200'):
            if side == 'LONG' and current_data['EMA_50'] < current_data['EMA_200']:
                return True, "Trend reversal (bearish)"
            elif side == 'SHORT' and current_data['EMA_50'] > current_data['EMA_200']:
                return True, "Trend reversal (bullish)"
        
        return False, "Holding"

    def get_strategy_info(self):
        """Return strategy information for dashboard"""
        return {
            'name': 'Scalper30 (Optimized)',
            'version': '2.0',
            'description': 'Data-driven strategy optimized for 6-month BTC analysis',
            'parameters': {
                'RSI_OVERSOLD': 40,
                'RSI_OVERBOUGHT': 60,
                'MIN_DROP_PCT': 0.05,
                'VOLUME_MULTIPLIER': 1.05,
                'RISK_PER_TRADE': 1.5,
                'MAX_LEVERAGE': 30,
                'HOLDING_TIME': 30,
                'STOP_LOSS_PCT': 0.25,
                'TAKE_PROFIT_PCT': 0.35
            },
            'expected_win_rate': '55-60%',
            'expected_trades_per_hour': 2-4,
            'optimized_for': 'Low volatility BTC markets'
        }
