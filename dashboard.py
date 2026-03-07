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
            --bg: #0a0e1a; --card: #111827; --border: #1f2937;
            --green: #10b981; --red: #ef4444; --yellow: #f59e0b;
            --blue: #3b82f6; --purple: #8b5cf6; --text: #f9fafb;
            --muted: #6b7280;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
        
        .header { display: flex; align-items: center; justify-content: space-between; padding: 20px 24px;
            background: linear-gradient(135deg, #0f172a, #1e1b4b); border-bottom: 1px solid var(--border); }
        .logo { font-size: 1.5rem; font-weight: 700; background: linear-gradient(90deg, #3b82f6, #8b5cf6); 
            -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .status-badge { display: flex; align-items: center; gap: 8px; font-size: 0.85rem; }
        .dot { width: 9px; height: 9px; border-radius: 50%; animation: pulse 2s infinite; }
        .dot.green { background: var(--green); }
        .dot.red { background: var(--red); }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

        .container { max-width: 1200px; margin: 0 auto; padding: 24px; }
        
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .stat-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px;
            transition: transform 0.2s; }
        .stat-card:hover { transform: translateY(-2px); }
        .stat-label { font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }
        .stat-value { font-size: 1.8rem; font-weight: 700; }
        .stat-sub { font-size: 0.8rem; color: var(--muted); margin-top: 4px; }
        .green { color: var(--green); } .red { color: var(--red); } .yellow { color: var(--yellow); }
        .blue { color: var(--blue); }

        .section { background: var(--card); border: 1px solid var(--border); border-radius: 12px; 
            overflow: hidden; margin-bottom: 24px; }
        .section-header { padding: 16px 20px; border-bottom: 1px solid var(--border); font-weight: 600; font-size: 0.95rem;
            display: flex; align-items: center; gap: 8px; }

        .position-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; padding: 16px; }
        .position-card { background: #0f172a; border-radius: 10px; padding: 16px; border: 1px solid var(--border); }
        .pos-symbol { font-weight: 700; font-size: 1.1rem; margin-bottom: 8px; }
        .pos-row { display: flex; justify-content: space-between; font-size: 0.82rem; color: var(--muted); margin: 4px 0; }
        .pos-row span:last-child { color: var(--text); font-weight: 500; }
        .badge { display: inline-block; padding: 2px 10px; border-radius: 100px; font-size: 0.72rem; font-weight: 600; }
        .badge.long { background: rgba(16,185,129,0.15); color: var(--green); }
        .badge.short { background: rgba(239,68,68,0.15); color: var(--red); }
        .badge.flat { background: rgba(107,114,128,0.15); color: var(--muted); }

        table { width: 100%; border-collapse: collapse; }
        th { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted);
            padding: 10px 20px; text-align: left; border-bottom: 1px solid var(--border); }
        td { padding: 12px 20px; font-size: 0.85rem; border-bottom: 1px solid rgba(255,255,255,0.04); }
        tr:last-child td { border-bottom: none; }
        tr:hover td { background: rgba(255,255,255,0.02); }
        .pnl-positive { color: var(--green); font-weight: 600; }
        .pnl-negative { color: var(--red); font-weight: 600; }
        .action-open { color: var(--blue); font-weight: 500; }
        .action-close { color: var(--yellow); font-weight: 500; }

        .empty { padding: 40px; text-align: center; color: var(--muted); font-size: 0.9rem; }
        .footer { text-align: center; color: var(--muted); font-size: 0.75rem; padding: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">🤖 ProfitBot Pro</div>
        <div style="display:flex;align-items:center;gap:20px;">
            <span style="font-size:0.8rem;color:var(--muted)" id="last-update">Connecting...</span>
            <div class="status-badge">
                <div class="dot green" id="status-dot"></div>
                <span id="bot-status">LIVE</span>
            </div>
        </div>
    </div>

    <div class="container">
        <!-- Global Stats -->
        <div class="stats-grid" id="global-stats">
            <div class="stat-card">
                <div class="stat-label">💰 Balance</div>
                <div class="stat-value blue" id="balance">$0.00</div>
                <div class="stat-sub">Starting: $3.00</div>
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
                <div class="stat-value" id="net-pnl">$0.00</div>
                <div class="stat-sub">After Fees</div>
            </div>
        </div>

        <!-- Positions -->
        <div class="section">
            <div class="section-header">🔥 Live Positions</div>
            <div class="position-grid" id="positions">
                <div class="empty">Scanning for signals...</div>
            </div>
        </div>

        <!-- Trade History -->
        <div class="section">
            <div class="section-header">📋 Trade History (Last 50)</div>
            <div id="history-container">
                <table>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Symbol</th>
                            <th>Action</th>
                            <th>Price</th>
                            <th>Notional</th>
                            <th>PnL</th>
                            <th>Balance</th>
                        </tr>
                    </thead>
                    <tbody id="trade-table">
                        <tr><td colspan="7" class="empty">No trades yet. Bot is scanning...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="footer">ProfitBot Pro — Anti-Loss Edition 🛡️ | Refreshing every 5s</div>
    </div>

    <script>
    async function refresh() {
        try {
            const r = await fetch('/api/state');
            const d = await r.json();
            
            document.getElementById('last-update').textContent = 
                'Updated: ' + new Date().toLocaleTimeString();
            document.getElementById('bot-status').textContent = d.bot_status || 'RUNNING';

            // Compute stats from trade log
            const trades = d.trades || [];
            const closedTrades = trades.filter(t => t.action && t.action.startsWith('CLOSE'));
            const wins = closedTrades.filter(t => t.pnl > 0);
            const netPnl = closedTrades.reduce((s, t) => s + (t.pnl || 0), 0);
            const winRate = closedTrades.length > 0 ? ((wins.length / closedTrades.length) * 100).toFixed(1) : '—';
            
            // Balance from latest trade
            const lastBal = trades.length > 0 ? trades[trades.length - 1].balance : 3.0;
            
            document.getElementById('balance').textContent = '$' + parseFloat(lastBal).toFixed(4);
            document.getElementById('total-trades').textContent = trades.length;
            document.getElementById('win-rate').textContent = winRate !== '—' ? winRate + '%' : '—';
            document.getElementById('win-rate').className = 'stat-value ' + (parseFloat(winRate) >= 60 ? 'green' : 'yellow');
            document.getElementById('net-pnl').textContent = (netPnl >= 0 ? '+$' : '-$') + Math.abs(netPnl).toFixed(4);
            document.getElementById('net-pnl').className = 'stat-value ' + (netPnl >= 0 ? 'green' : 'red');

            // Positions
            const posEl = document.getElementById('positions');
            const syms = d.symbols || {};
            if (Object.keys(syms).length === 0) {
                posEl.innerHTML = '<div class="empty">Bot is scanning... No open positions.</div>';
            } else {
                posEl.innerHTML = Object.entries(syms).map(([sym, s]) => `
                    <div class="position-card">
                        <div class="pos-symbol">${sym} <span class="badge ${(s.direction || 'flat').toLowerCase()}">${s.direction || 'FLAT'}</span></div>
                        <div class="pos-row"><span>Price</span><span>$${(s.price || 0).toLocaleString()}</span></div>
                        <div class="pos-row"><span>Signal</span><span class="${s.signal === 'LONG' ? 'green' : s.signal === 'SHORT' ? 'red' : ''}">${s.signal || '—'}</span></div>
                        <div class="pos-row"><span>Entry</span><span>${s.entry > 0 ? '$' + s.entry.toLocaleString() : '—'}</span></div>
                        <div class="pos-row"><span>uPnL</span><span class="${s.upnl >= 0 ? 'green' : 'red'}">${s.upnl !== undefined ? (s.upnl >= 0 ? '+$' : '-$') + Math.abs(s.upnl).toFixed(4) : '—'}</span></div>
                    </div>
                `).join('');
            }

            // Trade History
            const tbody = document.getElementById('trade-table');
            const recent = [...trades].reverse().slice(0, 50);
            if (recent.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="empty">No trades yet. Bot is scanning...</td></tr>';
            } else {
                tbody.innerHTML = recent.map(t => {
                    const isClose = t.action && t.action.startsWith('CLOSE');
                    const pnlClass = t.pnl > 0 ? 'pnl-positive' : t.pnl < 0 ? 'pnl-negative' : '';
                    const pnlStr = t.pnl !== null && t.pnl !== undefined ? 
                        ((t.pnl >= 0 ? '+$' : '-$') + Math.abs(t.pnl).toFixed(4)) : '—';
                    return `<tr>
                        <td>${t.timestamp}</td>
                        <td><strong>${t.symbol || 'BTC'}</strong></td>
                        <td class="${isClose ? 'action-close' : 'action-open'}">${t.action}</td>
                        <td>$${(t.price || 0).toLocaleString()}</td>
                        <td>$${(t.notional || 0).toFixed(2)}</td>
                        <td class="${pnlClass}">${pnlStr}</td>
                        <td>$${(t.balance || 0).toFixed(4)}</td>
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

def run_dashboard(host="0.0.0.0", port=5000):
    """Run Flask dashboard in a background thread."""
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)  # suppress Flask request logs
    app.run(host=host, port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    print("Starting ProfitBot Pro Dashboard at http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
