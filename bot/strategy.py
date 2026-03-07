import logging

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
    # Filter out None values for EMA calculation
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
    
    import math
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
            d['MACD'] = macd[i]
            d['MACD_Signal'] = signal[i]
            d['MACD_Hist'] = hist[i]
            d['BB_Upper'] = upper[i]
            d['BB_Middle'] = middle[i]
            d['BB_Lower'] = lower[i]
            
        return data_list

    def generate_signals(self, data_list):
        lookback = 200 # Need 200 EMA to be valid
        if len(data_list) < lookback:
            return data_list
            
        for i in range(1, len(data_list)):
            d = data_list[i]
            prev_d = data_list[i-1]
            price = d['close']
            ema_200 = d.get('EMA_200')
            rsi = d.get('RSI')
            macd_hist = d.get('MACD_Hist')
            prev_macd_hist = prev_d.get('MACD_Hist')
            bb_lower = d.get('BB_Lower')
            bb_upper = d.get('BB_Upper')
            
            d['signal'] = 'NONE'
            
            # Require all indicators to be warmed up
            if None in [ema_200, rsi, macd_hist, prev_macd_hist, bb_lower, bb_upper]:
                continue
                
            # --- SMART MONEY CONTINUATION LOGIC ---
            # LONG SETUP: 
            # 1. Price is generally above 200 EMA (Uptrend)
            # 2. Price touches or goes slightly below BB Lower Band (Pullback)
            # 3. RSI is recovering from oversold (< 45) but not overbought (< 70)
            # 4. MACD Histogram is crossing up (Momentum shift to bullish)
            if price > ema_200 and price <= (bb_lower * 1.002): # Pulled back to bottom band
                if rsi < 45 and (macd_hist > prev_macd_hist): 
                    d['signal'] = 'LONG'
                    
            # SHORT SETUP:
            # 1. Price is generally below 200 EMA (Downtrend)
            # 2. Price touches or goes slightly above BB Upper Band (Fake rally)
            # 3. RSI is rejecting from overbought (> 55) but not oversold (> 30)
            # 4. MACD Histogram is crossing down (Momentum shift to bearish)
            elif price < ema_200 and price >= (bb_upper * 0.998): # Rallied to top band
                if rsi > 55 and (macd_hist < prev_macd_hist):
                    d['signal'] = 'SHORT'
                    
        return data_list
