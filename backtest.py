import logging
from bot.data_loader import DataLoader
from bot.strategy import SmartMoneyStrategy
from bot.paper_exchange import PaperExchange

# Setup Logging for Backtest Output
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("Backtester")

def run_backtest(symbol='BTCUSDT', timeframe='1m', limit=5000, leverage=45, initial_capital=3.0, atr_period=24, sma_period=100):
    logger.info("=" * 60)
    logger.info(f"STARTING BACKTEST: {symbol} | {timeframe} | {limit} Candles")
    logger.info(f"Strategy: SmartMoney | Leverage: {leverage}x")
    logger.info("=" * 60)

    # 1. Initialize Components
    data_loader = DataLoader(exchange_id='binanceusdm', testnet=False)
    strategy = SmartMoneyStrategy(leverage=leverage)
    exchange = PaperExchange(initial_capital=initial_capital)

    # 2. Fetch Historical Data (Batch)
    data = data_loader.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    if not data:
        logger.error("Failed to fetch historical data. Aborting.")
        return

    # 3. Calculate Indicators and Signals for the entire dataset at once
    data = strategy.calculate_indicators(data)
    data = strategy.generate_signals(data)

    # 4. Simulate Execution loop over historical candles
    total_trades = 0
    winning_trades = 0
    losing_trades = 0
    
    # Risk Management: Hard Stop Loss (0.5%)
    stop_loss_pct = 0.005

    for i in range(len(data)):
        candle = data[i]
        current_price = candle['close']
        timestamp = candle['timestamp']
        signal = candle.get('signal', 'WAIT')
        sma = candle.get('SMA')

        # If in position, check for mean reversion (Price touches SMA), reversal, or Hard Stop Loss
        if exchange.is_in_position and sma is not None:
            close_position = False
            
            # 1. Take Profit / Mean Reversion Exit
            if exchange.position_direction == 'LONG':
                if current_price >= sma or signal == 'SHORT':
                    close_position = True
                    
            elif exchange.position_direction == 'SHORT':
                if current_price <= sma or signal == 'LONG':
                    close_position = True
            
            # 2. Hard Stop Loss Exit (Safety First)
            unrealized_pnl_pct = exchange.get_unrealized_pnl(current_price) / (exchange.position_size * exchange.entry_price)
            if unrealized_pnl_pct <= -stop_loss_pct:
                close_position = True
                logger.warning(f"[{timestamp}] STOP LOSS TRIGGERED at {current_price:.2f}")

            if close_position:
                # Check if it was a win or loss before closing
                pnl = exchange.get_unrealized_pnl(current_price)
                if pnl > 0:
                    winning_trades += 1
                else:
                    losing_trades += 1
                total_trades += 1
                
                exchange.execute_market_order('CLOSE', exchange.position_size, current_price, timestamp)

        # Evaluate opening new positions
        if not exchange.is_in_position and signal in ['LONG', 'SHORT']:
            # Calculate size to meet Binance $131 Minimum Notional
            target_notional = 131.0
            size = target_notional / current_price
            
            # Use Limit Orders (Maker Fee) for Grid Strategy entries
            if exchange.cash * leverage >= target_notional:
                # We use maker_fee for opening (Limit orders) and taker_fee for closing (emergency/market)
                exchange.taker_fee = 0.0002 # Set to Maker Rate for this simulation
                exchange.execute_market_order(signal, size, current_price, timestamp)
                # Reset to Taker for safety closures
                exchange.taker_fee = 0.0005

    # 5. Close any open position at the end of the test
    if exchange.is_in_position:
        logger.info("\n--- Closing final open position for end of backtest ---")
        pnl = exchange.get_unrealized_pnl(current_price)
        if pnl > 0: winning_trades += 1
        else: losing_trades += 1
        total_trades += 1
        exchange.execute_market_order('CLOSE', exchange.position_size, current_price, timestamp)

    # 6. Calculate Metrics
    final_balance = exchange.cash
    net_profit = final_balance - initial_capital
    profit_percentage = (net_profit / initial_capital) * 100
    win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0.0

    logger.info("=" * 60)
    logger.info("BACKTEST RESULTS")
    logger.info("=" * 60)
    report = f"""
============================================================
BACKTEST RESULTS: {symbol}
============================================================
Starting Capital : ${initial_capital:.2f}
Final Capital    : ${final_balance:.2f}
Net Profit       : ${net_profit:.2f} ({profit_percentage:.2f}%)
Total Trades     : {total_trades}
Win Rate         : {win_rate:.2f}% ({winning_trades} W / {losing_trades} L)
============================================================
"""
    print(report)
    with open("final_report.txt", "w") as f:
        f.write(report)

if __name__ == "__main__":
    run_backtest()
