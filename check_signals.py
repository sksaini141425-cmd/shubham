from bot.strategy import Scalper70Strategy
from bot.data_loader import DataLoader

strategy = Scalper70Strategy()
loader = DataLoader()

# Check multiple symbols
symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT']

for symbol in symbols:
    print(f"\n=== {symbol} ===")
    data = loader.fetch_ohlcv(symbol, '1m', 200)
    if len(data) < 200:
        print(f"Insufficient data: {len(data)} candles")
        continue
        
    data_with_indicators = strategy.calculate_indicators(data)
    data_with_signals = strategy.generate_signals(data_with_indicators)
    latest = data_with_signals[-1]
    
    print(f"Price: {latest['close']}")
    print(f"EMA 200: {latest.get('EMA_200', 'N/A')}")
    print(f"RSI: {latest.get('RSI', 'N/A')}")
    print(f"MACD Hist: {latest.get('MACD_Hist', 'N/A')}")
    print(f"Volume: {latest['volume']}")
    print(f"VOL SMA: {latest.get('VOL_SMA', 'N/A')}")
    print(f"Signal: {latest.get('signal', 'NONE')}")
    
    # Check Scalper70 conditions
    if latest.get('EMA_200') and latest.get('RSI') and latest.get('MACD_Hist'):
        price = latest['close']
        ema200 = latest['EMA_200']
        rsi = latest['RSI']
        macd_hist = latest['MACD_Hist']
        volume = latest['volume']
        vol_sma = latest.get('VOL_SMA', 0)
        
        print("\nScalper70 Conditions:")
        print(f"Trend (Price > EMA 200): {price > ema200}")
        print(f"Oversold (RSI < 35): {rsi < 35}")
        print(f"Overbought (RSI > 65): {rsi > 65}")
        print(f"MACD Momentum: {macd_hist > 0 if price > ema200 else macd_hist < 0}")
        print(f"Volume Spike: {volume > vol_sma * 1.2 if vol_sma else False}")
