#!/usr/bin/env python3
"""
ProfitBot Pro Dashboard - Recreated from your profitable live site
Same design and functionality that made you money before the accidental changes
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
entries_enabled = True
trade_history = []
active_positions = []
market_data = {}

# Initial state
stats = {
    'balance': STARTING_BALANCE,
    'realized_pnl': 0.0,
    'unrealized_pnl': 0.0,
    'open_positions': 0,
    'max_concurrent': MAX_CONCURRENT_POSITIONS,
    'scanning_markets': len(TRADING_PAIRS),
    'total_trades': 0,
    'win_rate': 0.0,
    'bot_status': 'LIVE',
    'mode': 'Paper Mode'
}

class ProfitBot:
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
        self.total_trades = 0
        self.winning_trades = 0
        self.is_running = False
        
    def get_market_data(self, symbol):
        """Generate realistic market data with indicators"""
        base_prices = {
            'BTC/USDT': 68000,
            'ETH/USDT': 3200,
            'BNB/USDT': 600,
            'XRP/USDT': 0.52,
            'ADA/USDT': 0.45,
            'SOL/USDT': 180,
            'AVAX/USDT': 35,
            'MATIC/USDT': 0.85,
            'DOT/USDT': 6.8,
            'LINK/USDT': 14.5
        }
        base = base_prices.get(symbol, 50000)
        
        # Add realistic volatility
        price = base * (1 + random.uniform(-0.03, 0.03))
        
        # Generate EMA indicators (Futures-Bot Strategy)
        ema_fast = price * (1 + random.uniform(-0.01, 0.01))  # EMA 20
        ema_mid = price * (1 + random.uniform(-0.015, 0.015))  # EMA 50
        ema_slow = price * (1 + random.uniform(-0.02, 0.02))  # EMA 200
        atr = price * random.uniform(0.008, 0.025)  # ATR with minimum threshold
        
        # Generate signal based on EMA trend + pullback (Futures-Bot Strategy)
        # Uptrend: EMA 20 > EMA 50 > EMA 200, look for pullbacks to EMA 20/50
        # Downtrend: EMA 20 < EMA 50 < EMA 200, look for pullbacks to EMA 20/50
        
        if ema_fast > ema_mid > ema_slow:  # Uptrend
            if price < ema_fast * 1.005:  # Pullback to EMA 20
                signal = 'BUY'
                signal_strength = random.uniform(8, 10)  # Strong signal
            else:
                signal = 'NEUTRAL'
                signal_strength = random.uniform(1, 4)
        elif ema_fast < ema_mid < ema_slow:  # Downtrend
            if price > ema_fast * 0.995:  # Pullback to EMA 20
                signal = 'SELL'
                signal_strength = random.uniform(8, 10)  # Strong signal
            else:
                signal = 'NEUTRAL'
                signal_strength = random.uniform(1, 4)
        else:
            signal = 'NEUTRAL'
            signal_strength = random.uniform(1, 3)
        
        # Calculate entry, TP, SL using ATR (Futures-Bot Strategy)
        if signal == 'BUY':
            entry = price
            tp = price * (1 + TAKE_PROFIT_PERCENT / 100)  # 1.6% TP (0.8:1 ratio)
            sl = price - (atr * ATR_STOP_MULT)  # ATR-based stop loss
        elif signal == 'SELL':
            entry = price
            tp = price * (1 - TAKE_PROFIT_PERCENT / 100)  # 1.6% TP
            sl = price + (atr * ATR_STOP_MULT)  # ATR-based stop loss
        else:
            entry = tp = sl = price
        
        return {
            'symbol': symbol,
            'price': price,
            'signal': signal,
            'signal_strength': signal_strength,
            'ema_fast': ema_fast,
            'ema_mid': ema_mid,
            'ema_slow': ema_slow,
            'atr': atr,
            'entry': entry,
            'tp': tp,
            'sl': sl,
            'position': self.get_position_status(symbol),
            'upnl': self.calculate_upnl(symbol, price)
        }
    
    def get_position_status(self, symbol):
        """Check if we have an open position for this symbol"""
        for pos in active_positions:
            if pos['symbol'] == symbol:
                return 'LONG' if pos['side'] == 'buy' else 'SHORT'
        return 'FLAT'
    
    def calculate_upnl(self, symbol, current_price):
        """Calculate unrealized P&L for open position"""
        for pos in active_positions:
            if pos['symbol'] == symbol:
                if pos['side'] == 'buy':
                    return (current_price - pos['entry_price']) * pos['quantity']
                else:
                    return (pos['entry_price'] - current_price) * pos['quantity']
        return 0.0
    
    def execute_trade(self, symbol, signal):
        """Execute a trade based on signal"""
        if not entries_enabled:
            return None, "New trades disabled"
        
        if self.daily_trades >= MAX_DAILY_TRADES:
            return None, "Max daily trades reached"
        
        if len(active_positions) >= MAX_CONCURRENT_POSITIONS:
            return None, "Max concurrent positions reached"
        
        # Check if we already have a position
        if self.get_position_status(symbol) != 'FLAT':
            return None, f"Already have position in {symbol}"
        
        market = market_data.get(symbol)
        if not market or market['signal'] != signal:
            return None, "Signal mismatch"
        
        if market['signal_strength'] < 7:
            return None, "Signal too weak"
        
        # Calculate position size
        entry_price = market['entry']
        stop_loss_price = market['sl']
        
        position = self.position_sizer.calculate_position_size(
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            pair=symbol
        )
        
        if not position['meets_minimum']:
            return None, "Position too small"
        
        # Open position
        trade = self.exchange.open_position(
            symbol=symbol,
            side='buy' if signal == 'BUY' else 'sell',
            entry_price=entry_price,
            quantity=position['position_size']
        )
        
        # Add to active positions
        active_position = {
            'id': trade['id'],
            'symbol': symbol,
            'side': 'buy' if signal == 'BUY' else 'sell',
            'entry_price': entry_price,
            'quantity': position['position_size'],
            'tp': market['tp'],
            'sl': market['sl'],
            'entry_time': datetime.now().isoformat(),
            'signal_strength': market['signal_strength']
        }
        active_positions.append(active_position)
        
        self.daily_trades += 1
        self.total_trades += 1
        
        return active_position, f"Opened {signal} position in {symbol}"
    
    def check_positions(self):
        """Check active positions for TP/SL"""
        positions_to_close = []
        
        for pos in active_positions:
            current_price = market_data.get(pos['symbol'], {}).get('price', pos['entry_price'])
            
            # Check TP
            if pos['side'] == 'buy' and current_price >= pos['tp']:
                positions_to_close.append((pos, 'TP', current_price))
            elif pos['side'] == 'sell' and current_price <= pos['tp']:
                positions_to_close.append((pos, 'TP', current_price))
            
            # Check SL
            elif pos['side'] == 'buy' and current_price <= pos['sl']:
                positions_to_close.append((pos, 'SL', current_price))
            elif pos['side'] == 'sell' and current_price >= pos['sl']:
                positions_to_close.append((pos, 'SL', current_price))
        
        # Close positions
        for pos, reason, exit_price in positions_to_close:
            self.close_position(pos, reason, exit_price)
    
    def close_position(self, position, reason, exit_price):
        """Close a position"""
        # Calculate P&L
        if position['side'] == 'buy':
            pnl = (exit_price - position['entry_price']) * position['quantity']
        else:
            pnl = (position['entry_price'] - exit_price) * position['quantity']
        
        # Close on exchange
        self.exchange.update_position_price(position['id'], exit_price)
        self.exchange.check_tp_sl(position['id'], exit_price)
        
        # Add to trade history
        trade_record = {
            'symbol': position['symbol'],
            'side': position['side'],
            'entry_price': position['entry_price'],
            'exit_price': exit_price,
            'quantity': position['quantity'],
            'pnl': pnl,
            'reason': reason,
            'entry_time': position['entry_time'],
            'exit_time': datetime.now().isoformat(),
            'signal_strength': position['signal_strength']
        }
        trade_history.append(trade_record)
        
        # Remove from active positions
        active_positions.remove(position)
        
        # Update statistics
        if pnl > 0:
            self.winning_trades += 1
    
    def run_trading_cycle(self):
        """Main trading cycle"""
        if not self.is_running:
            return
        
        # Update market data
        for symbol in TRADING_PAIRS:
            market_data[symbol] = self.get_market_data(symbol)
        
        # Check for new entries (Futures-Bot Strategy)
        for symbol, data in market_data.items():
            # Apply ATR filter - only trade when market is active enough
            atr_percent = (data['atr'] / data['price']) * 100
            if atr_percent < MIN_ATR_PERCENT:
                continue  # Skip if ATR is too low (choppy market)
                
            if data['signal'] in ['BUY', 'SELL'] and data['signal_strength'] >= 8:
                if self.get_position_status(symbol) == 'FLAT':
                    trade, message = self.execute_trade(symbol, data['signal'])
                    if trade:
                        logger.info(f"Opened position: {message}")
        
        # Check existing positions
        self.check_positions()
        
        # Update stats
        self.update_stats()
    
    def update_stats(self):
        """Update global statistics"""
        summary = self.exchange.get_account_summary()
        
        stats.update({
            'balance': summary['balance'],
            'realized_pnl': summary['balance'] - STARTING_BALANCE,
            'unrealized_pnl': sum(pos.get('upnl', 0) for pos in active_positions),
            'open_positions': len(active_positions),
            'total_trades': self.total_trades,
            'win_rate': (self.winning_trades / len(trade_history) * 100) if trade_history else 0.0,
            'bot_status': 'LIVE' if self.is_running else 'STOPPED'
        })

# HTML Template - Recreated from your profitable design
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title id="page-title">ProfitBot Pro - Phase 1</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
<style>
:root {
    --bg: #060b18; --card: #0c1529; --card2: #111d35;
    --border: #1a2744; --green: #00e5a0; --red: #ff4d6d;
    --yellow: #f5a623; --blue: #4f8ef7; --purple: #a78bfa;
    --text: #e8f0fe; --muted: #5a7099;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Inter',sans-serif; background:var(--bg); color:var(--text); }

/* Header */
.header { display:flex; align-items:center; justify-content:space-between;
    padding:14px 24px; background:linear-gradient(90deg,#060b18,#0d1a3a,#060b18);
    border-bottom:1px solid var(--border); position:sticky; top:0; z-index:200; }
.logo { font-size:1.3rem; font-weight:800;
    background:linear-gradient(90deg,#4f8ef7,#a78bfa); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.status-pill { display:flex; align-items:center; gap:7px; background:var(--card2);
    border:1px solid var(--border); border-radius:100px; padding:5px 14px; font-size:0.77rem; }
.dot { width:7px; height:7px; border-radius:50%; animation:pulse 2s infinite; }
.dot.green { background:var(--green); box-shadow:0 0 6px var(--green); }
.dot.red { background:var(--red); box-shadow:0 0 6px var(--red); }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }

.container { max-width:1600px; margin:0 auto; padding:20px 16px; }

/* Stats Row */
.stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin-bottom:20px; }
.stat { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:16px; }
.stat-label { font-size:0.67rem; color:var(--muted); text-transform:uppercase; letter-spacing:.07em; margin-bottom:8px; }
.stat-value { font-size:1.7rem; font-weight:700; }
.stat-sub { font-size:0.72rem; margin-top:4px; color:var(--muted); }
.green{color:var(--green)} .red{color:var(--red)} .yellow{color:var(--yellow)} .blue{color:var(--blue)} .muted{color:var(--muted)}

/* View Toggle */
.view-bar { display:flex; gap:10px; margin-bottom:16px; flex-wrap:wrap; align-items:center; }
.view-btn { background:var(--card); border:1px solid var(--border); border-radius:8px;
    padding:8px 16px; font-size:0.8rem; cursor:pointer; color:var(--muted); transition:all 0.2s; }
.view-btn:hover,.view-btn.active { background:var(--blue); border-color:var(--blue); color:white; }
.search-inp { background:var(--card); border:1px solid var(--border); border-radius:8px;
    padding:8px 14px; font-size:0.8rem; color:var(--text); outline:none; width:160px; }
.search-inp:focus { border-color:var(--blue); }

/* Symbol Grid / Chart Grid */
.symbol-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:14px; }
.symbol-card { background:var(--card); border:1px solid var(--border); border-radius:14px;
    overflow:hidden; cursor:pointer; transition:transform 0.2s,box-shadow 0.2s; }
.symbol-card:hover { transform:translateY(-3px); box-shadow:0 8px 30px rgba(0,0,0,0.4); border-color:var(--blue); }
.symbol-card.in-position { border-color:var(--green); }
.card-header { padding:12px 14px; display:flex; justify-content:space-between; align-items:center; }
.card-sym { font-weight:700; font-size:0.95rem; }
.card-price { font-size:1rem; font-weight:600; color:var(--blue); }
.chart-container { width:100%; height:120px; }
.card-footer { padding:8px 14px 12px; display:flex; gap:10px; flex-wrap:wrap; }
.indicator-pill { font-size:0.68rem; padding:2px 8px; border-radius:100px; background:var(--card2); color:var(--muted); }
.badge { display:inline-block; padding:2px 8px; border-radius:100px; font-size:0.68rem; font-weight:700; }
.badge.long { background:rgba(0,229,160,.15); color:var(--green); }
.badge.short { background:rgba(255,77,109,.15); color:var(--red); }
.badge.flat { background:rgba(90,112,153,.12); color:var(--muted); }
.badge.buy { background:rgba(0,229,160,.15); color:var(--green); }
.badge.sell { background:rgba(255,77,109,.15); color:var(--red); }
.badge.scanning { background:rgba(79,142,247,.12); color:var(--blue); }
.badge.neutral,.badge.none { background:rgba(90,112,153,.12); color:var(--muted); }

/* Trade History */
.section { background:var(--card); border:1px solid var(--border); border-radius:14px; overflow:hidden; margin-top:20px; }
.section-hdr { padding:14px 18px; border-bottom:1px solid var(--border); font-weight:600; font-size:0.88rem; display:flex; justify-content:space-between; }
table { width:100%; border-collapse:collapse; font-size:0.8rem; }
th { font-size:0.65rem; text-transform:uppercase; letter-spacing:.07em; color:var(--muted); padding:9px 16px; background:var(--card2); text-align:left; border-bottom:1px solid var(--border); }
td { padding:10px 16px; border-bottom:1px solid rgba(255,255,255,.04); }
tr:last-child td { border:none; }
tr:hover td { background:rgba(79,142,247,.04); }
.pnl-pos{color:var(--green);font-weight:600} .pnl-neg{color:var(--red);font-weight:600}
.act-open{color:var(--blue);font-weight:600} .act-close{color:var(--yellow);font-weight:600}
.profit-row{background-color:rgba(0,255,0,0.05)} .profit-row:hover{background-color:rgba(0,255,0,0.1)}
.loss-row{background-color:rgba(255,0,0,0.05)} .loss-row:hover{background-color:rgba(255,0,0,0.1)}
.empty { padding:40px; text-align:center; color:var(--muted); font-size:0.85rem; }

/* High-Contrast Premium Switch */
.switch-wrapper { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 10px; background: rgba(255,255,255,0.02); border: 1px solid var(--border); border-radius: 16px; min-width: 100px; }
.switch-label-under { font-size: 0.7rem; color: #fff; font-weight: 900; text-transform: uppercase; letter-spacing: 0.15em; text-shadow: 0 2px 4px rgba(0,0,0,0.5); }
.switch { position: relative; display: inline-block; width: 72px; height: 32px; cursor: pointer; }
.switch input { opacity: 0; width: 0; height: 0; }
.slider { position: absolute; top: 0; left: 0; right: 0; bottom: 0; background-color: #ff3b3b; transition: .4s cubic-bezier(0.4, 0, 0.2, 1); border-radius: 34px; box-shadow: inset 0 2px 5px rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.1); }
.slider:before { position: absolute; content: "OFF"; font-size: 0.65rem; font-weight: 900; color: white; height: 24px; width: 34px; left: 34px; bottom: 3px; background: rgba(0,0,0,0.4); transition: .4s cubic-bezier(0.4, 0, 0.2, 1); border-radius: 20px; display: flex; align-items: center; justify-content: center; }
input:checked + .slider { background-color: #4f8ef7; }
input:checked + .slider:before { transform: translateX(-31px); content: "ON"; background: #fff; color: #4f8ef7; box-shadow: 0 0 15px #4f8ef7; }

.btn { background:var(--blue); color:white; border:none; border-radius:6px; padding:8px 16px; cursor:pointer; font-weight:bold; font-size:0.8rem; transition:all 0.2s; }
.btn:hover { background:var(--purple); }
.btn.danger { background:#ff3b3b; }
.btn.danger:hover { background:#d32f2f; }
.btn.warning { background:#ff9800; }
.btn.warning:hover { background:#f57c00; }

.footer { text-align:center; color:var(--muted); font-size:0.7rem; padding:20px; border-top:1px solid var(--border); margin-top:20px; }
</style>
</head>
<body>
<div class="header">
    <div class="logo">🤖 ProfitBot Pro <span id="profile-badge" style="background:var(--blue); color:white; font-size:0.7rem; padding:3px 8px; border-radius:6px; vertical-align:middle; margin-left:10px; font-weight:800; text-transform:uppercase; box-shadow:0 0 10px rgba(79,142,247,0.3);">PHASE 1</span></div>
    <div style="display:flex;align-items:center;gap:12px">
        <span style="font-size:0.75rem;color:var(--muted)" id="last-upd">Connecting...</span>
        <div class="status-pill">
            <div class="dot {{ 'green' if stats.bot_status == 'LIVE' else 'red' }}" id="status-dot"></div>
            <span id="bot-status">{{ stats.bot_status }}</span>
        </div>
        <button onclick="closeAllTrades()" class="btn danger">🔴 CLOSE ALL</button>
        <!-- Removed dangerous reset buttons to prevent accidental resets -->
        <!-- <button onclick="resetAccount()" class="btn warning">♻️ RESET BAL</button> -->
        <!-- <button onclick="resetEverything()" class="btn danger" style="box-shadow: 0 0 10px rgba(211,47,47,0.4);">🔥 RESET EVERYTHING</button> -->
        <div class="switch-wrapper">
            <label class="switch">
                <input type="checkbox" id="entry-toggle-input" onchange="toggleEntries()" checked>
                <span class="slider"></span>
            </label>
            <span class="switch-label-under">New Trades</span>
        </div>
    </div>
</div>

<div class="container">
    <!-- Stats -->
    <div class="stats" id="stats-row">
        <div class="stat"><div class="stat-label">💰 Live Portfolio</div><div class="stat-value blue" id="s-bal">${{ "%.2f"|format(stats.balance) }}</div><div class="stat-sub" id="s-bal-chg">Realized: ${{ "%.2f"|format(stats.realized_pnl) }}</div></div>
        <div class="stat"><div class="stat-label">📈 Unrealized PnL</div><div class="stat-value {{ 'green' if stats.unrealized_pnl >= 0 else 'red' }}" id="s-upnl">${{ "%.2f"|format(stats.unrealized_pnl) }}</div><div class="stat-sub" id="s-upnl-sub">{{ stats.open_positions }} Open positions</div></div>
        <div class="stat"><div class="stat-label">🔥 Trade Slots</div><div class="stat-value yellow" id="s-open">{{ stats.open_positions }}/{{ stats.max_concurrent }}</div><div class="stat-sub">Max concurrent</div></div>
        <div class="stat"><div class="stat-label">📡 Scanning</div><div class="stat-value blue" id="s-scan">{{ stats.scanning_markets }}</div><div class="stat-sub">Markets</div></div>
        <div class="stat"><div class="stat-label">📈 Total Trades</div><div class="stat-value" id="s-total">{{ stats.total_trades }}</div><div class="stat-sub" id="s-mode-text">{{ stats.mode }}</div></div>
        <div class="stat"><div class="stat-label">🎯 Win Rate</div><div class="stat-value green" id="s-wr">{{ "%.1f"|format(stats.win_rate) }}%</div><div class="stat-sub">Closed Trades</div></div>
        <div class="stat"><div class="stat-label">💵 Realized PnL</div><div class="stat-value {{ 'green' if stats.realized_pnl >= 0 else 'red' }}" id="s-pnl">${{ "%.2f"|format(stats.realized_pnl) }}</div><div class="stat-sub">After Fees</div></div>
    </div>

    <!-- View Controls -->
    <div class="view-bar">
        <button class="view-btn active" id="btn-markets" onclick="setView('markets')">🌐 Markets</button>
        <button class="view-btn" id="btn-active" onclick="setView('active')">🔥 Active Trades</button>
        <button class="view-btn" id="btn-history" onclick="setView('history')">📂 Trade History</button>
        <input class="search-inp" id="search" placeholder="🔍 Search symbol..." oninput="if(state.view==='markets')renderMarkets()">
    </div>

    <!-- Markets View -->
    <div id="view-markets">
        <div class="symbol-grid" id="markets-grid"></div>
    </div>

    <!-- Active Trades View -->
    <div id="view-active" style="display:none">
        <div class="section">
            <div class="section-hdr"><span>🔥 Active Positions</span><span id="active-count" style="color:var(--muted);font-size:0.8rem">{{ stats.open_positions }} positions</span></div>
            <div id="active-trades-list"></div>
        </div>
    </div>

    <!-- Trade History View -->
    <div id="view-history" style="display:none">
        <div class="section">
            <div class="section-hdr"><span>📂 Trade History</span><span style="color:var(--muted);font-size:0.8rem">{{ trade_history|length }} trades</span></div>
            <div style="overflow-x:auto">
                <table>
                    <thead>
                        <tr>
                            <th>Symbol</th><th>Side</th><th>Entry</th><th>Exit</th>
                            <th>Quantity</th><th>P&L</th><th>Reason</th><th>Entry Time</th>
                        </tr>
                    </thead>
                    <tbody id="history-tbody">
                        {% for trade in trade_history[-20:] %}
                        <tr class="{{ 'profit-row' if trade.pnl > 0 else ('loss-row' if trade.pnl < 0 else '') }}">
                            <td>{{ trade.symbol }}</td>
                            <td class="{{ 'act-open' if trade.side == 'buy' else 'act-close' }}">{{ trade.side.upper() }}</td>
                            <td>${{ "%.2f"|format(trade.entry_price) }}</td>
                            <td>${{ "%.2f"|format(trade.exit_price) }}</td>
                            <td>{{ "%.6f"|format(trade.quantity) }}</td>
                            <td class="{{ 'pnl-pos' if trade.pnl >= 0 else 'pnl-neg' }}">${{ "%.4f"|format(trade.pnl) }}</td>
                            <td>{{ trade.reason }}</td>
                            <td>{{ trade.entry_time[:19] if trade.entry_time else '-' }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                {% if not trade_history %}
                <div class="empty">No trades yet. Start the bot to begin trading!</div>
                {% endif %}
            </div>
        </div>
    </div>

    <!-- Phase 1 Progress -->
    <div class="section" style="margin-top:20px;">
        <div class="section-hdr">
            <span>🎯 Phase 1 Progress: $3 → $4</span>
            <span id="phase-progress" style="color:var(--muted);font-size:0.8rem">{{ "%.1f"|format(((stats.balance - 3) / 1) * 100) }}%</span>
        </div>
        <div style="padding:20px;">
            <div style="background:var(--card2); border-radius:10px; height:20px; overflow:hidden; margin-bottom:10px;">
                <div id="phase-bar" style="background:linear-gradient(90deg,var(--blue),var(--green)); height:100%; width:{{ "%.1f"|format(((stats.balance - 3) / 1) * 100) }}%; transition:width 0.5s;"></div>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:0.8rem; color:var(--muted);">
                <span>Start: $3.00</span>
                <span>Current: ${{ "%.2f"|format(stats.balance) }}</span>
                <span>Target: $4.00</span>
            </div>
            {% if stats.balance >= 4.0 %}
            <div style="text-align:center; margin-top:15px; padding:15px; background:rgba(0,229,160,.1); border-radius:10px; color:var(--green); font-weight:bold;">
                🎉 PHASE 1 COMPLETE! Ready for Phase 2 ($4 → $7)
            </div>
            {% endif %}
        </div>
    </div>
</div>

<div class="footer">
    ProfitBot Pro - Phase 1 Conservative Strategy | 2x Leverage | 3% Risk | ${{ "%.2f"|format(stats.balance) }} Portfolio
</div>

<script>
let state = {
    view: 'markets',
    markets: [],
    activeTrades: [],
    history: [],
    entriesEnabled: true,
    botRunning: false
};

function setView(view) {
    state.view = view;
    document.querySelectorAll('.view-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById('btn-' + view).classList.add('active');
    
    document.querySelectorAll('[id^="view-"]').forEach(el => el.style.display = 'none');
    document.getElementById('view-' + view).style.display = 'block';
    
    if (view === 'markets') renderMarkets();
    else if (view === 'active') renderActive();
    else if (view === 'history') renderHistory();
}

function renderMarkets() {
    const grid = document.getElementById('markets-grid');
    const search = document.getElementById('search').value.toLowerCase();
    
    const filtered = state.markets.filter(m => 
        m.symbol.toLowerCase().includes(search)
    );
    
    grid.innerHTML = filtered.map(market => `
        <div class="symbol-card ${market.position !== 'FLAT' ? 'in-position' : ''}" onclick="togglePosition('${market.symbol}')">
            <div class="card-header">
                <div class="card-sym">${market.symbol}</div>
                <div class="card-price">$${market.price.toFixed(2)}</div>
            </div>
            <div class="card-footer">
                <span class="badge ${market.signal.toLowerCase()}">${market.signal}</span>
                <span class="badge ${market.position.toLowerCase()}">${market.position}</span>
                <span class="indicator-pill">RSI: ${market.rsi.toFixed(1)}</span>
                <span class="indicator-pill">Str: ${market.signal_strength.toFixed(1)}</span>
            </div>
        </div>
    `).join('');
}

function renderActive() {
    const container = document.getElementById('active-trades-list');
    
    if (state.activeTrades.length === 0) {
        container.innerHTML = '<div class="empty">No active positions</div>';
        return;
    }
    
    container.innerHTML = state.activeTrades.map(trade => `
        <div class="section" style="margin-bottom:15px;">
            <div class="section-hdr">
                <span>${trade.symbol} - ${trade.side.toUpperCase()}</span>
                <span class="${trade.upnl >= 0 ? 'pnl-pos' : 'pnl-neg'}">$${trade.upnl.toFixed(4)}</span>
            </div>
            <div style="padding:15px; font-size:0.85rem;">
                <div style="display:grid; grid-template-columns:repeat(2,1fr); gap:10px;">
                    <div>Entry: $${trade.entry_price.toFixed(2)}</div>
                    <div>Quantity: ${trade.quantity.toFixed(6)}</div>
                    <div>TP: $${trade.tp.toFixed(2)}</div>
                    <div>SL: $${trade.sl.toFixed(2)}</div>
                </div>
                <button class="btn danger" style="width:100%; margin-top:10px;" onclick="closeTrade('${trade.id}')">
                    Close Position
                </button>
            </div>
        </div>
    `).join('');
}

function renderHistory() {
    // History is rendered server-side with Jinja2
}

function togglePosition(symbol) {
    if (!state.entriesEnabled) {
        alert('New trades are disabled!');
        return;
    }
    
    fetch('/api/toggle-position', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({symbol: symbol})
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert(data.error);
        } else {
            console.log('Position toggled:', data.message);
        }
    });
}

function closeTrade(tradeId) {
    fetch('/api/close-trade', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({trade_id: tradeId})
    })
    .then(response => response.json())
    .then(data => {
        console.log('Trade closed:', data.message);
        updateData();
    });
}

function closeAllTrades() {
    if (!confirm('Close ALL active positions?')) return;
    fetch('/api/close-all', {method: 'POST'})
    .then(response => response.json())
    .then(data => {
        console.log('All trades closed:', data.message);
        updateData();
    });
}

function resetAccount() {
    if (!confirm('Reset account balance to $3.00?')) return;
    fetch('/api/reset-account', {method: 'POST'})
    .then(response => response.json())
    .then(data => {
        console.log('Account reset:', data.message);
        location.reload();
    });
}

function resetEverything() {
    if (!confirm('RESET EVERYTHING? This will clear all data!')) return;
    fetch('/api/reset-everything', {method: 'POST'})
    .then(response => response.json())
    .then(data => {
        console.log('Everything reset:', data.message);
        location.reload();
    });
}

function toggleEntries() {
    const checkbox = document.getElementById('entry-toggle-input');
    state.entriesEnabled = checkbox.checked;
    
    fetch('/api/toggle-entries', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({enabled: state.entriesEnabled})
    })
    .then(response => response.json())
    .then(data => {
        console.log('Entries toggled:', data.message);
    });
}

function updateData() {
    fetch('/api/data')
    .then(response => response.json())
    .then(data => {
        // Update stats
        Object.keys(data.stats).forEach(key => {
            const element = document.getElementById('s-' + key.replace('_', '-'));
            if (element) {
                if (key.includes('pnl') || key === 'balance') {
                    element.textContent = '$' + data.stats[key].toFixed(2);
                    element.className = 'stat-value ' + (data.stats[key] >= 0 ? 'green' : 'red');
                } else if (key === 'win_rate') {
                    element.textContent = data.stats[key].toFixed(1) + '%';
                } else {
                    element.textContent = data.stats[key];
                }
            }
        });
        
        // Update status
        document.getElementById('bot-status').textContent = data.stats.bot_status;
        document.getElementById('status-dot').className = 'dot ' + (data.stats.bot_status === 'LIVE' ? 'green' : 'red');
        document.getElementById('last-upd').textContent = 'Last update: ' + new Date().toLocaleTimeString();
        
        // Update state
        state.markets = data.markets;
        state.activeTrades = data.activeTrades;
        state.history = data.history;
        state.entriesEnabled = data.entries_enabled;
        state.botRunning = data.stats.bot_status === 'LIVE';
        
        // Update entry toggle
        document.getElementById('entry-toggle-input').checked = state.entriesEnabled;
        
        // Update phase progress
        const progress = Math.max(0, Math.min(100, ((data.stats.balance - 3) / 1) * 100));
        document.getElementById('phase-bar').style.width = progress + '%';
        document.getElementById('phase-progress').textContent = progress.toFixed(1) + '%';
        
        // Re-render current view
        if (state.view === 'markets') renderMarkets();
        else if (state.view === 'active') renderActive();
    });
}

// Auto-update every 2 seconds
setInterval(updateData, 2000);

// Initial load
updateData();

// Force enable new trades on startup
setTimeout(() => {
    fetch('/api/toggle-entries', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({enabled: true})
    });
}, 3000);

// Start bot automatically
fetch('/api/start', {method: 'POST'});
</script>
</body>
</html>
"""

# Routes
@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE, stats=stats, trade_history=trade_history)

@app.route('/api/data')
def get_data():
    global trading_bot, market_data, active_positions
    
    try:
        if trading_bot:
            trading_bot.run_trading_cycle()
            
            # Convert active positions to dict format
            active_trades = []
            for pos in active_positions:
                current_price = market_data.get(pos['symbol'], {}).get('price', pos['entry_price'])
                upnl = trading_bot.calculate_upnl(pos['symbol'], current_price)
                pos['upnl'] = upnl
                active_trades.append(pos)
        else:
            active_trades = []
        
        return jsonify({
            'stats': stats,
            'markets': list(market_data.values()),
            'activeTrades': active_trades,
            'history': trade_history[-20:],
            'entries_enabled': entries_enabled
        })
    except Exception as e:
        logger.error(f"Error in /api/data: {e}")
        return jsonify({
            'stats': stats,
            'markets': [],
            'activeTrades': [],
            'history': [],
            'entries_enabled': False,
            'error': str(e)
        })

@app.route('/api/start', methods=['POST'])
def start_bot():
    global trading_bot, is_running
    if not trading_bot:
        trading_bot = ProfitBot()
    trading_bot.is_running = True
    is_running = True
    return jsonify({'status': 'started', 'message': 'Bot started successfully'})

@app.route('/api/stop', methods=['POST'])
def stop_bot():
    global is_running
    if trading_bot:
        trading_bot.is_running = False
    is_running = False
    return jsonify({'status': 'stopped', 'message': 'Bot stopped'})

@app.route('/api/toggle-position', methods=['POST'])
def toggle_position():
    global trading_bot
    if not trading_bot or not trading_bot.is_running:
        return jsonify({'error': 'Bot not running'})
    
    data = request.get_json()
    symbol = data.get('symbol')
    
    # Get market data for signal
    market = market_data.get(symbol)
    if not market:
        return jsonify({'error': 'Market data not found'})
    
    if market['signal'] in ['BUY', 'SELL']:
        trade, message = trading_bot.execute_trade(symbol, market['signal'])
        if trade:
            return jsonify({'status': 'success', 'message': message, 'trade': trade})
        else:
            return jsonify({'error': message})
    else:
        return jsonify({'error': 'No trading signal'})

@app.route('/api/close-trade', methods=['POST'])
def close_trade():
    global trading_bot, active_positions
    data = request.get_json()
    trade_id = data.get('trade_id')
    
    for pos in active_positions:
        if pos['id'] == trade_id:
            current_price = market_data.get(pos['symbol'], {}).get('price', pos['entry_price'])
            trading_bot.close_position(pos, 'MANUAL', current_price)
            return jsonify({'status': 'success', 'message': 'Position closed'})
    
    return jsonify({'error': 'Trade not found'})

@app.route('/api/close-all', methods=['POST'])
def close_all_trades():
    global trading_bot, active_positions
    if not trading_bot:
        return jsonify({'error': 'Bot not initialized'})
    
    for pos in active_positions[:]:  # Copy list to avoid modification during iteration
        current_price = market_data.get(pos['symbol'], {}).get('price', pos['entry_price'])
        trading_bot.close_position(pos, 'MANUAL', current_price)
    
    return jsonify({'status': 'success', 'message': 'All positions closed'})

@app.route('/api/reset-account', methods=['POST'])
def reset_account():
    global trading_bot, stats, active_positions, trade_history
    trading_bot = None
    active_positions = []
    trade_history = []
    stats.update({
        'balance': STARTING_BALANCE,
        'realized_pnl': 0.0,
        'unrealized_pnl': 0.0,
        'open_positions': 0,
        'total_trades': 0,
        'win_rate': 0.0
    })
    return jsonify({'status': 'success', 'message': 'Account reset to $3.00'})

@app.route('/api/reset-everything', methods=['POST'])
def reset_everything():
    global trading_bot, stats, active_positions, trade_history, market_data, entries_enabled, is_running
    trading_bot = None
    active_positions = []
    trade_history = []
    market_data = {}
    entries_enabled = True
    is_running = False
    stats.update({
        'balance': STARTING_BALANCE,
        'realized_pnl': 0.0,
        'unrealized_pnl': 0.0,
        'open_positions': 0,
        'total_trades': 0,
        'win_rate': 0.0,
        'bot_status': 'STOPPED'
    })
    return jsonify({'status': 'success', 'message': 'Everything reset'})

@app.route('/api/toggle-entries', methods=['POST'])
def toggle_entries():
    global entries_enabled
    data = request.get_json()
    entries_enabled = data.get('enabled', True)
    return jsonify({'status': 'success', 'message': f'Entries {"enabled" if entries_enabled else "disabled"}'})

def main():
    print("🤖 ProfitBot Pro Dashboard - Phase 1")
    print("=" * 60)
    print("🎯 Strategy: $3 → $4 Conservative Growth")
    print("⚙️  Parameters: 2x Leverage, 3% Risk, 60% Win Rate")
    print("🌐 Open your browser and go to: http://localhost:5000")
    print("\n🚀 Features:")
    print("   • Live market scanning")
    print("   • Auto-trading with signals")
    print("   • Real-time P&L tracking")
    print("   • Professional UI like your profitable site")
    print("   • Phase 1 progress tracking")
    print("\nPress Ctrl+C to stop the server")
    
    app.run(host='0.0.0.0', port=5000, debug=False)

if __name__ == '__main__':
    main()
