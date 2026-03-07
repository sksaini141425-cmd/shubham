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

class GridScalperStrategy(BaseStrategy):
    def __init__(self, atr_period=14, sma_period=50, leverage=45):
        super().__init__(leverage=leverage)
        self.atr_period = atr_period
        self.sma_period = sma_period

    def calculate_indicators(self, data_list):
        if not data_list: return data_list
        
        closes = [d['close'] for d in data_list]
        smas = calculate_sma(closes, self.sma_period)
        atrs = calculate_atr(data_list, self.atr_period)
        emas_200 = calculate_ema(closes, 200)
        
        for i, d in enumerate(data_list):
            d['SMA'] = smas[i]
            d['ATR'] = atrs[i]
            d['EMA_200'] = emas_200[i]
            
        return data_list

    def generate_signals(self, data_list):
        lookback = max(self.sma_period, 100)
        if len(data_list) < lookback:
            return data_list
            
        for i in range(1, len(data_list)):
            d = data_list[i]
            price = d['close']
            sma = d.get('SMA')
            atr = d.get('ATR')
            ema_200 = d.get('EMA_200')
            
            d['signal'] = 'NONE'
            
            if sma is None or atr is None:
                continue
                
            min_fee_spacing = price * 0.0025
            grid_spacing = max(atr * 1.5, min_fee_spacing)
            
            # --- TREND FILTER (EMA 200) ---
            # If EMA 200 is not ready, we skip the filter
            if ema_200 is not None:
                # LONG only if ABOVE 200 EMA
                if price < (sma - grid_spacing) and price > ema_200:
                    d['signal'] = 'LONG'
                # SHORT only if BELOW 200 EMA
                elif price > (sma + grid_spacing) and price < ema_200:
                    d['signal'] = 'SHORT'
            else:
                # Fallback if EMA 200 is not ready
                if price < (sma - grid_spacing):
                    d['signal'] = 'LONG'
                elif price > (sma + grid_spacing):
                    d['signal'] = 'SHORT'
                    
        return data_list
