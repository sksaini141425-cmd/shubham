"""
ProfitBot Pro - Live Paper Trading Dashboard
Serves a real-time dashboard accessible in any browser.
"""
from flask import Flask, jsonify, render_template_string
import json
import os
import time

app = Flask(__name__)

# Shared state - will be updated by main.py
dashboard_state = {
    "bot_status": "STARTING",
    "last_update": "",
    "symbols": {}
}

TRADE_LOG_FILE = "trade_log.json"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ProfitBot Pro — Live Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #060b18; --card: #0d1526; --card2: #111d35;
            --border: #1a2744; --green: #00e5a0; --red: #ff4d6d;
            --yellow: #f5a623; --blue: #4f8ef7; --purple: #a78bfa;
            --text: #e8f0fe; --muted: #5a7099;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }

        .header {
            display: flex; align-items: center; justify-content: space-between;
            padding: 16px 28px;
            background: linear-gradient(90deg, #060b18 0%, #0d1a3a 50%, #060b18 100%);
            border-bottom: 1px solid var(--border);
            position: sticky; top: 0; z-index: 100;
        }
        .logo { font-size: 1.4rem; font-weight: 800; letter-spacing: -0.5px;
            background: linear-gradient(90deg, #4f8ef7, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .status-pill { display: flex; align-items: center; gap: 8px; background: var(--card2);
            border: 1px solid var(--border); border-radius: 100px; padding: 6px 14px; font-size: 0.8rem; }
        .dot { width: 8px; height: 8px; border-radius: 50%; animation: pulse 2s infinite; }
        .dot.green { background: var(--green); box-shadow: 0 0 8px var(--green); }
        .dot.red { background: var(--red); }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

        .container { max-width: 1400px; margin: 0 auto; padding: 24px 20px; }

        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 24px; }
        .stat-card { background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 18px 20px;
            transition: transform 0.2s, box-shadow 0.2s; }
        .stat-card:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,0.3); }
        .stat-label { font-size: 0.7rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.07em; margin-bottom: 10px; }
        .stat-value { font-size: 2rem; font-weight: 700; line-height: 1; }
        .stat-sub { font-size: 0.75rem; color: var(--muted); margin-top: 6px; }

        .section { background: var(--card); border: 1px solid var(--border); border-radius: 14px; overflow: hidden; margin-bottom: 24px; }
        .section-header { padding: 14px 20px; border-bottom: 1px solid var(--border); font-weight: 600; font-size: 0.9rem;
            display: flex; justify-content: space-between; align-items: center; }
        .section-header .count { background: var(--card2); border: 1px solid var(--border);
            border-radius: 100px; padding: 2px 10px; font-size: 0.75rem; color: var(--muted); }

        .green { color: var(--green); } .red { color: var(--red); }
        .yellow { color: var(--yellow); } .blue { color: var(--blue); } .muted { color: var(--muted); }

        /* Markets Table */
        .markets-table-wrap { overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
        th { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.07em; color: var(--muted);
            padding: 10px 16px; text-align: left; border-bottom: 1px solid var(--border); white-space: nowrap;
            background: var(--card2); }
        td { padding: 11px 16px; border-bottom: 1px solid rgba(255,255,255,0.04); white-space: nowrap; }
        tr:last-child td { border-bottom: none; }
        tr:hover td { background: rgba(79,142,247,0.04); }

        .badge { display: inline-block; padding: 3px 9px; border-radius: 100px; font-size: 0.7rem; font-weight: 700; }
        .badge.long { background: rgba(0,229,160,0.12); color: var(--green); }
        .badge.short { background: rgba(255,77,109,0.12); color: var(--red); }
        .badge.flat { background: rgba(90,112,153,0.12); color: var(--muted); }
        .badge.buy { background: rgba(0,229,160,0.12); color: var(--green); }
        .badge.sell { background: rgba(255,77,109,0.12); color: var(--red); }
        .badge.neutral { background: rgba(90,112,153,0.12); color: var(--muted); }

        .pnl-pos { color: var(--green); font-weight: 600; }
        .pnl-neg { color: var(--red); font-weight: 600; }
        .action-open { color: var(--blue); font-weight: 600; }
        .action-close { color: var(--yellow); font-weight: 600; }

        .empty { padding: 48px 20px; text-align: center; color: var(--muted); font-size: 0.85rem; }
        .loader { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 8px;
            background: var(--blue); animation: pulse 1.5s infinite; }

        .footer { text-align: center; color: var(--muted); font-size: 0.72rem; padding: 20px; border-top: 1px solid var(--border); }
        .tabs { display: flex; gap: 0; border-bottom: 1px solid var(--border); }
        .tab { padding: 12px 20px; font-size: 0.82rem; cursor: pointer; border-bottom: 2px solid transparent;
            transition: color 0.2s, border-color 0.2s; color: var(--muted); }
        .tab.active { color: var(--blue); border-bottom-color: var(--blue); }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">🤖 ProfitBot Pro</div>
        <div style="display:flex;align-items:center;gap:12px;">
            <span style="font-size:0.75rem;color:var(--muted)" id="last-update">Connecting...</span>
            <div class="status-pill">
                <div class="dot green" id="status-dot"></div>
                <span id="bot-status">LIVE</span>
            </div>
        </div>
    </div>

    <div class="container">
        <!-- Stats -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">💰 Balance</div>
                <div class="stat-value blue" id="balance">$3.00</div>
                <div class="stat-sub" id="balance-change">Starting: $3.00</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">📊 Scanning</div>
                <div class="stat-value blue" id="scanning-count">—</div>
                <div class="stat-sub">Active Markets</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">🔥 Open Positions</div>
                <div class="stat-value yellow" id="open-positions">0</div>
                <div class="stat-sub">Live Trades</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">📈 Total Trades</div>
                <div class="stat-value" id="total-trades">0</div>
                <div class="stat-sub">Paper Trading Mode</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">🎯 Win Rate</div>
                <div class="stat-value green" id="win-rate">—</div>
                <div class="stat-sub">Closed Trades</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">💵 Net PnL</div>
                <div class="stat-value" id="net-pnl">+$0.00</div>
                <div class="stat-sub">After Binance Fees</div>
            </div>
        </div>

        <!-- Markets Section with Tabs -->
        <div class="section">
            <div class="section-header">
                <span>📡 Market Scanner</span>
                <span class="count" id="market-count">Loading...</span>
            </div>
            <div class="tabs">
                <div class="tab active" onclick="switchTab('positions')">🔥 Open Positions</div>
                <div class="tab" onclick="switchTab('all-markets')">🌐 All Markets</div>
                <div class="tab" onclick="switchTab('signals')">⚡ Active Signals</div>
            </div>
            <div id="tab-positions" class="tab-content active">
                <div id="positions-content"><div class="empty">Bot is scanning... No open positions.</div></div>
            </div>
            <div id="tab-all-markets" class="tab-content">
                <div class="markets-table-wrap">
                    <table>
                        <thead><tr>
                            <th>Symbol</th><th>Price</th><th>Signal</th>
                            <th>Position</th><th>Entry</th><th>Unrealized PnL</th>
                            <th>Min Notional</th><th>Fee</th>
                        </tr></thead>
                        <tbody id="markets-table"><tr><td colspan="8" class="empty"><span class="loader"></span>Loading markets...</td></tr></tbody>
                    </table>
                </div>
            </div>
            <div id="tab-signals" class="tab-content">
                <div class="markets-table-wrap">
                    <table>
                        <thead><tr><th>Symbol</th><th>Signal</th><th>Price</th><th>Position</th></tr></thead>
                        <tbody id="signals-table"><tr><td colspan="4" class="empty">No active signals.</td></tr></tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Trade History -->
        <div class="section">
            <div class="section-header">
                <span>📋 Trade History</span>
                <span class="count" id="trade-count">0 trades</span>
            </div>
            <div class="markets-table-wrap">
                <table>
                    <thead><tr>
                        <th>#</th><th>Time</th><th>Symbol</th><th>Action</th>
                        <th>Entry Price</th><th>Exit Price</th>
                        <th>Size</th><th>Notional</th>
                        <th>Fee</th><th>PnL</th>
                        <th>Bal Before</th><th>Bal After</th>
                    </tr></thead>
                    <tbody id="trade-table"><tr><td colspan="12" class="empty"><span class="loader"></span>Scanning for trades...</td></tr></tbody>
                </table>
            </div>
        </div>

        <div class="footer">ProfitBot Pro — Anti-Loss Edition 🛡️ | Smart Money: EMA + MACD + RSI + ATR Trailing SL | Auto-refreshes every 5s</div>
    </div>

    <script>
    function switchTab(tab) {
        document.querySelectorAll('.tab').forEach((t,i) => t.classList.toggle('active', ['positions','all-markets','signals'][i] === tab));
        document.querySelectorAll('.tab-content').forEach((c,i) => c.classList.toggle('active', ['tab-positions','tab-all-markets','tab-signals'][i] === 'tab-'+tab));
    }

    async function refresh() {
        try {
            const r = await fetch('/api/state');
            const d = await r.json();

            document.getElementById('last-update').textContent = 'Updated: ' + new Date().toLocaleTimeString();
            document.getElementById('bot-status').textContent = d.bot_status || 'RUNNING';

            const syms = d.symbols || {};
            const trades = d.trades || [];
            const closedTrades = trades.filter(t => t.action && t.action.startsWith('CLOSE'));
            const wins = closedTrades.filter(t => t.pnl > 0);
            const netPnl = closedTrades.reduce((s, t) => s + (t.pnl || 0), 0);
            const winRate = closedTrades.length > 0 ? ((wins.length / closedTrades.length) * 100).toFixed(1) : null;
            const openPositions = Object.values(syms).filter(s => s.direction && s.direction !== 'FLAT');
            const lastBal = trades.length > 0 ? trades[trades.length - 1].balance : 3.0;
            const balChange = lastBal - 3.0;

            document.getElementById('balance').textContent = '$' + parseFloat(lastBal).toFixed(4);
            document.getElementById('balance-change').textContent = (balChange >= 0 ? '▲ +' : '▼ ') + '$' + Math.abs(balChange).toFixed(4) + ' from start';
            document.getElementById('balance-change').className = 'stat-sub ' + (balChange >= 0 ? 'green' : 'red');
            document.getElementById('scanning-count').textContent = Object.keys(syms).length;
            document.getElementById('open-positions').textContent = openPositions.length;
            document.getElementById('total-trades').textContent = trades.length;
            document.getElementById('win-rate').textContent = winRate ? winRate + '%' : '—';
            document.getElementById('win-rate').className = 'stat-value ' + (winRate >= 60 ? 'green' : winRate ? 'yellow' : 'green');
            document.getElementById('net-pnl').textContent = (netPnl >= 0 ? '+$' : '-$') + Math.abs(netPnl).toFixed(4);
            document.getElementById('net-pnl').className = 'stat-value ' + (netPnl >= 0 ? 'green' : 'red');
            document.getElementById('market-count').textContent = Object.keys(syms).length + ' markets';
            document.getElementById('trade-count').textContent = trades.length + ' trades';

            // Open Positions Tab
            const posEl = document.getElementById('positions-content');
            if (openPositions.length === 0) {
                posEl.innerHTML = '<div class="empty">🔍 Bot is scanning... No open positions right now.</div>';
            } else {
                posEl.innerHTML = '<table><thead><tr><th>Symbol</th><th>Direction</th><th>Entry</th><th>Current Price</th><th>Unrealized PnL</th><th>Fee</th></tr></thead><tbody>' +
                    Object.entries(syms).filter(([,s]) => s.direction && s.direction !== 'FLAT').map(([sym, s]) => `
                    <tr>
                        <td><strong>${sym}</strong></td>
                        <td><span class="badge ${s.direction.toLowerCase()}">${s.direction}</span></td>
                        <td>$${(s.entry||0).toLocaleString('en', {minimumFractionDigits:4})}</td>
                        <td>$${(s.price||0).toLocaleString('en', {minimumFractionDigits:4})}</td>
                        <td class="${s.upnl >= 0 ? 'pnl-pos' : 'pnl-neg'}">${s.upnl >= 0 ? '+$' : '-$'}${Math.abs(s.upnl||0).toFixed(4)}</td>
                        <td class="muted">${s.fee_pct || '—'}</td>
                    </tr>`).join('') + '</tbody></table>';
            }

            // All Markets Tab
            const mRows = Object.entries(syms).map(([sym, s]) => {
                const sig = s.signal || 'NEUTRAL';
                const dir = s.direction || 'FLAT';
                const sigClass = sig === 'LONG' ? 'buy' : sig === 'SHORT' ? 'sell' : 'neutral';
                const dirClass = dir.toLowerCase();
                return `<tr>
                    <td><strong>${sym}</strong></td>
                    <td>$${(s.price||0).toLocaleString('en', {minimumFractionDigits:4})}</td>
                    <td><span class="badge ${sigClass}">${sig}</span></td>
                    <td><span class="badge ${dirClass}">${dir}</span></td>
                    <td>${s.entry > 0 ? '$'+s.entry.toLocaleString('en',{minimumFractionDigits:4}) : '—'}</td>
                    <td class="${s.upnl >= 0 ? 'pnl-pos' : 'pnl-neg'}">${s.direction !== 'FLAT' ? (s.upnl >= 0 ? '+$' : '-$') + Math.abs(s.upnl||0).toFixed(4) : '—'}</td>
                    <td class="muted">$${(s.min_notional||0).toFixed(2)}</td>
                    <td class="muted">${s.fee_pct || '—'}</td>
                </tr>`;
            });
            document.getElementById('markets-table').innerHTML = mRows.length > 0 ? mRows.join('') : '<tr><td colspan="8" class="empty">Loading market data...</td></tr>';

            // Signals Tab (only LONG/SHORT)
            const sigRows = Object.entries(syms).filter(([,s]) => s.signal && s.signal !== 'NEUTRAL').map(([sym, s]) => `
                <tr>
                    <td><strong>${sym}</strong></td>
                    <td><span class="badge ${s.signal === 'LONG' ? 'buy' : 'sell'}">${s.signal}</span></td>
                    <td>$${(s.price||0).toLocaleString('en', {minimumFractionDigits:4})}</td>
                    <td><span class="badge ${(s.direction||'FLAT').toLowerCase()}">${s.direction||'FLAT'}</span></td>
                </tr>`);
            document.getElementById('signals-table').innerHTML = sigRows.length > 0 ? sigRows.join('') : '<tr><td colspan="4" class="empty">No active LONG/SHORT signals right now.</td></tr>';

            // Trade History
            const recent = [...trades].reverse();
            if (recent.length === 0) {
                document.getElementById('trade-table').innerHTML = '<tr><td colspan="12" class="empty">No trades yet. Bot is scanning for high-conviction setups...</td></tr>';
            } else {
                document.getElementById('trade-table').innerHTML = recent.map((t, i) => {
                    const isClose = t.action && t.action.startsWith('CLOSE');
                    const pnlClass = t.pnl > 0 ? 'pnl-pos' : t.pnl < 0 ? 'pnl-neg' : '';
                    const pnlStr = t.pnl !== null && t.pnl !== undefined ? ((t.pnl >= 0 ? '+$' : '-$') + Math.abs(t.pnl).toFixed(4)) : '—';
                    const entryP = isClose && t.entry_price ? '$' + t.entry_price.toLocaleString('en',{minimumFractionDigits:4}) : (t.price ? '$'+t.price.toLocaleString('en',{minimumFractionDigits:4}) : '—');
                    const exitP = isClose && t.price ? '$' + t.price.toLocaleString('en',{minimumFractionDigits:4}) : '—';
                    return `<tr>
                        <td class="muted">${recent.length - i}</td>
                        <td class="muted">${t.timestamp || '—'}</td>
                        <td><strong>${t.symbol || '—'}</strong></td>
                        <td class="${isClose ? 'action-close' : 'action-open'}">${t.action || '—'}</td>
                        <td>${entryP}</td>
                        <td>${exitP}</td>
                        <td class="muted">${t.size ? t.size.toFixed(4) : '—'}</td>
                        <td>$${(t.notional||0).toFixed(2)}</td>
                        <td class="muted">-$${(t.fee||0).toFixed(4)}</td>
                        <td class="${pnlClass}">${pnlStr}</td>
                        <td class="muted">$${(t.balance_before||0).toFixed(4)}</td>
                        <td class="${isClose ? (t.pnl > 0 ? 'pnl-pos' : 'pnl-neg') : ''}">$${(t.balance||0).toFixed(4)}</td>
                    </tr>`;
                }).join('');
            }
        } catch (e) {
            document.getElementById('last-update').textContent = 'Connection error — retrying...';
        }
    }

    refresh();
    setInterval(refresh, 5000);
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

    return jsonify({
        "bot_status": dashboard_state.get("bot_status", "RUNNING"),
        "last_update": dashboard_state.get("last_update", ""),
        "symbols": dashboard_state.get("symbols", {}),
        "trades": trades
    })

@app.route('/api/update', methods=['POST'])
def update_state():
    """Called by main.py to push live state."""
    from flask import request
    data = request.json
    dashboard_state.update(data)
    return jsonify({"ok": True})

def run_dashboard(host="0.0.0.0", port=None):
    """Run Flask dashboard in a background thread."""
    if port is None:
        port = int(os.environ.get('PORT', 5000))
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host=host, port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting ProfitBot Pro Dashboard at http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
