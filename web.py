"""
Wolf Matrix — Web Dashboard Server
Лёгкий HTTP сервер: отдаёт dashboard.html + /api/state с JSON.
Запускается в отдельном потоке, не блокирует бота.
"""
from __future__ import annotations

import json
import os
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine import WolfEngine

import config as cfg

_engine_ref: WolfEngine | None = None


class DashboardHandler(SimpleHTTPRequestHandler):
    """Обрабатывает /api/state и статику."""

    def __init__(self, *args, directory=None, **kwargs):
        # Serve from the bot's directory
        d = directory or os.path.dirname(os.path.abspath(__file__))
        super().__init__(*args, directory=d, **kwargs)

    def do_GET(self):
        if self.path.startswith('/api/state'):
            self._send_state()
        elif self.path == '/' or self.path == '/index.html':
            self.path = '/dashboard.html'
            super().do_GET()
        else:
            super().do_GET()

    def _send_state(self):
        eng = _engine_ref
        if eng is None:
            self.send_response(503)
            self.end_headers()
            return

        stats = eng.stats()

        # Equity curve
        equity = []
        cum = 0.0
        for t in eng.closed:
            cum += t.pnl_usdt
            equity.append(round(cum, 2))

        # Closed trades
        closed = []
        for t in eng.closed:
            closed.append({
                "symbol": t.symbol,
                "side": t.side,
                "entry": t.entry_price,
                "exit": t.exit_price,
                "pnl_pct": round(t.pnl_pct, 4),
                "pnl": round(t.pnl_usdt, 2),
                "delta": round(t.entry_delta, 4),
                "hold": getattr(t, 'hold_limit', cfg.MAX_HOLD_CANDLES),
            })

        # Open positions
        open_pos = []
        for p in eng.open:
            current = eng.states[p.symbol].last_price if p.symbol in eng.states else p.entry_price
            sym_candle = eng.states[p.symbol].candle_count if p.symbol in eng.states else 0
            open_pos.append({
                "symbol": p.symbol,
                "side": p.side,
                "entry": p.entry_price,
                "current": current,
                "hold": sym_candle - p.entry_candle,
            })

        # Matrix snapshot
        matrix = eng.snapshot()

        # Symbol PnL
        sym_pnl: dict[str, float] = defaultdict(float)
        for t in eng.closed:
            sym_pnl[t.symbol] += t.pnl_usdt
        sym_pnl = {k: round(v, 2) for k, v in sym_pnl.items()}

        payload = {
            "stats": stats,
            "btc": eng.btc_up,
            "signals": eng.signals,
            "equity": equity,
            "closed": closed,
            "open_pos": open_pos,
            "matrix": matrix,
            "sym_pnl": sym_pnl,
            "tick": eng.tick,
        }

        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # тихий сервер


def start_dashboard(engine: 'WolfEngine', port: int = 8888):
    """Запускает дашборд в фоновом потоке. Возвращает thread."""
    global _engine_ref
    _engine_ref = engine

    server = HTTPServer(('0.0.0.0', port), DashboardHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"  \033[36m◉ Dashboard: http://localhost:{port}\033[0m")
    return thread
