import logging
import math

logger = logging.getLogger(__name__)

def calculate_sma(prices, period):
    if len(prices) < period:
        return [None] * len(prices)
    smas = [None] * (period - 1)
    for i in range(period, len(prices) + 1):
        smas.append(sum(prices[i-period:i]) / period)
    return smas

def calculate_ema(prices, period):
    if len(prices) < period:
        return [None] * len(prices)
    
    k = 2 / (period + 1)
    emas = [None] * (period - 1)
    
    # First EMA is SMA
    first_ema = sum(prices[:period]) / period
    emas.append(first_ema)
    
    for i in range(period, len(prices)):
        new_ema = prices[i] * k + emas[-1] * (1 - k)
        emas.append(new_ema)
    return emas

def calculate_atr(data, period=14):
    if len(data) < period + 1:
        return [None] * len(data)
        
    true_ranges = [None]
    for i in range(1, len(data)):
        high = data[i]['high']
        low = data[i]['low']
        prev_close = data[i-1]['close']
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)
        
    atr = [None] * period
    first_atr = sum([tr for tr in true_ranges[1:period+1] if tr is not None]) / period
    atr.append(first_atr)
    
    for i in range(period + 1, len(true_ranges)):
        current_atr = (atr[-1] * (period - 1) + true_ranges[i]) / period
        atr.append(current_atr)
    return atr

class BaseStrategy:
    def __init__(self, leverage=1):
        self.leverage = min(leverage, 150)
        logger.info(f"Strategy initialized with {self.leverage}x leverage.")
        
    def calculate_indicators(self, data_list):
        raise NotImplementedError()
        
    def generate_signals(self, data_list):
        raise NotImplementedError()

def calculate_rsi(data_list, period=14):
    if len(data_list) < period + 1:
        return [None] * len(data_list)
        
    rsi_list = [None] * period
    gains = []
    losses = []
    
    for i in range(1, period + 1):
        change = data_list[i]['close'] - data_list[i-1]['close']
        gains.append(max(0, change))
        losses.append(max(0, -change))
        
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    
    if avg_loss == 0:
        rsi_list.append(100.0)
    else:
        rs = avg_gain / avg_loss
        rsi_list.append(100.0 - (100.0 / (1.0 + rs)))
        
    for i in range(period + 1, len(data_list)):
        change = data_list[i]['close'] - data_list[i-1]['close']
        gain = max(0, change)
        loss = max(0, -change)
        
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        
        if avg_loss == 0:
            rsi_list.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_list.append(100.0 - (100.0 / (1.0 + rs)))
            
    return rsi_list

def calculate_macd(data_list, fast_period=12, slow_period=26, signal_period=9):
    if len(data_list) < slow_period:
        return [None]*len(data_list), [None]*len(data_list), [None]*len(data_list)
        
    closes = [d['close'] for d in data_list]
    ema_fast = calculate_ema(closes, fast_period)
    ema_slow = calculate_ema(closes, slow_period)
    
    macd_line = []
    for f, s in zip(ema_fast, ema_slow):
        if f is None or s is None:
            macd_line.append(None)
        else:
            macd_line.append(f - s)
            
    # Calculate Signal Line (EMA of MACD Line)
    valid_macd = [m for m in macd_line if m is not None]
    if len(valid_macd) < signal_period:
        signal_line = [None] * len(macd_line)
    else:
        macds_ema = calculate_ema(valid_macd, signal_period)
        signal_line = [None] * (len(macd_line) - len(macds_ema)) + macds_ema
        
    histogram = []
    for m, s in zip(macd_line, signal_line):
        if m is None or s is None:
            histogram.append(None)
        else:
            histogram.append(m - s)
            
    return macd_line, signal_line, histogram

def calculate_bollinger_bands(prices, period=20, std_dev_multiplier=2.0):
    if len(prices) < period:
        return [None]*len(prices), [None]*len(prices), [None]*len(prices)
        
    upper_band = [None] * (period - 1)
    middle_band = [None] * (period - 1)
    lower_band = [None] * (period - 1)
    
    for i in range(period, len(prices) + 1):
        window = prices[i-period:i]
        sma = sum(window) / period
        variance = sum((x - sma) ** 2 for x in window) / period
        std_dev = math.sqrt(variance)
        
        middle_band.append(sma)
        upper_band.append(sma + (std_dev_multiplier * std_dev))
        lower_band.append(sma - (std_dev_multiplier * std_dev))
        
    return upper_band, middle_band, lower_band

class SmartMoneyStrategy(BaseStrategy):
    def __init__(self, leverage=45):
        super().__init__(leverage=leverage)

    def calculate_indicators(self, data_list):
        if not data_list: return data_list

class DiamondSniperStrategy(BaseStrategy):
    """
    Explosive Breakout Strategy (Diamond Sniper).
    Waits for a Bollinger Band Squeeze (low volatility) and enters on an explosive breakout.
    Designed to catch 5-10% moves with high leverage for maximum profit.
    """
    def __init__(self, leverage=50):
        super().__init__(leverage=leverage)

    def calculate_indicators(self, data_list):
        if not data_list: return data_list
        closes = [d['close'] for d in data_list]
        volumes = [d['volume'] for d in data_list]
        
        upper, middle, lower = calculate_bollinger_bands(closes, 20, 2.0)
        emas_200 = calculate_ema(closes, 200)
        atrs = calculate_atr(data_list, 14)
        vol_sma = calculate_sma(volumes, 20)
        
        for i, d in enumerate(data_list):
            d['BB_Upper'] = upper[i]
            d['BB_Lower'] = lower[i]
            d['BB_Middle'] = middle[i]
            d['EMA_200'] = emas_200[i]
            d['ATR'] = atrs[i]
            d['VOL_SMA'] = vol_sma[i]
            
            # Squeeze indicator: Band width
            if upper[i] and lower[i] and middle[i]:
                d['BB_Width'] = (upper[i] - lower[i]) / middle[i]
            else:
                d['BB_Width'] = None
                
        return data_list

    def generate_signals(self, data_list):
        if len(data_list) < 50: return data_list
        
        # Calculate average BB width for squeeze detection
        widths = [d['BB_Width'] for d in data_list[-50:] if d['BB_Width'] is not None]
        avg_width = sum(widths) / len(widths) if widths else 0
        
        for i in range(1, len(data_list)):
            d, prev_d = data_list[i], data_list[i-1]
            price, vol = d['close'], d['volume']
            ema200 = d.get('EMA_200')
            bb_upper, bb_lower = d.get('BB_Upper'), d.get('BB_Lower')
            bb_width = d.get('BB_Width')
            vol_sma = d.get('VOL_SMA')
            
            d['signal'] = 'NONE'
            if None in [ema200, bb_upper, bb_lower, bb_width, vol_sma]: continue
            
            # SQUEEZE condition: Current width is 20% tighter than average
            is_squeeze = bb_width < (avg_width * 0.8)
            
            # LONG: Price breaks BB Upper with high volume + Above EMA 200
            if price > bb_upper and vol > (vol_sma * 1.5) and price > ema200:
                d['signal'] = 'LONG'
            
            # SHORT: Price breaks BB Lower with high volume + Below EMA 200
            elif price < bb_lower and vol > (vol_sma * 1.5) and price < ema200:
                d['signal'] = 'SHORT'
                
        return data_list

class HyperScalper25Strategy(BaseStrategy):
    """
    Hyper-Aggressive Scalping Strategy targeting $25 from $3.
    Uses 50x leverage, compounding, and a tight trailing stop loss.
    """
    def __init__(self, leverage=50):
        super().__init__(leverage=leverage)

    def calculate_indicators(self, data_list):
        if not data_list: return data_list
        closes = [d['close'] for d in data_list]
        emas_9 = calculate_ema(closes, 9)
        emas_21 = calculate_ema(closes, 21)
        emas_200 = calculate_ema(closes, 200)
        rsi = calculate_rsi(data_list, 14)
        macd, signal, hist = calculate_macd(data_list)
        atrs = calculate_atr(data_list, 14)
        
        for i, d in enumerate(data_list):
            d['EMA_9'] = emas_9[i]
            d['EMA_21'] = emas_21[i]
            d['EMA_200'] = emas_200[i]
            d['RSI'] = rsi[i]
            d['MACD_Hist'] = hist[i]
            d['ATR'] = atrs[i]
        return data_list

    def generate_signals(self, data_list):
        if len(data_list) < 200: return data_list
        for i in range(1, len(data_list)):
            d, prev_d = data_list[i], data_list[i-1]
            price = d['close']
            rsi, macd_hist = d.get('RSI'), d.get('MACD_Hist')
            ema9, ema21, ema200 = d.get('EMA_9'), d.get('EMA_21'), d.get('EMA_200')
            
            d['signal'] = 'NONE'
            if None in [rsi, macd_hist, ema9, ema21, ema200]: continue
            
            # HYPER LONG: 
            # 1. Price > EMA 200 (Main Trend)
            # 2. EMA 9 crosses above EMA 21 (Short-term momentum)
            # 3. RSI is not yet overbought (< 60)
            if price > ema200 and ema9 > ema21 and prev_d.get('EMA_9', 0) <= prev_d.get('EMA_21', 0) and rsi < 60:
                d['signal'] = 'LONG'
            
            # HYPER SHORT:
            # 1. Price < EMA 200
            # 2. EMA 9 crosses below EMA 21
            # 3. RSI is not yet oversold (> 40)
            elif price < ema200 and ema9 < ema21 and prev_d.get('EMA_9', 0) >= prev_d.get('EMA_21', 0) and rsi > 40:
                d['signal'] = 'SHORT'
                
        return data_list
        closes = [d['close'] for d in data_list]
        emas_200 = calculate_ema(closes, 200)
        atrs = calculate_atr(data_list, 14)
        rsi = calculate_rsi(data_list, 14)
        macd, signal, hist = calculate_macd(data_list)
        upper, middle, lower = calculate_bollinger_bands(closes, 20)
        
        for i, d in enumerate(data_list):
            d['EMA_200'] = emas_200[i]
            d['ATR'] = atrs[i]
            d['RSI'] = rsi[i]
            d['MACD_Hist'] = hist[i]
            d['BB_Upper'] = upper[i]
            d['BB_Lower'] = lower[i]
        return data_list

    def generate_signals(self, data_list):
        if len(data_list) < 20: return data_list
        for i in range(1, len(data_list)):
            d, prev_d = data_list[i], data_list[i-1]
            price, rsi = d['close'], d.get('RSI')
            macd_hist, prev_macd_hist = d.get('MACD_Hist'), prev_d.get('MACD_Hist')
            ema200 = d.get('EMA_200')
            d['signal'] = 'NONE'
            if None in [rsi, macd_hist, prev_macd_hist, ema200]: continue
            if price > ema200 and rsi < 35 and macd_hist > prev_macd_hist:
                d['signal'] = 'LONG'
            elif price < ema200 and rsi > 65 and macd_hist < prev_macd_hist:
                d['signal'] = 'SHORT'
        return data_list

class RSDTraderStrategy(BaseStrategy):
    def __init__(self, leverage=45):
        super().__init__(leverage=leverage)

    def calculate_indicators(self, data_list):
        if not data_list: return data_list
        closes = [d['close'] for d in data_list]
        emas_200 = calculate_ema(closes, 200)
        atrs = calculate_atr(data_list, 14)
        rsi = calculate_rsi(data_list, 14)
        macd, signal, hist = calculate_macd(data_list)
        upper, middle, lower = calculate_bollinger_bands(closes, 20)
        
        for i, d in enumerate(data_list):
            d['EMA_200'] = emas_200[i]
            d['ATR'] = atrs[i]
            d['RSI'] = rsi[i]
            d['MACD_Hist'] = hist[i]
            d['BB_Upper'] = upper[i]
            d['BB_Lower'] = lower[i]
        return data_list

    def generate_signals(self, data_list):
        if len(data_list) < 20: return data_list
        for i in range(1, len(data_list)):
            d, prev_d = data_list[i], data_list[i-1]
            price, rsi = d['close'], d.get('RSI')
            macd_hist, prev_macd_hist = d.get('MACD_Hist'), prev_d.get('MACD_Hist')
            ema200, bb_upper, bb_lower = d.get('EMA_200'), d.get('BB_Upper'), d.get('BB_Lower')
            d['signal'] = 'NONE'
            if None in [rsi, macd_hist, prev_macd_hist, ema200, bb_upper, bb_lower]: continue
            if price > ema200 and (rsi < 35 or price <= bb_lower) and macd_hist > prev_macd_hist:
                d['signal'] = 'LONG'
            elif price < ema200 and (rsi > 65 or price >= bb_upper) and macd_hist < prev_macd_hist:
                d['signal'] = 'SHORT'
        return data_list

class EliteScalperStrategy(BaseStrategy):
    def __init__(self, leverage=45):
        super().__init__(leverage=leverage)

    def calculate_indicators(self, data_list):
        if not data_list: return data_list
        closes = [d['close'] for d in data_list]
        volumes = [d['volume'] for d in data_list]
        emas_50 = calculate_ema(closes, 50)
        emas_200 = calculate_ema(closes, 200)
        atrs = calculate_atr(data_list, 14)
        rsi = calculate_rsi(data_list, 14)
        macd, signal, hist = calculate_macd(data_list)
        vol_sma = calculate_sma(volumes, 10)
        
        for i, d in enumerate(data_list):
            d['EMA_50'] = emas_50[i]
            d['EMA_200'] = emas_200[i]
            d['ATR'] = atrs[i]
            d['RSI'] = rsi[i]
            d['MACD_Hist'] = hist[i]
            d['VOL_SMA'] = vol_sma[i]
        return data_list

    def generate_signals(self, data_list):
        if len(data_list) < 20: return data_list
        for i in range(1, len(data_list)):
            d, prev_d = data_list[i], data_list[i-1]
            price, vol = d['close'], d['volume']
            rsi, macd_hist = d.get('RSI'), d.get('MACD_Hist')
            prev_macd_hist = prev_d.get('MACD_Hist')
            ema50, ema200, vol_sma = d.get('EMA_50'), d.get('EMA_200'), d.get('VOL_SMA')
            d['signal'] = 'NONE'
            if None in [rsi, macd_hist, prev_macd_hist, ema50, ema200, vol_sma]: continue
            if price > ema50 > ema200 and rsi < 40 and macd_hist > prev_macd_hist and vol > (vol_sma * 1.2):
                d['signal'] = 'LONG'
            elif price < ema50 < ema200 and rsi > 60 and macd_hist < prev_macd_hist and vol > (vol_sma * 1.2):
                d['signal'] = 'SHORT'
        return data_list

class Scalper70Strategy(BaseStrategy):
    """
    High-winrate Scalping Strategy (Targeting 70%+).
    Uses EMA 200 for trend, RSI for oversold/overbought, and MACD for momentum confirmation.
    """
    def __init__(self, leverage=20):
        super().__init__(leverage=leverage)

    def calculate_indicators(self, data_list):
        if not data_list: return data_list
        closes = [d['close'] for d in data_list]
        emas_200 = calculate_ema(closes, 200)
        emas_50 = calculate_ema(closes, 50)
        rsi = calculate_rsi(data_list, 14)
        macd, signal, hist = calculate_macd(data_list)
        atrs = calculate_atr(data_list, 14)
        
        for i, d in enumerate(data_list):
            d['EMA_200'] = emas_200[i]
            d['EMA_50'] = emas_50[i]
            d['RSI'] = rsi[i]
            d['MACD_Hist'] = hist[i]
            d['ATR'] = atrs[i]
        return data_list

    def generate_signals(self, data_list):
        if len(data_list) < 200: return data_list
        for i in range(1, len(data_list)):
            d, prev_d = data_list[i], data_list[i-1]
            price = d['close']
            rsi, macd_hist = d.get('RSI'), d.get('MACD_Hist')
            prev_macd_hist = prev_d.get('MACD_Hist')
            ema200, ema50 = d.get('EMA_200'), d.get('EMA_50')
            
            d['signal'] = 'NONE'
            if None in [rsi, macd_hist, prev_macd_hist, ema200, ema50]: continue
            
            # LONG Condition: 
            # 1. Price above EMA 200 (Uptrend)
            # 2. RSI oversold (< 35) or dipping below EMA 50
            # 3. MACD histogram starting to turn up (momentum shift)
            if price > ema200 and rsi < 35 and macd_hist > prev_macd_hist:
                d['signal'] = 'LONG'
            
            # SHORT Condition:
            # 1. Price below EMA 200 (Downtrend)
            # 2. RSI overbought (> 65) or jumping above EMA 50
            # 3. MACD histogram starting to turn down
            elif price < ema200 and rsi > 65 and macd_hist < prev_macd_hist:
                d['signal'] = 'SHORT'
                
        return data_list
