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
<title>ProfitBot Pro — Chart Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://unpkg.com/lightweight-charts@4.0.0/dist/lightweight-charts.standalone.production.js"></script>
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

/* Full Chart Modal */
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
.modal-chart { width:100%; height:340px; border-radius:10px; overflow:hidden; }
.indicator-row { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:10px; margin:14px 0; }
.ind-card { background:var(--card2); border:1px solid var(--border); border-radius:10px; padding:12px; }
.ind-label { font-size:0.65rem; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; margin-bottom:5px; }
.ind-value { font-size:1.1rem; font-weight:600; }
.trade-info { background:var(--card2); border:1px solid var(--border); border-radius:10px; padding:14px; margin-top:12px; }
.trade-row { display:flex; justify-content:space-between; font-size:0.82rem; margin:6px 0; }
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
        <div class="stat"><div class="stat-label">💰 Balance</div><div class="stat-value blue" id="s-bal">$3.00</div><div class="stat-sub" id="s-bal-chg">Starting: $3.00</div></div>
        <div class="stat"><div class="stat-label">📡 Scanning</div><div class="stat-value blue" id="s-scan">—</div><div class="stat-sub">Markets</div></div>
        <div class="stat"><div class="stat-label">🔥 Open Positions</div><div class="stat-value yellow" id="s-open">0</div><div class="stat-sub">Live Trades</div></div>
        <div class="stat"><div class="stat-label">📈 Total Trades</div><div class="stat-value" id="s-total">0</div><div class="stat-sub">Paper Mode</div></div>
        <div class="stat"><div class="stat-label">🎯 Win Rate</div><div class="stat-value green" id="s-wr">—</div><div class="stat-sub">Closed Trades</div></div>
        <div class="stat"><div class="stat-label">💵 Net PnL</div><div class="stat-value" id="s-pnl">+$0.00</div><div class="stat-sub">After Fees</div></div>
    </div>

    <!-- View Controls -->
    <div class="view-bar">
        <button class="view-btn active" onclick="setView('charts')">📊 Charts</button>
        <button class="view-btn" onclick="setView('table')">📋 Market Table</button>
        <button class="view-btn" onclick="setView('history')">📂 Trade History</button>
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
let state = {syms:{}, trades:[], view:'charts'};
let miniCharts = {};
let modalChart = null;
let currentSym = null;

function setView(v) {
    state.view = v;
    document.getElementById('view-charts').style.display = v==='charts' ? '' : 'none';
    document.getElementById('view-table').style.display = v==='table' ? '' : 'none';
    document.getElementById('view-history').style.display = v==='history' ? '' : 'none';
    document.querySelectorAll('.view-btn').forEach((b,i)=>b.classList.toggle('active',['charts','table','history'][i]===v));
    if (v==='table') renderTable();
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
        const lastBal = state.trades.length > 0 ? state.trades[state.trades.length-1].balance : 3.0;
        const balChg = lastBal - 3.0;
        const openPos = Object.values(state.syms).filter(s => s.direction && s.direction !== 'FLAT');

        document.getElementById('s-bal').textContent = '$'+parseFloat(lastBal).toFixed(4);
        document.getElementById('s-bal-chg').textContent = (balChg>=0?'▲ +':'▼ ')+'$'+Math.abs(balChg).toFixed(4);
        document.getElementById('s-bal-chg').className = 'stat-sub '+(balChg>=0?'green':'red');
        document.getElementById('s-scan').textContent = Object.keys(state.syms).length;
        document.getElementById('s-open').textContent = openPos.length;
        document.getElementById('s-total').textContent = state.trades.length;
        document.getElementById('s-wr').textContent = wr ? wr+'%' : '—';
        document.getElementById('s-pnl').textContent = (netPnl>=0?'+$':'-$')+Math.abs(netPnl).toFixed(4);
        document.getElementById('s-pnl').className = 'stat-value '+(netPnl>=0?'green':'red');

        if (state.view === 'charts') renderSymbols();
        if (state.view === 'table') renderTable();
        if (state.view === 'history') renderHistory();
        if (currentSym && state.syms[currentSym]) updateModal(currentSym);
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
                <div class="chart-container" id="chart-${sym}"></div>
                <div class="card-footer">
                    <span class="indicator-pill" id="rsi-${sym}">RSI: ${s.rsi ? s.rsi.toFixed(1) : '—'}</span>
                    <span class="indicator-pill" id="macd-${sym}">MACD: ${s.macd_hist ? (s.macd_hist > 0 ? '▲' : '▼') : '—'}</span>
                    <span class="indicator-pill" id="atr-${sym}">ATR: ${s.atr ? s.atr.toFixed(4) : '—'}</span>
                    ${inPos ? `<span class="indicator-pill pnl-${(s.upnl||0)>=0?'pos':'neg'}" id="upnl-${sym}">${(s.upnl||0)>=0?'+$':'-$'}${Math.abs(s.upnl||0).toFixed(4)}</span>` : ''}
                </div>`;
            grid.appendChild(card);

            // Draw mini chart
            if (s.candles && s.candles.length > 0) {
                drawMiniChart(sym, s.candles, s);
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
        }
    });
}

function drawMiniChart(sym, candles, s) {
    const el = document.getElementById('chart-'+sym);
    if (!el || miniCharts[sym]) return;
    const chart = LightweightCharts.createChart(el, {
        width: el.clientWidth || 280, height: 120,
        layout:{ background:{color:'transparent'}, textColor:'transparent' },
        grid:{ vertLines:{visible:false}, horzLines:{color:'rgba(26,39,68,0.5)'} },
        crosshair:{ mode: LightweightCharts.CrosshairMode.Hidden },
        handleScroll:false, handleScale:false,
        timeScale:{ visible:false }
    });
    const series = chart.addCandlestickSeries({
        upColor:'#00e5a0', downColor:'#ff4d6d',
        borderUpColor:'#00e5a0', borderDownColor:'#ff4d6d',
        wickUpColor:'#00e5a0', wickDownColor:'#ff4d6d'
    });
    const data = candles.map(c => ({
        time: Math.floor(c.t/1000), open:c.o, high:c.h, low:c.l, close:c.c
    }));
    series.setData(data);

    // Draw BB if available
    if (s.bb_upper && s.bb_lower) {
        const bbU = chart.addLineSeries({ color:'rgba(167,139,250,0.4)', lineWidth:1, priceLineVisible:false, lastValueVisible:false });
        const bbL = chart.addLineSeries({ color:'rgba(167,139,250,0.4)', lineWidth:1, priceLineVisible:false, lastValueVisible:false });
        const lastT = data[data.length-1]?.time;
        if (lastT) {
            bbU.setData([{time:lastT, value:s.bb_upper}]);
            bbL.setData([{time:lastT, value:s.bb_lower}]);
        }
    }
    chart.timeScale().fitContent();
    miniCharts[sym] = chart;
}

function openModal(sym) {
    currentSym = sym;
    document.getElementById('modal').classList.add('open');
    document.getElementById('modal-title').textContent = sym;
    updateModal(sym);
}

function updateModal(sym) {
    const s = state.syms[sym];
    if (!s) return;
    const el = document.getElementById('modal-chart');
    el.innerHTML = '';

    if (modalChart) { try { modalChart.remove(); } catch(e){} modalChart = null; }

    modalChart = LightweightCharts.createChart(el, {
        width: el.clientWidth || 900, height: 340,
        layout:{ background:{color:'#0a1428'}, textColor:'#5a7099' },
        grid:{ vertLines:{color:'rgba(26,39,68,0.5)'}, horzLines:{color:'rgba(26,39,68,0.5)'} },
        crosshair:{ mode: LightweightCharts.CrosshairMode.Magnet },
        timeScale:{ timeVisible:true, secondsVisible:false }
    });

    const candleSeries = modalChart.addCandlestickSeries({
        upColor:'#00e5a0', downColor:'#ff4d6d',
        borderUpColor:'#00e5a0', borderDownColor:'#ff4d6d',
        wickUpColor:'#00e5a0', wickDownColor:'#ff4d6d'
    });

    if (s.candles && s.candles.length > 0) {
        const data = s.candles.map(c => ({
            time: Math.floor(c.t/1000), open:c.o, high:c.h, low:c.l, close:c.c
        }));
        candleSeries.setData(data);

        // EMA 200 line - show as reference
        if (s.ema200 > 0) {
            const ema = modalChart.addLineSeries({ color:'#4f8ef7', lineWidth:1, title:'EMA200', priceLineVisible:false });
            ema.setData(data.map(d => ({time:d.time, value:s.ema200})));
        }
        // BB Bands
        if (s.bb_upper && s.bb_lower) {
            const bbU = modalChart.addLineSeries({ color:'rgba(167,139,250,0.6)', lineWidth:1, title:'BB Upper', priceLineVisible:false, lastValueVisible:false });
            const bbM = modalChart.addLineSeries({ color:'rgba(167,139,250,0.3)', lineWidth:1, lineStyle:2, priceLineVisible:false, lastValueVisible:false });
            const bbL = modalChart.addLineSeries({ color:'rgba(167,139,250,0.6)', lineWidth:1, title:'BB Lower', priceLineVisible:false, lastValueVisible:false });
            bbU.setData(data.map(d => ({time:d.time, value:s.bb_upper})));
            bbM.setData(data.map(d => ({time:d.time, value:s.bb_middle})));
            bbL.setData(data.map(d => ({time:d.time, value:s.bb_lower})));
        }
        // Entry, TP, SL price lines
        if (s.entry > 0) {
            candleSeries.createPriceLine({ price:s.entry, color:'#4f8ef7', lineWidth:1, title:'Entry', lineStyle:2 });
        }
        if (s.tp_price) {
            candleSeries.createPriceLine({ price:s.tp_price, color:'#00e5a0', lineWidth:2, title:'TP', lineStyle:0 });
        }
        if (s.sl_price) {
            candleSeries.createPriceLine({ price:s.sl_price, color:'#ff4d6d', lineWidth:2, title:'SL', lineStyle:0 });
        }
        modalChart.timeScale().fitContent();
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
        tradeEl.innerHTML = `
            <div style="font-weight:700;margin-bottom:10px;color:${s.direction==='LONG'?'var(--green)':'var(--red)'}">
                🔥 LIVE ${s.direction} POSITION
            </div>
            <div class="trade-row"><span>Entry Price</span><span style="color:var(--blue)">$${s.entry.toLocaleString('en',{minimumFractionDigits:4})}</span></div>
            <div class="trade-row"><span>Current Price</span><span>$${s.price.toLocaleString('en',{minimumFractionDigits:4})}</span></div>
            <div class="trade-row"><span>Unrealized PnL</span><span class="${s.upnl>=0?'pnl-pos':'pnl-neg'}">${s.upnl>=0?'+$':'-$'}${Math.abs(s.upnl).toFixed(4)}</span></div>
            <div class="trade-row"><span>Take Profit 🟢</span><span class="green">${s.tp_price ? '$'+s.tp_price.toLocaleString('en',{minimumFractionDigits:4}) : '—'}</span></div>
            <div class="trade-row"><span>Stop Loss 🔴</span><span class="red">${s.sl_price ? '$'+s.sl_price.toLocaleString('en',{minimumFractionDigits:4}) : '—'}</span></div>`;
    } else {
        tradeEl.style.display = 'none';
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
    if (!e || e.target === document.getElementById('modal')) {
        document.getElementById('modal').classList.remove('open');
        currentSym = null;
        if (modalChart) { try{modalChart.remove();}catch(e){} modalChart=null; }
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
        "trades": trades
    })

@app.route('/api/update', methods=['POST'])
def update_state():
    data = request.json
    dashboard_state.update(data)
    return jsonify({"ok": True})

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
