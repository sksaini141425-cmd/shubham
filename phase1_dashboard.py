#!/usr/bin/env python3
"""
Phase 1 Strategy Dashboard - Localhost Backtesting & Monitoring
Run this to test your $3 → $4 strategy in real-time
"""

import os
import sys
import json
import time
import threading
import random
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request
import logging

# Import Phase 1 configuration
from config_phase1 import (
    STARTING_BALANCE, LEVERAGE, RISK_PER_TRADE,
    STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT, MIN_POSITION_VALUE_USDT,
    TRADING_PAIRS, MAX_CONCURRENT_POSITIONS, MAX_DAILY_TRADES,
    PHASE1_TARGETS
)

# Import leverage modules
from leverage_position_sizer import LeveragePositionSizer
from enhanced_paper_exchange import EnhancedPaperExchange

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global variables for trading state
trading_bot = None
is_running = False
trade_history = []
current_positions = []
stats = {
    'starting_balance': STARTING_BALANCE,
    'current_balance': STARTING_BALANCE,
    'total_trades': 0,
    'winning_trades': 0,
    'losing_trades': 0,
    'total_pnl': 0.0,
    'daily_pnl': 0.0,
    'win_rate': 0.0,
    'phase_complete': False,
    'daily_trades': 0,
    'last_trade_time': None
}

class Phase1TradingBot:
    def __init__(self):
        self.exchange = EnhancedPaperExchange(
            initial_balance=STARTING_BALANCE,
            leverage=LEVERAGE
        )
        self.position_sizer = LeveragePositionSizer(
            account_balance=STARTING_BALANCE,
            leverage=LEVERAGE
        )
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.is_running = False
        
    def get_market_price(self, pair):
        """Simulate realistic market price"""
        base_prices = {
            'BTC/USDT': 68000,
            'ETH/USDT': 3200
        }
        base = base_prices.get(pair, 50000)
        # Add random volatility ±2%
        return base * (1 + random.uniform(-0.02, 0.02))
    
    def check_signals(self, pair):
        """Generate trading signals based on indicators"""
        price = self.get_market_price(pair)
        
        # Simple signal logic for demonstration
        rsi = random.uniform(10, 90)  # Simulated RSI
        
        if rsi < 20:  # Oversold
            return 'BUY', price, rsi
        elif rsi > 80:  # Overbought
            return 'SELL', price, rsi
        else:
            return None, price, rsi
    
    def execute_trade(self, pair, signal, entry_price):
        """Execute a trade with Phase 1 parameters"""
        
        # Calculate position size
        if signal == 'BUY':
            stop_loss_price = entry_price * (1 - STOP_LOSS_PERCENT / 100)
        else:
            stop_loss_price = entry_price * (1 + STOP_LOSS_PERCENT / 100)
        
        position = self.position_sizer.calculate_position_size(
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            pair=pair
        )
        
        if not position['meets_minimum']:
            return None, "Position too small"
        
        # Open position
        trade = self.exchange.open_position(
            symbol=pair,
            side='buy' if signal == 'BUY' else 'sell',
            entry_price=entry_price,
            quantity=position['position_size']
        )
        
        # Simulate trade outcome (60% win rate)
        if random.random() < 0.60:
            # Win - hit take profit
            if signal == 'BUY':
                exit_price = entry_price * (1 + TAKE_PROFIT_PERCENT / 100)
            else:
                exit_price = entry_price * (1 - TAKE_PROFIT_PERCENT / 100)
            result = 'WIN'
        else:
            # Loss - hit stop loss
            if signal == 'BUY':
                exit_price = entry_price * (1 - STOP_LOSS_PERCENT / 100)
            else:
                exit_price = entry_price * (1 + STOP_LOSS_PERCENT / 100)
            result = 'LOSS'
        
        # Close position
        self.exchange.update_position_price(trade['id'], exit_price)
        close_result = self.exchange.check_tp_sl(trade['id'], exit_price)
        
        # Calculate P&L
        pnl = (exit_price - entry_price) * position['position_size']
        if signal == 'SELL':
            pnl = -pnl
        
        # Update statistics
        self.daily_trades += 1
        self.total_trades += 1
        self.daily_pnl += pnl
        
        if result == 'WIN':
            self.winning_trades += 1
        
        trade_record = {
            'id': trade['id'],
            'pair': pair,
            'signal': signal,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'quantity': position['position_size'],
            'pnl': pnl,
            'result': result,
            'timestamp': datetime.now().isoformat(),
            'balance': self.exchange.get_account_summary()['balance']
        }
        
        return trade_record, f"{result}: P&L ${pnl:+.4f}"
    
    def run_trading_cycle(self):
        """Run one trading cycle"""
        if self.daily_trades >= MAX_DAILY_TRADES:
            return None, "Max daily trades reached"
        
        # Check daily loss limit
        if self.daily_pnl < -PHASE1_TARGETS['max_daily_loss']:
            return None, "Daily loss limit reached"
        
        # Check each pair for signals
        for pair in TRADING_PAIRS:
            signal, price, rsi = self.check_signals(pair)
            
            if signal:
                trade_record, message = self.execute_trade(pair, signal, price)
                return trade_record, message
        
        return None, "No trading signals"

# HTML Template for Dashboard
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Phase 1 Trading Dashboard - $3 → $4</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0f1419; color: #ffffff; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { text-align: center; margin-bottom: 30px; }
        .header h1 { color: #1da1f2; font-size: 2.5em; margin-bottom: 10px; }
        .header p { color: #8899a6; font-size: 1.1em; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: #192734; padding: 20px; border-radius: 12px; border: 1px solid #38444d; }
        .stat-label { color: #8899a6; font-size: 0.9em; margin-bottom: 5px; }
        .stat-value { font-size: 1.8em; font-weight: bold; }
        .positive { color: #00ff88; }
        .negative { color: #ff4444; }
        .neutral { color: #ffffff; }
        .controls { text-align: center; margin-bottom: 30px; }
        .btn { background: #1da1f2; color: white; border: none; padding: 12px 30px; font-size: 1em; border-radius: 25px; cursor: pointer; margin: 0 10px; transition: all 0.3s; }
        .btn:hover { background: #1a91da; transform: translateY(-2px); }
        .btn.danger { background: #e0245e; }
        .btn.danger:hover { background: #c01e40; }
        .btn:disabled { background: #536471; cursor: not-allowed; transform: none; }
        .trades-section { background: #192734; padding: 20px; border-radius: 12px; border: 1px solid #38444d; }
        .trades-header { font-size: 1.3em; margin-bottom: 15px; color: #1da1f2; }
        .trade-item { background: #0f1419; padding: 15px; margin-bottom: 10px; border-radius: 8px; border-left: 4px solid #1da1f2; }
        .trade-item.win { border-left-color: #00ff88; }
        .trade-item.loss { border-left-color: #ff4444; }
        .trade-info { display: flex; justify-content: space-between; align-items: center; }
        .trade-pair { font-weight: bold; color: #1da1f2; }
        .trade-pnl { font-weight: bold; }
        .progress-bar { background: #38444d; height: 20px; border-radius: 10px; overflow: hidden; margin: 10px 0; }
        .progress-fill { background: linear-gradient(90deg, #1da1f2, #00ff88); height: 100%; transition: width 0.5s; }
        .phase-complete { text-align: center; font-size: 1.5em; color: #00ff88; margin: 20px 0; }
        .auto-trade { background: #192734; padding: 15px; border-radius: 8px; margin: 20px 0; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Phase 1 Trading Dashboard</h1>
            <p>Conservative $3 → $4 Growth Strategy | 2x Leverage | 3% Risk</p>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Current Balance</div>
                <div class="stat-value" id="balance">${{ "%.2f"|format(stats.current_balance) }}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total P&L</div>
                <div class="stat-value {{ 'positive' if stats.total_pnl >= 0 else 'negative' }}" id="pnl">${{ "%.2f"|format(stats.total_pnl) }}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Win Rate</div>
                <div class="stat-value" id="winrate">{{ "%.1f"|format(stats.win_rate) }}%</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total Trades</div>
                <div class="stat-value" id="trades">{{ stats.total_trades }}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Daily P&L</div>
                <div class="stat-value {{ 'positive' if stats.daily_pnl >= 0 else 'negative' }}" id="dailypnl">${{ "%.2f"|format(stats.daily_pnl) }}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Daily Trades</div>
                <div class="stat-value" id="dailytrades">{{ stats.daily_trades }}/{{ MAX_DAILY_TRADES }}</div>
            </div>
        </div>

        <div class="progress-bar">
            <div class="progress-fill" id="progress" style="width: {{ "%.1f"|format(((stats.current_balance - 3) / 1) * 100) }}%"></div>
        </div>
        <div style="text-align: center; margin-bottom: 20px;">
            <span>Progress to $4 Target: {{ "%.1f"|format(((stats.current_balance - 3) / 1) * 100) }}%</span>
        </div>

        {% if stats.phase_complete %}
        <div class="phase-complete">
            🎉 PHASE 1 COMPLETE! Ready for Phase 2 ($4 → $7)
        </div>
        {% endif %}

        <div class="controls">
            <button class="btn" id="startBtn" onclick="startTrading()">Start Trading</button>
            <button class="btn danger" id="stopBtn" onclick="stopTrading()" disabled>Stop Trading</button>
            <button class="btn" onclick="resetSimulation()">Reset Simulation</button>
        </div>

        <div class="auto-trade">
            <label>
                <input type="checkbox" id="autoTrade"> Auto-trade every 5 seconds
            </label>
        </div>

        <div class="trades-section">
            <div class="trades-header">📊 Recent Trades</div>
            <div id="tradesList">
                {% for trade in recent_trades %}
                <div class="trade-item {{ 'win' if trade.result == 'WIN' else 'loss' }}">
                    <div class="trade-info">
                        <div>
                            <span class="trade-pair">{{ trade.pair }}</span>
                            <span style="margin-left: 10px; color: #8899a6;">{{ trade.signal }}</span>
                        </div>
                        <div class="trade-pnl {{ 'positive' if trade.pnl >= 0 else 'negative' }}">
                            ${{ "%.4f"|format(trade.pnl) }} ({{ trade.result }})
                        </div>
                    </div>
                    <div style="color: #8899a6; font-size: 0.9em; margin-top: 5px;">
                        Entry: ${{ "%.2f"|format(trade.entry_price) }} → Exit: ${{ "%.2f"|format(trade.exit_price) }}
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>

    <script>
        let isRunning = false;
        let autoTradeInterval = null;

        function updateStats() {
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('balance').textContent = '$' + data.current_balance.toFixed(2);
                    document.getElementById('pnl').textContent = '$' + data.total_pnl.toFixed(2);
                    document.getElementById('pnl').className = 'stat-value ' + (data.total_pnl >= 0 ? 'positive' : 'negative');
                    document.getElementById('winrate').textContent = data.win_rate.toFixed(1) + '%';
                    document.getElementById('trades').textContent = data.total_trades;
                    document.getElementById('dailypnl').textContent = '$' + data.daily_pnl.toFixed(2);
                    document.getElementById('dailypnl').className = 'stat-value ' + (data.daily_pnl >= 0 ? 'positive' : 'negative');
                    document.getElementById('dailytrades').textContent = data.daily_trades + '/{{ MAX_DAILY_TRADES }}';
                    
                    const progress = ((data.current_balance - 3) / 1) * 100;
                    document.getElementById('progress').style.width = progress + '%';
                    
                    if (data.phase_complete) {
                        document.querySelector('.progress-bar').innerHTML += '<div class="phase-complete">🎉 PHASE 1 COMPLETE!</div>';
                    }
                });
        }

        function updateTrades() {
            fetch('/api/trades')
                .then(response => response.json())
                .then(data => {
                    const tradesList = document.getElementById('tradesList');
                    tradesList.innerHTML = data.map(trade => `
                        <div class="trade-item ${trade.result === 'WIN' ? 'win' : 'loss'}">
                            <div class="trade-info">
                                <div>
                                    <span class="trade-pair">${trade.pair}</span>
                                    <span style="margin-left: 10px; color: #8899a6;">${trade.signal}</span>
                                </div>
                                <div class="trade-pnl ${trade.pnl >= 0 ? 'positive' : 'negative'}">
                                    $${trade.pnl.toFixed(4)} (${trade.result})
                                </div>
                            </div>
                            <div style="color: #8899a6; font-size: 0.9em; margin-top: 5px;">
                                Entry: $${trade.entry_price.toFixed(2)} → Exit: $${trade.exit_price.toFixed(2)}
                            </div>
                        </div>
                    `).join('');
                });
        }

        function startTrading() {
            fetch('/api/start', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    isRunning = true;
                    document.getElementById('startBtn').disabled = true;
                    document.getElementById('stopBtn').disabled = false;
                    
                    if (document.getElementById('autoTrade').checked) {
                        autoTradeInterval = setInterval(() => {
                            fetch('/api/trade', {method: 'POST'});
                        }, 5000);
                    }
                });
        }

        function stopTrading() {
            fetch('/api/stop', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    isRunning = false;
                    document.getElementById('startBtn').disabled = false;
                    document.getElementById('stopBtn').disabled = true;
                    
                    if (autoTradeInterval) {
                        clearInterval(autoTradeInterval);
                        autoTradeInterval = null;
                    }
                });
        }

        function resetSimulation() {
            if (confirm('Reset all trading data and start over?')) {
                fetch('/api/reset', {method: 'POST'})
                    .then(response => response.json())
                    .then(data => {
                        location.reload();
                    });
            }
        }

        // Auto-update every 2 seconds
        setInterval(() => {
            updateStats();
            updateTrades();
        }, 2000);

        // Initial load
        updateStats();
        updateTrades();
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE, stats=stats, recent_trades=trade_history[-10:], MAX_DAILY_TRADES=MAX_DAILY_TRADES)

@app.route('/api/stats')
def get_stats():
    if trading_bot:
        summary = trading_bot.exchange.get_account_summary()
        stats.update({
            'current_balance': summary['balance'],
            'total_trades': trading_bot.total_trades,
            'winning_trades': trading_bot.winning_trades,
            'losing_trades': trading_bot.total_trades - trading_bot.winning_trades,
            'total_pnl': summary['balance'] - STARTING_BALANCE,
            'daily_pnl': trading_bot.daily_pnl,
            'win_rate': (trading_bot.winning_trades / trading_bot.total_trades * 100) if trading_bot.total_trades > 0 else 0,
            'phase_complete': summary['balance'] >= PHASE1_TARGETS['phase_complete_balance'],
            'daily_trades': trading_bot.daily_trades
        })
    return jsonify(stats)

@app.route('/api/trades')
def get_trades():
    return jsonify(trade_history[-20:])

@app.route('/api/start', methods=['POST'])
def start_trading():
    global trading_bot, is_running
    if not trading_bot:
        trading_bot = Phase1TradingBot()
    is_running = True
    trading_bot.is_running = True
    return jsonify({'status': 'started'})

@app.route('/api/stop', methods=['POST'])
def stop_trading():
    global is_running
    is_running = False
    if trading_bot:
        trading_bot.is_running = False
    return jsonify({'status': 'stopped'})

@app.route('/api/trade', methods=['POST'])
def execute_trade():
    global trading_bot, trade_history
    
    if not trading_bot or not trading_bot.is_running:
        return jsonify({'error': 'Trading not started'})
    
    trade_record, message = trading_bot.run_trading_cycle()
    
    if trade_record:
        trade_history.append(trade_record)
        stats['last_trade_time'] = datetime.now().isoformat()
        
        # Check if phase is complete
        if trade_record['balance'] >= PHASE1_TARGETS['phase_complete_balance']:
            trading_bot.is_running = False
            stats['phase_complete'] = True
    
    return jsonify({
        'trade': trade_record,
        'message': message,
        'stats': stats
    })

@app.route('/api/reset', methods=['POST'])
def reset_simulation():
    global trading_bot, trade_history, stats, is_running
    
    # Reset global state
    trading_bot = None
    trade_history = []
    is_running = False
    stats = {
        'starting_balance': STARTING_BALANCE,
        'current_balance': STARTING_BALANCE,
        'total_trades': 0,
        'winning_trades': 0,
        'losing_trades': 0,
        'total_pnl': 0.0,
        'daily_pnl': 0.0,
        'win_rate': 0.0,
        'phase_complete': False,
        'daily_trades': 0,
        'last_trade_time': None
    }
    
    return jsonify({'status': 'reset'})

def main():
    print("🚀 Starting Phase 1 Trading Dashboard...")
    print("📊 Strategy: $3 → $4 Conservative Growth")
    print("⚙️  Parameters: 2x Leverage, 3% Risk, 60% Win Rate Target")
    print("\n🌐 Open your browser and go to: http://localhost:5000")
    print("📱 Use the dashboard to:")
    print("   • Start/Stop trading simulation")
    print("   • Monitor real-time P&L")
    print("   • View trade history")
    print("   • Track progress to $4 target")
    print("\nPress Ctrl+C to stop the server")
    
    app.run(host='0.0.0.0', port=5000, debug=False)

if __name__ == '__main__':
    main()
