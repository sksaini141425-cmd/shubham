"""
Real Binance Exchange Integration
Replace fake simulated trading with real Binance API
"""

import ccxt
import os
import logging
from dotenv import load_dotenv
import time
from datetime import datetime

logger = logging.getLogger(__name__)

class RealBinanceExchange:
    def __init__(self, use_testnet=True):
        """
        Initialize real Binance exchange connection
        use_testnet: Start with True for safety
        """
        load_dotenv()  # Load from .env file
        
        # Get API keys from environment (secure)
        api_key = os.getenv('BINANCE_API_KEY')
        secret = os.getenv('BINANCE_SECRET')
        
        if not api_key or not secret:
            raise ValueError("Please set BINANCE_API_KEY and BINANCE_SECRET in .env file")
        
        # Configure exchange
        if use_testnet:
            # Binance Testnet (safe for testing)
            self.exchange = ccxt.binance({
                'apiKey': api_key,
                'secret': secret,
                'sandbox': True,
                'urls': {
                    'api': {
                        'public': 'https://testnet.binance.vision/api/v3',
                        'private': 'https://testnet.binance.vision/api/v3',
                    }
                }
            })
            logger.info("🧪 Connected to Binance TESTNET")
        else:
            # Real Binance (use with small amounts!)
            self.exchange = ccxt.binance({
                'apiKey': api_key,
                'secret': secret,
                'enableRateLimit': True,
            })
            logger.info("🚀 Connected to Binance LIVE")
        
        self.balance = 0.0
        self.positions = []
        
    def get_account_summary(self):
        """Get real account balance"""
        try:
            balance = self.exchange.fetch_balance()
            usdt_balance = balance['USDT']['free'] if 'USDT' in balance['free'] else 0
            self.balance = usdt_balance
            
            return {
                'balance': usdt_balance,
                'total': balance['USDT']['total'] if 'USDT' in balance['total'] else 0,
                'used': balance['USDT']['used'] if 'USDT' in balance['used'] else 0,
                'free': usdt_balance
            }
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            return {'balance': 0, 'total': 0, 'used': 0, 'free': 0}
    
    def get_real_market_data(self, symbol):
        """
        Replace fake market data with real Binance data
        """
        try:
            # Get real ticker data
            ticker = self.exchange.fetch_ticker(symbol)
            
            # Get OHLCV for indicators
            ohlcv = self.exchange.fetch_ohlcv(symbol, '15m', limit=200)  # 200 candles
            
            # Calculate EMAs from real data
            closes = [candle[4] for candle in ohlcv]  # Close prices
            ema_20 = self.calculate_ema(closes, 20)
            ema_50 = self.calculate_ema(closes, 50)
            ema_200 = self.calculate_ema(closes, 200)
            
            # Calculate ATR
            atr = self.calculate_atr(ohlcv, 14)
            
            # Generate signal based on real EMA alignment
            signal = self.generate_signal_from_ema(ticker['last'], ema_20, ema_50, ema_200)
            
            return {
                'symbol': symbol,
                'price': ticker['last'],
                'signal': signal,
                'signal_strength': self.calculate_signal_strength(signal, ema_20, ema_50, ema_200, ticker['last']),
                'ema_fast': ema_20,
                'ema_mid': ema_50,
                'ema_slow': ema_200,
                'atr': atr,
                'volume': ticker['baseVolume'],
                'change': ticker['percentage'],
                'high': ticker['high'],
                'low': ticker['low']
            }
            
        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
            return None
    
    def calculate_ema(self, prices, period):
        """Calculate EMA from real price data"""
        if len(prices) < period:
            return prices[-1] if prices else 0
        
        multiplier = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def calculate_atr(self, ohlcv, period):
        """Calculate ATR from real OHLCV data"""
        if len(ohlcv) < period + 1:
            return 0
        
        tr_values = []
        for i in range(1, len(ohlcv)):
            high = ohlcv[i][2]
            low = ohlcv[i][3]
            prev_close = ohlcv[i-1][4]
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            tr_values.append(tr)
        
        return sum(tr_values[-period:]) / period
    
    def generate_signal_from_ema(self, price, ema_20, ema_50, ema_200):
        """Generate signal from real EMA alignment (Futures-Bot Strategy)"""
        if price > ema_200:  # Uptrend
            if price < ema_20 and ema_20 < ema_50:  # Pullback to EMAs
                return 'BUY'
        elif price < ema_200:  # Downtrend
            if price > ema_20 and ema_20 > ema_50:  # Pullback to EMAs
                return 'SELL'
        
        return 'NEUTRAL'
    
    def calculate_signal_strength(self, signal, ema_20, ema_50, ema_200, price):
        """Calculate signal strength based on real market conditions"""
        if signal == 'NEUTRAL':
            return 1.0
        
        # Distance from EMAs (pullback strength)
        ema_distance = abs(price - ema_20) / price * 100
        
        # EMA alignment strength
        if signal == 'BUY':
            alignment = (ema_200 - ema_50) / ema_200 * 100 + (ema_50 - ema_20) / ema_50 * 100
        else:
            alignment = (ema_50 - ema_200) / ema_200 * 100 + (ema_20 - ema_50) / ema_50 * 100
        
        # Combine factors
        strength = min(10.0, max(1.0, ema_distance * 2 + alignment * 3))
        
        return strength
    
    def open_position(self, symbol, side, entry_price, quantity):
        """Open real position on Binance"""
        try:
            # Create market order
            if side == 'buy':
                order = self.exchange.create_market_buy_order(symbol, quantity)
            else:
                order = self.exchange.create_market_sell_order(symbol, quantity)
            
            position = {
                'id': str(order['id']),
                'symbol': symbol,
                'side': side,
                'entry_price': entry_price,
                'quantity': quantity,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"✅ Real position opened: {symbol} {side} {quantity} @ {entry_price}")
            return position
            
        except Exception as e:
            logger.error(f"❌ Failed to open position: {e}")
            raise e
    
    def close_position(self, position_id, symbol, quantity):
        """Close real position on Binance"""
        try:
            # Create opposite market order
            current_position = next((p for p in self.positions if p['id'] == position_id), None)
            if not current_position:
                raise ValueError("Position not found")
            
            opposite_side = 'sell' if current_position['side'] == 'buy' else 'buy'
            order = self.exchange.create_market_order(symbol, opposite_side, quantity)
            
            logger.info(f"✅ Real position closed: {symbol} {opposite_side} {quantity}")
            return order
            
        except Exception as e:
            logger.error(f"❌ Failed to close position: {e}")
            raise e
    
    def update_position_price(self, position_id, current_price):
        """Update position with current market price"""
        for pos in self.positions:
            if pos['id'] == position_id:
                pos['current_price'] = current_price
                break
    
    def check_tp_sl(self, position_id, current_price):
        """Check if TP/SL hit for real position"""
        for pos in self.positions:
            if pos['id'] == position_id:
                # Calculate P&L
                if pos['side'] == 'buy':
                    pnl = (current_price - pos['entry_price']) * pos['quantity']
                else:
                    pnl = (pos['entry_price'] - current_price) * pos['quantity']
                
                return {
                    'pnl': pnl,
                    'exit_price': current_price,
                    'reason': 'TP/SL_HIT'
                }
        return None

# Usage example (you'll add your keys in .env)
if __name__ == "__main__":
    # Start with testnet for safety
    exchange = RealBinanceExchange(use_testnet=True)
    
    # Test connection
    balance = exchange.get_account_summary()
    print(f"Account Balance: ${balance['balance']}")
    
    # Test market data
    btc_data = exchange.get_real_market_data('BTC/USDT')
    if btc_data:
        print(f"BTC Price: ${btc_data['price']}")
        print(f"Signal: {btc_data['signal']} (Strength: {btc_data['signal_strength']:.1f})")
