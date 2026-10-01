"""
Dashboard generator: produces a static HTML dashboard from today's scan data.
Designed to be deployed to GitHub Pages or opened locally.
"""
import json
import datetime
import logging
import os
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


def generate_dashboard(bulk_data: dict, watchlist: list, state: dict, output_path: str = "docs/index.html"):
    """
    Generate a static HTML dashboard from the latest scan results.

    Args:
        bulk_data: dict of ticker -> quote data from the bulk scan
        watchlist: list of watchlist items
        state: current state dict (alerts sent today, history)
        output_path: where to write the HTML file
    """
    now_ist = datetime.datetime.now(ZoneInfo("Asia/Kolkata"))
    timestamp = now_ist.strftime("%d %b %Y, %I:%M %p IST")
    date_str = now_ist.strftime("%Y-%m-%d")

    # Build sorted lists
    movers = []
    for ticker, data in bulk_data.items():
        price = data.get("price", 0)
        prev = data.get("prev_close", 0)
        vol = data.get("volume", 0)
        avg_vol = data.get("avg_volume", 0)
        if prev and prev != 0:
            pct = ((price - prev) / prev) * 100
        else:
            pct = 0
        vol_ratio = (vol / avg_vol) if avg_vol and avg_vol > 0 else 0
        movers.append({
            "ticker": ticker,
            "price": round(price, 2),
            "prev_close": round(prev, 2),
            "pct_change": round(pct, 2),
            "volume": int(vol) if vol else 0,
            "avg_volume": int(avg_vol) if avg_vol else 0,
            "vol_ratio": round(vol_ratio, 2),
        })

    top_gainers = sorted(movers, key=lambda x: x["pct_change"], reverse=True)[:20]
    top_losers = sorted(movers, key=lambda x: x["pct_change"])[:20]
    high_volume = sorted(movers, key=lambda x: x["vol_ratio"], reverse=True)[:20]

    alerts_today = state.get("alerts_sent_today", 0)
    alert_history = state.get("history", {})
    triggered_tickers = [t for t, rules in alert_history.items() if rules]

    # Generate the HTML
    html = _build_html(
        timestamp=timestamp,
        total_stocks=len(movers),
        alerts_today=alerts_today,
        triggered_tickers=triggered_tickers,
        top_gainers=top_gainers,
        top_losers=top_losers,
        high_volume=high_volume,
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)
    logger.info(f"Dashboard written to {output_path}")


def _build_html(timestamp, total_stocks, alerts_today, triggered_tickers,
                top_gainers, top_losers, high_volume) -> str:
    def _stock_rows(items, show_vol=False):
        rows = ""
        for item in items:
            pct = item["pct_change"]
            color = "#00e676" if pct >= 0 else "#ff5252"
            arrow = "▲" if pct >= 0 else "▼"
            vol_cell = ""
            if show_vol:
                vol_cell = f'<td>{item["volume"]:,}</td><td>{item["vol_ratio"]:.1f}x</td>'
            rows += f"""<tr>
                <td class="ticker">{item["ticker"]}</td>
                <td>₹{item["price"]:,.2f}</td>
                <td style="color:{color}">{arrow} {pct:+.2f}%</td>
                {vol_cell}
            </tr>"""
        return rows

    triggered_badges = "".join(
        f'<span class="badge">{t}</span>' for t in triggered_tickers[:30]
    ) or '<span class="badge neutral">None today</span>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NSE Stock Screener Dashboard</title>
    <meta name="description" content="Real-time NSE Nifty 500 stock screener dashboard with top gainers, losers, and volume breakouts.">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #0a0e17;
            --bg-card: rgba(15, 23, 42, 0.8);
            --bg-card-hover: rgba(30, 41, 59, 0.9);
            --border: rgba(99, 102, 241, 0.2);
            --border-glow: rgba(99, 102, 241, 0.4);
            --text-primary: #e2e8f0;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-green: #00e676;
            --accent-red: #ff5252;
            --accent-blue: #6366f1;
            --accent-purple: #a855f7;
            --accent-amber: #f59e0b;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', -apple-system, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            background-image:
                radial-gradient(ellipse at 20% 50%, rgba(99, 102, 241, 0.08) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 20%, rgba(168, 85, 247, 0.06) 0%, transparent 50%);
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 1.5rem;
        }}
        header {{
            text-align: center;
            padding: 2rem 0 1rem;
        }}
        header h1 {{
            font-size: 2rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        header p {{
            color: var(--text-muted);
            margin-top: 0.5rem;
            font-size: 0.9rem;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin: 1.5rem 0;
        }}
        .stat-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.25rem;
            backdrop-filter: blur(12px);
            transition: border-color 0.3s, transform 0.2s;
        }}
        .stat-card:hover {{
            border-color: var(--border-glow);
            transform: translateY(-2px);
        }}
        .stat-card .label {{
            font-size: 0.8rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .stat-card .value {{
            font-size: 1.8rem;
            font-weight: 700;
            margin-top: 0.25rem;
        }}
        .stat-card .value.green {{ color: var(--accent-green); }}
        .stat-card .value.red {{ color: var(--accent-red); }}
        .stat-card .value.blue {{ color: var(--accent-blue); }}
        .stat-card .value.amber {{ color: var(--accent-amber); }}

        .tables-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
            gap: 1.5rem;
            margin-top: 1.5rem;
        }}
        .table-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.25rem;
            backdrop-filter: blur(12px);
            overflow: hidden;
        }}
        .table-card h2 {{
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th {{
            text-align: left;
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            padding: 0.5rem 0.75rem;
            border-bottom: 1px solid var(--border);
        }}
        td {{
            padding: 0.6rem 0.75rem;
            font-size: 0.85rem;
            border-bottom: 1px solid rgba(51, 65, 85, 0.3);
        }}
        tr:hover {{
            background: var(--bg-card-hover);
        }}
        .ticker {{
            font-weight: 600;
            color: var(--accent-blue);
        }}
        .alerts-section {{
            margin-top: 1.5rem;
        }}
        .alerts-section h2 {{
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 0.75rem;
        }}
        .badge {{
            display: inline-block;
            background: rgba(99, 102, 241, 0.15);
            color: var(--accent-blue);
            border: 1px solid rgba(99, 102, 241, 0.3);
            border-radius: 6px;
            padding: 0.25rem 0.6rem;
            font-size: 0.8rem;
            font-weight: 500;
            margin: 0.2rem;
        }}
        .badge.neutral {{
            background: rgba(100, 116, 139, 0.15);
            color: var(--text-muted);
            border-color: rgba(100, 116, 139, 0.3);
        }}
        footer {{
            text-align: center;
            padding: 2rem 0 1rem;
            color: var(--text-muted);
            font-size: 0.8rem;
        }}
        @media (max-width: 768px) {{
            .container {{ padding: 1rem; }}
            header h1 {{ font-size: 1.5rem; }}
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .tables-grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 NSE Stock Screener</h1>
            <p>Last updated: {timestamp}</p>
        </header>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">Stocks Scanned</div>
                <div class="value blue">{total_stocks}</div>
            </div>
            <div class="stat-card">
                <div class="label">Alerts Today</div>
                <div class="value amber">{alerts_today}</div>
            </div>
            <div class="stat-card">
                <div class="label">Top Gainer</div>
                <div class="value green">{top_gainers[0]["ticker"] if top_gainers else "—"}<br><small>{top_gainers[0]["pct_change"]:+.2f}%</small></div>
            </div>
            <div class="stat-card">
                <div class="label">Top Loser</div>
                <div class="value red">{top_losers[0]["ticker"] if top_losers else "—"}<br><small>{top_losers[0]["pct_change"]:+.2f}%</small></div>
            </div>
        </div>

        <div class="alerts-section">
            <h2>🔔 Alerts Triggered Today</h2>
            {triggered_badges}
        </div>

        <div class="tables-grid">
            <div class="table-card">
                <h2>🟢 Top Gainers</h2>
                <table>
                    <thead><tr><th>Ticker</th><th>Price</th><th>Change</th></tr></thead>
                    <tbody>{_stock_rows(top_gainers)}</tbody>
                </table>
            </div>
            <div class="table-card">
                <h2>🔴 Top Losers</h2>
                <table>
                    <thead><tr><th>Ticker</th><th>Price</th><th>Change</th></tr></thead>
                    <tbody>{_stock_rows(top_losers)}</tbody>
                </table>
            </div>
            <div class="table-card">
                <h2>🔥 High Volume (vs Avg)</h2>
                <table>
                    <thead><tr><th>Ticker</th><th>Price</th><th>Change</th><th>Volume</th><th>Ratio</th></tr></thead>
                    <tbody>{_stock_rows(high_volume, show_vol=True)}</tbody>
                </table>
            </div>
        </div>

        <footer>
            <p>NSE Stock Screener &bull; Data from yfinance &bull; Not financial advice</p>
        </footer>
    </div>
</body>
</html>"""
