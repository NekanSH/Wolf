"""
Wolf Matrix v4.1 — Data-Proven Filters
═══════════════════════════════════════

121 live trades, +$103.61 — edge confirmed.
Avg win $3.99 (2x avg loss $2.03).

Фильтры из данных (не гадание, а факты):

  vol < 0.3 → -$11 (43% WR) → SKIP
  vol ≥ 5.0 → -$10 (0% WR) → SKIP
  ρ < 0.75 → -$0.22 (29% WR) → SKIP
  ρ 0.75-0.88 → +$87 (57% WR) → BEST

BTC фильтр улучшен:
  EMA5 > EMA15 = тренд вверх (было)
  EMA5 РАСТЁТ = импульс жив (новое)
  EMA5 ПАДАЕТ = импульс умирает → НЕ ВХОДИТЬ

Это отсекает входы на вершине когда BTC начинает
разворачиваться но EMA5 ещё выше EMA15.
"""

SYMBOLS = [
    "ETHUSDT",    # +$9.31
    "SOLUSDT",    # +$22.61
    "XRPUSDT",    # +$47.65 — чемпион
    "SUIUSDT",    # +$24.04
]

KLINE_INTERVAL = "1"
WARMUP_CANDLES = 15

WS_URL = "wss://stream.bybit.com/v5/public/linear"
WS_PING_SEC = 20
WS_RECONNECT_SEC = 5

EMA_FAST = 5; EMA_MID = 15; EMA_SLOW = 50
RSI_PERIOD = 14; VOLUME_AVG_PERIOD = 20; VWAP_PERIOD = 20
MOMENTUM_LOOKBACK = 5; HIGH_LOW_LOOKBACK = 20; DENSITY_HISTORY = 5
DELTA_VOLUME_MIN_MULT = 1.0
BTC_TREND_WEIGHT = True

# ─── ENTRY (v4 base) ──────────────────────────────────────────
DELTA_MIN = 0.50
DELTA_MAX = 0.80

# ─── NEW: vol filter (from 121 trades data) ───────────────────
VOL_MIN = 0.3                 # vol < 0.3 = -$11, 43% WR → skip
VOL_MAX = 5.0                 # vol ≥ 5.0 = -$10, 0% WR → skip

# ─── NEW: density filter ──────────────────────────────────────
DENSITY_MIN = 0.75            # ρ < 0.75 = 29% WR → skip
                               # ρ 0.75-0.88 = 57% WR, +$87

# ─── COMMISSIONS (Bybit taker fee) ────────────────────────────
# Taker: 0.055% per side × 2 sides = 0.11% round trip on price
# With 10x leverage: 0.11% × 10 = 1.1% of margin per trade
COMMISSION_PCT = 0.055          # per side, on notional
# Total round-trip cost on price = COMMISSION_PCT × 2

# ─── TRADING ──────────────────────────────────────────────────
LEVERAGE = 10
SHADOW_MODE = True
POSITION_SIZE_USDT = 100.0
MAX_SIMULTANEOUS = 4
MAX_HOLD_CANDLES = 12
COOLDOWN_CANDLES = 15

# ─── BTC ──────────────────────────────────────────────────────
BTC_SYMBOL = "BTCUSDT"

# ─── NO KILL SWITCH (testing phase) ──────────────────────────
KILL_SWITCH_ENABLED = False

# ─── LOGS ─────────────────────────────────────────────────────
CSV_SIGNALS = "wolf_signals.csv"
CSV_TRADES = "wolf_trades.csv"
STATE_FILE = "wolf_state.json"
LOG_TO_CONSOLE = True
CONSOLE_TOP_N = 4
