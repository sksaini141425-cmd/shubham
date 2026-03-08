"""
ProfitBot Pro - Live Paper Trading Dashboard
Rich chart view with per-asset candlestick charts, indicators, TP/SL, and live trades.
"""
from flask import Flask, jsonify, render_template_string, request
import json
import os
import requests as req_lib

app = Flask(__name__)

dashboard_state = {
    "bot_status": "STARTING",
    "last_update": "",
    "symbols": {}
}

manual_close_requests = set()

TRADE_LOG_FILE = "trade_log.json"

TOP_SYMBOLS = [
    'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT',
    'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'DOTUSDT',
    'MATICUSDT', 'LTCUSDT', 'ATOMUSDT', 'UNIUSDT', 'SHIBUSDT',
    'AAVEUSDT', 'NEARUSDT', 'ARBUSDT', 'APTUSDT', 'OPUSDT'
]

def _fetch_live_prices():
    """Batch fetch live prices from MEXC when scanner threads haven't populated state."""
    try:
        resp = req_lib.get(
            'https://api.mexc.com/api/v3/ticker/price',
            timeout=8
        )
        if resp.status_code == 200:
            data = resp.json()
            # Convert list of {symbol, price} to a dict map
            price_map = {item['symbol']: float(item['price']) for item in data}
            
            result = {}
            for sym in TOP_SYMBOLS:
                price = price_map.get(sym, 0)
                state = dashboard_state.get('symbols', {}).get(sym, {})
                result[sym] = {
                    'price': price,
                    'signal': state.get('signal', 'SCANNING'),
                    'direction': state.get('direction', 'FLAT'),
                    'entry': state.get('entry', 0),
                    'upnl': state.get('upnl', 0),
                    'min_notional': state.get('min_notional', 5.0),
                    'fee_pct': state.get('fee_pct', '0.050%'),
                    'rsi': state.get('rsi', None),
                    'macd_hist': state.get('macd_hist', None),
                    'ema200': state.get('ema200', None),
                    'atr': state.get('atr', None),
                    'bb_upper': state.get('bb_upper', None),
                    'bb_middle': state.get('bb_middle', None),
                    'bb_lower': state.get('bb_lower', None),
                    'sl_price': state.get('sl_price', None),
                    'tp_price': state.get('tp_price', None),
                    'candles': state.get('candles', [])
                }
            return result
    except Exception:
        pass
    return dashboard_state.get('symbols', {})

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ProfitBot Pro — Advanced TradingView Dashboard</title>
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

/* Modal with Full TradingView Widget */
.modal-overlay { display:none; position:fixed; inset:0; background:rgba(0,0,0,.8);
    z-index:1000; align-items:center; justify-content:center; }
.modal-overlay.open { display:flex; }
.modal { background:var(--card); border:1px solid var(--border); border-radius:16px;
    width:95vw; max-width:1100px; max-height:92vh; overflow-y:auto; padding:20px; }
.modal-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; }
.modal-title { font-size:1.2rem; font-weight:700; }
.close-btn { width:32px; height:32px; border-radius:50%; background:var(--card2);
    border:1px solid var(--border); cursor:pointer; font-size:1.1rem; display:flex; align-items:center; justify-content:center; }
.close-btn:hover { background:var(--red); color:white; border-color:var(--red); }
.modal-chart { width:100%; height:450px; border-radius:10px; overflow:hidden; }
.indicator-row { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:10px; margin:14px 0; }
.ind-card { background:var(--card2); border:1px solid var(--border); border-radius:10px; padding:12px; }
.ind-label { font-size:0.65rem; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; margin-bottom:5px; }
.ind-value { font-size:1.1rem; font-weight:600; }
.trade-info { background:var(--card2); border:1px solid var(--border); border-radius:10px; padding:14px; margin-top:12px; }
.trade-row { display:flex; justify-content:space-between; font-size:0.82rem; margin:6px 0; }
.close-manual-btn { margin-top:14px; width:100%; padding:12px; background:var(--red); color:white; border:none; border-radius:10px; font-weight:700; cursor:pointer; font-size:1rem; transition:background 0.2s; }
.close-manual-btn:hover { background:#d43f5a; }
.strategy-box { background:#0a1428; border:1px solid var(--border); border-radius:10px; padding:14px; margin-top:12px; font-size:0.8rem; color:var(--muted); line-height:1.8; }
.strategy-box strong { color:var(--text); }

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
.empty { padding:40px; text-align:center; color:var(--muted); font-size:0.85rem; }
.footer { text-align:center; color:var(--muted); font-size:0.7rem; padding:20px; border-top:1px solid var(--border); margin-top:20px; }
</style>
</head>
<body>

<div class="header">
    <div class="logo">🤖 ProfitBot Pro</div>
    <div style="display:flex;align-items:center;gap:12px">
        <span style="font-size:0.75rem;color:var(--muted)" id="last-upd">Connecting...</span>
        <div class="status-pill">
            <div class="dot green"></div>
            <span id="bot-status">LIVE</span>
        </div>
    </div>
</div>

<div class="container">
    <!-- Stats -->
    <div class="stats" id="stats-row">
        <div class="stat"><div class="stat-label">💰 Live Portfolio</div><div class="stat-value blue" id="s-bal">$3.00</div><div class="stat-sub" id="s-bal-chg">Realized: $3.00</div></div>
        <div class="stat"><div class="stat-label">📈 Unrealized PnL</div><div class="stat-value" id="s-upnl">+$0.00</div><div class="stat-sub" id="s-upnl-sub">Open positions</div></div>
        <div class="stat"><div class="stat-label">🔥 Trade Slots</div><div class="stat-value yellow" id="s-open">0/3</div><div class="stat-sub">Max concurrent</div></div>
        <div class="stat"><div class="stat-label">📡 Scanning</div><div class="stat-value blue" id="s-scan">—</div><div class="stat-sub">Markets</div></div>
        <div class="stat"><div class="stat-label">📈 Total Trades</div><div class="stat-value" id="s-total">0</div><div class="stat-sub">Paper Mode</div></div>
        <div class="stat"><div class="stat-label">🎯 Win Rate</div><div class="stat-value green" id="s-wr">—</div><div class="stat-sub">Closed Trades</div></div>
        <div class="stat"><div class="stat-label">💵 Realized PnL</div><div class="stat-value" id="s-pnl">+$0.00</div><div class="stat-sub">After Fees</div></div>
    </div>

    <!-- View Controls -->
    <div class="view-bar">
        <button class="view-btn active" id="btn-charts" onclick="setView('charts')">📊 Charts</button>
        <button class="view-btn" id="btn-table" onclick="setView('table')">📋 Market Table</button>
        <button class="view-btn" id="btn-active" onclick="setView('active')">🔥 Active Trades</button>
        <button class="view-btn" id="btn-history" onclick="setView('history')">📂 Trade History</button>
        <label style="font-size:0.85rem; display:flex; align-items:center; gap:8px; cursor:pointer;" id="toggle-charts-wrap">
            <input type="checkbox" id="toggle-mini" onchange="toggleMiniCharts()"> Show Mini Charts
        </label>
        <input class="search-inp" id="search" placeholder="🔍 Search symbol..." oninput="renderSymbols()">
    </div>

    <!-- Charts View -->
    <div id="view-charts">
        <div class="symbol-grid" id="sym-grid"></div>
    </div>

    <!-- Market Table View -->
    <div id="view-table" style="display:none">
        <div class="section">
            <div class="section-hdr"><span>🌐 All Markets</span><span id="mkt-count" style="color:var(--muted);font-size:0.8rem"></span></div>
            <div style="overflow-x:auto">
            <table><thead><tr>
                <th>Symbol</th><th>Price</th><th>Signal</th><th>Position</th>
                <th>RSI</th><th>MACD Hist</th><th>EMA200</th><th>ATR</th>
                <th>BB Upper</th><th>BB Lower</th><th>Entry</th><th>TP</th><th>SL</th><th>uPnL</th>
            </tr></thead>
            <tbody id="mkt-tbody"></tbody></table>
            </div>
        </div>
    </div>

    <!-- Active Trades View -->
    <div id="view-active" style="display:none">
        <div class="section">
            <div class="section-hdr"><span>🔥 Live Positions</span><span id="act-count" style="color:var(--muted);font-size:0.8rem"></span></div>
            <div style="overflow-x:auto">
            <table><thead><tr>
                <th>Symbol</th><th>Direction</th><th>Entry Price</th><th>Current Price</th>
                <th>Take Profit 🟢</th><th>Stop Loss 🔴</th><th>Live uPnL</th>
            </tr></thead>
            <tbody id="act-tbody"></tbody></table>
            </div>
        </div>
    </div>

    <!-- History View -->
    <div id="view-history" style="display:none">
        <div class="section">
            <div class="section-hdr"><span>📋 Trade History</span><span id="hist-count" style="color:var(--muted);font-size:0.8rem"></span></div>
            <div style="overflow-x:auto">
            <table><thead><tr>
                <th>#</th><th>Time</th><th>Symbol</th><th>Action</th>
                <th>Entry</th><th>Exit</th><th>Size</th><th>Notional</th>
                <th>Fee</th><th>PnL</th><th>Bal Before</th><th>Bal After</th>
            </tr></thead>
            <tbody id="hist-tbody"></tbody></table>
            </div>
        </div>
    </div>
</div>

<!-- Chart Modal -->
<div class="modal-overlay" id="modal" onclick="closeModal(event)">
    <div class="modal">
        <div class="modal-header">
            <div class="modal-title" id="modal-title">BTCUSDT</div>
            <div class="close-btn" onclick="closeModal()">✕</div>
        </div>
        <div class="modal-chart" id="modal-chart"></div>
        <div class="indicator-row" id="modal-inds"></div>
        <div class="trade-info" id="modal-trade" style="display:none"></div>
        <div class="strategy-box">
            <strong>📐 Smart Money Strategy Logic:</strong><br>
            • <strong>EMA 200</strong> — Trend filter. Price above = bullish bias, below = bearish bias<br>
            • <strong>Bollinger Bands (20)</strong> — Entry trigger. Pull back to lower band = LONG, rally to upper band = SHORT<br>
            • <strong>RSI (14)</strong> — Momentum. LONG needs RSI &lt;45 (oversold). SHORT needs RSI &gt;55 (overbought)<br>
            • <strong>MACD (12/26/9)</strong> — Confirmation. Histogram must be rising (LONG) or falling (SHORT)<br>
            • <strong>ATR (14)</strong> — Stop Loss distance. SL = 1.5× ATR below/above entry<br>
            • <strong>Trailing SL</strong> — Moves to break-even at 0.5% profit, then locks 50% profit at 1.5%
        </div>
    </div>
</div>

<div class="footer">ProfitBot Pro — Smart Money Edition 🛡️ | EMA200 + BB + RSI + MACD + ATR | Auto-refreshes every 10s</div>

<script>
let state = {syms:{}, trades:[], view:'charts', showMini:false};
let miniCharts = {};
let modalChart = null;
let currentSym = null;

let ws = null;
let subscribedSyms = new Set();

async function requestManualClose(sym) {
    if(!confirm('Are you sure you want to close ' + sym + ' manually?')) return;
    try {
        await fetch('/api/close_trade/' + sym, {method: 'POST'});
        alert('Close requested for ' + sym);
        closeModal();
        refresh();
    } catch(e) {
        alert('Error requesting close');
    }
}

function updateWsSubscriptions() {
    const active = Object.keys(state.syms).filter(sym => state.syms[sym].direction && state.syms[sym].direction !== 'FLAT');
    const toSub = active.filter(sym => !subscribedSyms.has(sym));
    const toUnsub = [...subscribedSyms].filter(sym => !active.includes(sym));
    
    if (toSub.length === 0 && toUnsub.length === 0) return;
    
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        if (active.length > 0) initWS(active);
        return;
    }
    
    if (toSub.length > 0) {
        ws.send(JSON.stringify({method: "SUBSCRIBE", params: toSub.map(s => s.toLowerCase() + '@ticker'), id: 1}));
        toSub.forEach(s => subscribedSyms.add(s));
    }
    if (toUnsub.length > 0) {
        ws.send(JSON.stringify({method: "UNSUBSCRIBE", params: toUnsub.map(s => s.toLowerCase() + '@ticker'), id: 2}));
        toUnsub.forEach(s => subscribedSyms.delete(s));
    }
}

function initWS(initialSyms) {
    ws = new WebSocket('wss://fstream.binance.com/ws');
    ws.onopen = () => {
        subscribedSyms = new Set(initialSyms);
        ws.send(JSON.stringify({method: "SUBSCRIBE", params: initialSyms.map(s => s.toLowerCase() + '@ticker'), id: 1}));
    };
    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.e === '24hrTicker') {
            onLivePrice(msg.s, parseFloat(msg.c));
        }
    };
    ws.onclose = () => { ws = null; subscribedSyms.clear(); };
}

function onLivePrice(sym, price) {
    if (!state.syms[sym]) return;
    const s = state.syms[sym];
    s.price = price;
    
    if (s.direction && s.direction !== 'FLAT') {
        let rawPnl = 0;
        if (s.direction === 'LONG') rawPnl = (price - s.entry) * (s.size || 0);
        if (s.direction === 'SHORT') rawPnl = (s.entry - price) * (s.size || 0);
        
        const fee_pct = parseFloat(s.fee_pct) / 100 || 0.0005;
        const close_fee = (s.size || 0) * price * fee_pct;
        s.upnl = rawPnl - close_fee;
        
        // Update DOM directly for high performance (every tick)
        updateLiveDom(sym, s, price);
    }
}

function updateLiveDom(sym, s, price) {
    const actRow = document.getElementById('act-row-'+sym);
    if (actRow) {
        const priceTd = actRow.querySelector('.live-price');
        const pnlTd = actRow.querySelector('.live-pnl');
        if (priceTd) priceTd.innerHTML = '$' + price.toLocaleString('en',{minimumFractionDigits:4});
        if (pnlTd) {
            pnlTd.className = 'live-pnl ' + (s.upnl >= 0 ? 'pnl-pos' : 'pnl-neg');
            pnlTd.innerHTML = (s.upnl >= 0 ? '+$' : '-$') + Math.abs(s.upnl).toFixed(6);
        }
    }
    
    if (currentSym === sym) {
        const tradeEl = document.getElementById('modal-trade');
        if (tradeEl) {
            const priceSpan = document.getElementById('modal-live-price');
            const pnlSpan = document.getElementById('modal-live-pnl');
            if (priceSpan) priceSpan.innerHTML = '$' + price.toLocaleString('en',{minimumFractionDigits:4});
            if (pnlSpan) {
                pnlSpan.className = 'modal-live-pnl ' + (s.upnl >= 0 ? 'pnl-pos' : 'pnl-neg');
                pnlSpan.innerHTML = (s.upnl >= 0 ? '+$' : '-$') + Math.abs(s.upnl).toFixed(6);
            }
        }
    }
}

function toggleMiniCharts() {
    state.showMini = document.getElementById('toggle-mini').checked;
    renderSymbols();
}

function setView(v) {
    state.view = v;
    document.getElementById('view-charts').style.display = v==='charts' ? '' : 'none';
    document.getElementById('view-table').style.display = v==='table' ? '' : 'none';
    document.getElementById('view-active').style.display = v==='active' ? '' : 'none';
    document.getElementById('view-history').style.display = v==='history' ? '' : 'none';
    document.getElementById('toggle-charts-wrap').style.display = v==='charts' ? 'flex' : 'none';
    
    document.getElementById('btn-charts').className = 'view-btn' + (v==='charts'?' active':'');
    document.getElementById('btn-table').className = 'view-btn' + (v==='table'?' active':'');
    document.getElementById('btn-active').className = 'view-btn' + (v==='active'?' active':'');
    document.getElementById('btn-history').className = 'view-btn' + (v==='history'?' active':'');
    
    if (v==='table') renderTable();
    if (v==='active') renderActiveTrades();
    if (v==='history') renderHistory();
}

function getRsiColor(rsi) {
    if (rsi === null || rsi === undefined) return 'var(--muted)';
    if (rsi < 30) return 'var(--green)'; // oversold
    if (rsi > 70) return 'var(--red)';   // overbought
    if (rsi < 45) return '#6ee7b7';
    if (rsi > 55) return '#fca5a5';
    return 'var(--text)';
}

function getMacdColor(hist) {
    if (hist === null || hist === undefined) return 'var(--muted)';
    return hist > 0 ? 'var(--green)' : 'var(--red)';
}

async function refresh() {
    try {
        const r = await fetch('/api/state');
        const d = await r.json();
        state.syms = d.symbols || {};
        state.trades = d.trades || [];

        document.getElementById('last-upd').textContent = 'Updated: ' + new Date().toLocaleTimeString();
        document.getElementById('bot-status').textContent = d.bot_status || 'RUNNING';

        const closed = state.trades.filter(t => t.action && t.action.startsWith('CLOSE'));
        const wins = closed.filter(t => t.pnl > 0);
        const netPnl = closed.reduce((s,t) => s+(t.pnl||0), 0);
        const wr = closed.length > 0 ? ((wins.length/closed.length)*100).toFixed(1) : null;

        // --- REAL-TIME LIVE BALANCE: Cash + Unrealized PnL ---
        const STARTING_CAPITAL = 3.0;
        const liveBal = d.live_balance != null ? d.live_balance : STARTING_CAPITAL;
        const realizedCash = d.realized_cash != null ? d.realized_cash : STARTING_CAPITAL;
        const totalUpnl = d.total_upnl != null ? d.total_upnl : 0;
        const openCount = d.open_trade_count != null ? d.open_trade_count : 0;
        const maxTrades = d.max_trades != null ? d.max_trades : 3;
        const liveBalChg = liveBal - STARTING_CAPITAL;

        document.getElementById('s-bal').textContent = '$'+liveBal.toFixed(4);
        document.getElementById('s-bal-chg').textContent = 'Realized: $'+realizedCash.toFixed(4);
        document.getElementById('s-bal-chg').className = 'stat-sub '+(liveBal >= STARTING_CAPITAL ? 'green' : 'red');

        document.getElementById('s-upnl').textContent = (totalUpnl>=0?'+$':'-$')+Math.abs(totalUpnl).toFixed(4);
        document.getElementById('s-upnl').className = 'stat-value '+(totalUpnl>=0?'green':'red');
        document.getElementById('s-upnl-sub').textContent = openCount + ' open position' + (openCount!==1?'s':'');

        document.getElementById('s-open').textContent = openCount+'/'+maxTrades;
        document.getElementById('s-scan').textContent = Object.keys(state.syms).length;
        document.getElementById('s-total').textContent = state.trades.length;
        document.getElementById('s-wr').textContent = wr ? wr+'%' : '—';
        document.getElementById('s-pnl').textContent = (netPnl>=0?'+$':'-$')+Math.abs(netPnl).toFixed(4);
        document.getElementById('s-pnl').className = 'stat-value '+(netPnl>=0?'green':'red');

        if (state.view === 'charts') renderSymbols();
        if (state.view === 'table') renderTable();
        if (state.view === 'active') renderActiveTrades();
        if (state.view === 'history') renderHistory();
        if (currentSym && state.syms[currentSym]) updateModal(currentSym, true); // true = update quietly
        
        updateWsSubscriptions();
        
    } catch(e) {
        document.getElementById('last-upd').textContent = 'Connection error...';
    }
}

function renderSymbols() {
    const q = document.getElementById('search').value.toUpperCase();
    const syms = Object.entries(state.syms).filter(([s]) => s.includes(q));
    const grid = document.getElementById('sym-grid');

    syms.forEach(([sym, s]) => {
        const inPos = s.direction && s.direction !== 'FLAT';
        const sig = s.signal || 'SCANNING';
        const sigClass = sig === 'LONG' ? 'buy' : sig === 'SHORT' ? 'sell' : sig === 'SCANNING' ? 'scanning' : 'neutral';

        let card = document.getElementById('card-'+sym);
        if (!card) {
            card = document.createElement('div');
            card.id = 'card-'+sym;
            card.className = 'symbol-card' + (inPos?' in-position':'');
            card.onclick = () => openModal(sym);
            card.innerHTML = `
                <div class="card-header">
                    <div>
                        <div class="card-sym">${sym.replace('USDT','')} <span class="muted" style="font-size:.7rem;font-weight:400">USDT</span></div>
                        <div style="margin-top:3px">
                            <span class="badge ${sigClass}" id="sig-${sym}">${sig}</span>
                            <span class="badge ${inPos?s.direction.toLowerCase():'flat'}" id="dir-${sym}">${inPos?s.direction:'FLAT'}</span>
                        </div>
                    </div>
                    <div class="card-price" id="price-${sym}">$${(s.price||0).toLocaleString('en',{minimumFractionDigits:2,maximumFractionDigits:6})}</div>
                </div>
                <!-- Binance Style Advanced TradingView Widget embedded per card -->
                <div class="chart-container" id="tv_widget_${sym}" style="display:${state.showMini?'block':'none'}"></div>
                <div class="card-footer">
                    <span class="indicator-pill" id="rsi-${sym}">RSI: ${s.rsi ? s.rsi.toFixed(1) : '—'}</span>
                    <span class="indicator-pill" id="macd-${sym}">MACD: ${s.macd_hist ? (s.macd_hist > 0 ? '▲' : '▼') : '—'}</span>
                    <span class="indicator-pill" id="atr-${sym}">ATR: ${s.atr ? s.atr.toFixed(4) : '—'}</span>
                    ${inPos ? `<span class="indicator-pill pnl-${(s.upnl||0)>=0?'pos':'neg'}" id="upnl-${sym}">${(s.upnl||0)>=0?'+$':'-$'}${Math.abs(s.upnl||0).toFixed(4)}</span>` : ''}
                </div>`;
            grid.appendChild(card);

            // Draw mini advanced chart widget
            if (state.showMini) {
                drawMiniChart(sym);
            }
        } else {
            // Update existing card
            card.className = 'symbol-card' + (inPos?' in-position':'');
            document.getElementById('sig-'+sym).textContent = sig;
            document.getElementById('sig-'+sym).className = 'badge '+sigClass;
            document.getElementById('dir-'+sym).textContent = inPos?s.direction:'FLAT';
            document.getElementById('dir-'+sym).className = 'badge '+(inPos?s.direction.toLowerCase():'flat');
            document.getElementById('price-'+sym).textContent = '$'+(s.price||0).toLocaleString('en',{minimumFractionDigits:2,maximumFractionDigits:6});
            document.getElementById('rsi-'+sym).textContent = 'RSI: '+(s.rsi ? s.rsi.toFixed(1) : '—');
            document.getElementById('rsi-'+sym).style.color = getRsiColor(s.rsi);
            document.getElementById('macd-'+sym).textContent = 'MACD: '+(s.macd_hist ? (s.macd_hist > 0 ? '▲ Bull' : '▼ Bear') : '—');
            document.getElementById('macd-'+sym).style.color = getMacdColor(s.macd_hist);
            if (document.getElementById('upnl-'+sym)) {
                document.getElementById('upnl-'+sym).textContent = (s.upnl||0)>=0?'+$':'-$'+Math.abs(s.upnl||0).toFixed(4);
            }

            const chartCont = document.getElementById('tv_widget_'+sym);
            if (chartCont) {
                chartCont.style.display = state.showMini ? 'block' : 'none';
                if (state.showMini) drawMiniChart(sym);
            }
        }
    });
}

function drawMiniChart(sym) {
    if (miniCharts[sym]) return;
    const tvSymbol = "BINANCE:" + sym; // Ensures it uses Binance data natively
    miniCharts[sym] = new TradingView.widget({
        "container_id": "tv_widget_"+sym,
        "width": "100%",
        "height": "120",
        "symbol": tvSymbol,
        "interval": "1",
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": "1",
        "locale": "en",
        "enable_publishing": false,
        "hide_top_toolbar": true,
        "hide_legend": true,
        "save_image": false,
        "toolbar_bg": "#0c1529",
        "studies": [] // Clean chart for mini view
    });
}

function openModal(sym) {
    currentSym = sym;
    document.getElementById('modal').classList.add('open');
    document.getElementById('modal-title').textContent = sym;
    updateModal(sym, false);
}

function updateModal(sym, quiet=false) {
    const s = state.syms[sym];
    if (!s) return;
    
    if (!quiet) {
        const el = document.getElementById('modal-chart');
        el.innerHTML = '';
        
        // Mount full-featured advanced Binance-style TradingView widget
        const tvSymbol = "BINANCE:" + sym;
        modalChart = new TradingView.widget({
            "container_id": "modal-chart",
            "width": "100%",
            "height": "450",
            "symbol": tvSymbol,
            "interval": "5",
            "timezone": "Etc/UTC",
            "theme": "dark",
            "style": "1",
            "locale": "en",
            "enable_publishing": false,
            "hide_top_toolbar": false,
            "hide_legend": false,
            "save_image": false,
            "toolbar_bg": "#0a1428",
            "studies": [
                "MACD@tv-basicstudies",    
                "RSI@tv-basicstudies",      
                "BB@tv-basicstudies",        
                "MASimple@tv-basicstudies"  
            ]
        });
    }

    // Indicators Row
    const rsiColor = getRsiColor(s.rsi);
    document.getElementById('modal-inds').innerHTML = `
        <div class="ind-card">
            <div class="ind-label">RSI (14)</div>
            <div class="ind-value" style="color:${rsiColor}">${s.rsi !== null && s.rsi !== undefined ? s.rsi.toFixed(1) : '—'}</div>
            <div style="font-size:.68rem;margin-top:3px;color:var(--muted)">${s.rsi < 30 ? '🟢 Oversold' : s.rsi > 70 ? '🔴 Overbought' : s.rsi < 45 ? 'Leaning Oversold' : s.rsi > 55 ? 'Leaning Overbought' : 'Neutral'}</div>
        </div>
        <div class="ind-card">
            <div class="ind-label">MACD Histogram</div>
            <div class="ind-value" style="color:${getMacdColor(s.macd_hist)}">${s.macd_hist !== null && s.macd_hist !== undefined ? (s.macd_hist > 0 ? '▲ ' : '▼ ') + Math.abs(s.macd_hist).toFixed(6) : '—'}</div>
            <div style="font-size:.68rem;margin-top:3px;color:var(--muted)">${s.macd_hist > 0 ? 'Bullish momentum' : s.macd_hist < 0 ? 'Bearish momentum' : 'Neutral'}</div>
        </div>
        <div class="ind-card">
            <div class="ind-label">ATR (14)</div>
            <div class="ind-value">${s.atr !== null && s.atr !== undefined ? s.atr.toFixed(6) : '—'}</div>
            <div style="font-size:.68rem;margin-top:3px;color:var(--muted)">SL distance: ${s.atr ? (s.atr * 1.5).toFixed(6) : '—'}</div>
        </div>
        <div class="ind-card">
            <div class="ind-label">EMA 200</div>
            <div class="ind-value ${s.price > (s.ema200||0) ? 'green' : 'red'}">${s.ema200 ? '$'+s.ema200.toFixed(4) : '—'}</div>
            <div style="font-size:.68rem;margin-top:3px;color:var(--muted)">Price is ${s.price > (s.ema200||0) ? '🟢 ABOVE (Bullish)' : '🔴 BELOW (Bearish)'}</div>
        </div>
        <div class="ind-card">
            <div class="ind-label">BB Upper</div>
            <div class="ind-value" style="color:var(--purple)">${s.bb_upper ? '$'+s.bb_upper.toFixed(4) : '—'}</div>
            <div style="font-size:.68rem;margin-top:3px;color:var(--muted)">SHORT zone ≥ this</div>
        </div>
        <div class="ind-card">
            <div class="ind-label">BB Lower</div>
            <div class="ind-value" style="color:var(--purple)">${s.bb_lower ? '$'+s.bb_lower.toFixed(4) : '—'}</div>
            <div style="font-size:.68rem;margin-top:3px;color:var(--muted)">LONG zone ≤ this</div>
        </div>`;

    // Live Trade Info
    const tradeEl = document.getElementById('modal-trade');
    if (s.direction && s.direction !== 'FLAT') {
        tradeEl.style.display = '';
        if (!quiet) {
            tradeEl.innerHTML = `
                <div style="font-weight:700;margin-bottom:10px;color:${s.direction==='LONG'?'var(--green)':'var(--red)'}; display:flex; justify-content:space-between; align-items:center;">
                    <span>🔥 LIVE ${s.direction} POSITION</span>
                    <span style="font-size:0.75rem; color:var(--muted); font-weight:400;">⚡ WebSocket Active</span>
                </div>
                <div class="trade-row"><span>Entry Price</span><span style="color:var(--blue)">$${s.entry.toLocaleString('en',{minimumFractionDigits:4})}</span></div>
                <div class="trade-row"><span>Current Price</span><span id="modal-live-price" class="modal-live-price">$${s.price.toLocaleString('en',{minimumFractionDigits:4})}</span></div>
                <div class="trade-row"><span>Live Net PnL</span><span id="modal-live-pnl" class="modal-live-pnl ${s.upnl>=0?'pnl-pos':'pnl-neg'}">${s.upnl>=0?'+$':'-$'}${Math.abs(s.upnl).toFixed(6)}</span></div>
                <div class="trade-row"><span>Take Profit 🟢</span><span class="green">${s.tp_price ? '$'+s.tp_price.toLocaleString('en',{minimumFractionDigits:4}) : '—'}</span></div>
                <div class="trade-row"><span>Stop Loss 🔴</span><span class="red">${s.sl_price ? '$'+s.sl_price.toLocaleString('en',{minimumFractionDigits:4}) : '—'}</span></div>
                <button onclick="requestManualClose('${sym}')" class="close-manual-btn">🛑 Close Manually Now</button>
                `;
        } else {
             updateLiveDom(sym, s, s.price);
        }
    } else {
        tradeEl.style.display = 'none';
        tradeEl.innerHTML = '';
    }
}

function renderTable() {
    const rows = Object.entries(state.syms).map(([sym, s]) => {
        const inPos = s.direction && s.direction !== 'FLAT';
        const sig = s.signal || 'SCANNING';
        const sigClass = sig === 'LONG' ? 'buy' : sig === 'SHORT' ? 'sell' : 'neutral';
        return `<tr onclick="openModal('${sym}')" style="cursor:pointer">
            <td><strong>${sym}</strong></td>
            <td style="color:var(--blue)">$${(s.price||0).toLocaleString('en',{minimumFractionDigits:4})}</td>
            <td><span class="badge ${sigClass}">${sig}</span></td>
            <td><span class="badge ${inPos?s.direction.toLowerCase():'flat'}">${inPos?s.direction:'FLAT'}</span></td>
            <td style="color:${getRsiColor(s.rsi)}">${s.rsi !== null && s.rsi !== undefined ? s.rsi.toFixed(1) : '—'}</td>
            <td style="color:${getMacdColor(s.macd_hist)}">${s.macd_hist ? (s.macd_hist>0?'▲ ':'▼ ')+Math.abs(s.macd_hist).toFixed(6) : '—'}</td>
            <td class="${s.price>(s.ema200||0)?'green':'red'}">${s.ema200 ? '$'+s.ema200.toFixed(2) : '—'}</td>
            <td class="muted">${s.atr ? s.atr.toFixed(4) : '—'}</td>
            <td style="color:var(--purple)">${s.bb_upper ? '$'+s.bb_upper.toFixed(4) : '—'}</td>
            <td style="color:var(--purple)">${s.bb_lower ? '$'+s.bb_lower.toFixed(4) : '—'}</td>
            <td>${inPos ? '$'+s.entry.toLocaleString('en',{minimumFractionDigits:4}) : '—'}</td>
            <td class="green">${s.tp_price ? '$'+s.tp_price.toFixed(4) : '—'}</td>
            <td class="red">${s.sl_price ? '$'+s.sl_price.toFixed(4) : '—'}</td>
            <td class="${s.upnl>=0?'pnl-pos':'pnl-neg'}">${inPos?(s.upnl>=0?'+$':'-$')+Math.abs(s.upnl).toFixed(4):'—'}</td>
        </tr>`;
    });
    document.getElementById('mkt-tbody').innerHTML = rows.length ? rows.join('') : '<tr><td colspan="14" class="empty">Loading market data...</td></tr>';
    document.getElementById('mkt-count').textContent = rows.length + ' markets';
}

function renderActiveTrades() {
    const activeSys = Object.entries(state.syms).filter(([sym, s]) => s.direction && s.direction !== 'FLAT');
    document.getElementById('act-count').textContent = activeSys.length + ' active trades';
    
    if (!activeSys.length) {
        document.getElementById('act-tbody').innerHTML = '<tr><td colspan="7" class="empty">No active trades right now. Bot is scanning the market for entries...</td></tr>';
        return;
    }
    
    const rows = activeSys.map(([sym, s]) => {
        return `<tr id="act-row-${sym}" onclick="openModal('${sym}')" style="cursor:pointer; background:rgba(79,142,247,.08)">
            <td><strong>${sym}</strong></td>
            <td><span class="badge ${s.direction.toLowerCase()}">${s.direction}</span></td>
            <td>$${(s.entry||0).toLocaleString('en',{minimumFractionDigits:4})}</td>
            <td class="live-price" style="color:var(--blue)">$${(s.price||0).toLocaleString('en',{minimumFractionDigits:4})}</td>
            <td class="green">${s.tp_price ? '$'+s.tp_price.toLocaleString('en',{minimumFractionDigits:4}) : '—'}</td>
            <td class="red">${s.sl_price ? '$'+s.sl_price.toLocaleString('en',{minimumFractionDigits:4}) : '—'}</td>
            <td class="live-pnl ${s.upnl>=0?'pnl-pos':'pnl-neg'}" style="font-size:1.1rem">${s.upnl>=0?'+$':'-$'}${Math.abs(s.upnl).toFixed(6)}</td>
        </tr>`;
    });
    
    document.getElementById('act-tbody').innerHTML = rows.join('');
}

function renderHistory() {
    const recent = [...state.trades].reverse();
    document.getElementById('hist-count').textContent = recent.length + ' trades';
    if (!recent.length) {
        document.getElementById('hist-tbody').innerHTML = '<tr><td colspan="12" class="empty">No trades yet. Bot is scanning...</td></tr>';
        return;
    }
    document.getElementById('hist-tbody').innerHTML = recent.map((t,i) => {
        const isClose = t.action && t.action.startsWith('CLOSE');
        const pnl = t.pnl !== null && t.pnl !== undefined;
        const pnlStr = pnl ? ((t.pnl>=0?'+$':'-$')+Math.abs(t.pnl).toFixed(4)) : '—';
        const pnlCls = t.pnl > 0 ? 'pnl-pos' : t.pnl < 0 ? 'pnl-neg' : '';
        const entryP = isClose && t.entry_price ? '$'+t.entry_price.toFixed(4) : (t.price ? '$'+t.price.toFixed(4) : '—');
        const exitP = isClose && t.price ? '$'+t.price.toFixed(4) : '—';
        return `<tr>
            <td class="muted">${recent.length-i}</td>
            <td class="muted">${t.timestamp||'—'}</td>
            <td><strong>${t.symbol||'—'}</strong></td>
            <td class="${isClose?'act-close':'act-open'}">${t.action||'—'}</td>
            <td>${entryP}</td><td>${exitP}</td>
            <td class="muted">${t.size?t.size.toFixed(4):'—'}</td>
            <td>$${(t.notional||0).toFixed(2)}</td>
            <td class="muted">-$${(t.fee||0).toFixed(4)}</td>
            <td class="${pnlCls}">${pnlStr}</td>
            <td class="muted">$${(t.balance_before||0).toFixed(4)}</td>
            <td class="${isClose&&t.pnl>0?'pnl-pos':isClose&&t.pnl<0?'pnl-neg':''}">$${(t.balance||0).toFixed(4)}</td>
        </tr>`;
    }).join('');
}

function closeModal(e) {
    if (!e || e.target === document.getElementById('modal') || e.target.classList.contains('close-btn')) {
        document.getElementById('modal').classList.remove('open');
        currentSym = null;
        if (modalChart) modalChart = null;
    }
}

refresh();
setInterval(refresh, 10000);
</script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

@app.route('/ping')
def ping():
    return "pong", 200

@app.route('/api/state')
def api_state():
    trades = []
    if os.path.exists(TRADE_LOG_FILE):
        try:
            with open(TRADE_LOG_FILE, "r") as f:
                trades = json.load(f)
        except:
            trades = []

    symbols = dashboard_state.get("symbols", {})
    if not symbols:
        symbols = _fetch_live_prices()

    return jsonify({
        "bot_status": dashboard_state.get("bot_status", "RUNNING 🟢"),
        "last_update": dashboard_state.get("last_update", ""),
        "symbols": symbols,
        "trades": trades,
        # Real-time balance fields populated by the main bot loop
        "live_balance": dashboard_state.get("live_balance"),      # cash + unrealized PnL
        "realized_cash": dashboard_state.get("realized_cash"),    # closed-trade cash only
        "total_upnl": dashboard_state.get("total_upnl"),          # sum of all open pos uPnL
        "open_trade_count": dashboard_state.get("open_trade_count", 0),
        "max_trades": dashboard_state.get("max_trades", 3),
    })

@app.route('/api/update', methods=['POST'])
def update_state():
    data = request.json
    dashboard_state.update(data)
    return jsonify({"ok": True})

@app.route('/api/close_trade/<symbol>', methods=['POST'])
def close_trade(symbol):
    manual_close_requests.add(symbol)
    return jsonify({"ok": True, "msg": f"Requested close for {symbol}"})

def run_dashboard(host="0.0.0.0", port=None):
    if port is None:
        port = int(os.environ.get('PORT', 5000))
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host=host, port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
