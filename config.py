"""
Wolf Matrix v5 — 5-Minute Edition
══════════════════════════════════

ПРОБЛЕМЫ v4.2 (из 112 live сделок):
  - BTC_WEAK exit закрыл 92/112 сделок = ГЛАВНЫЙ УБИЙЦА
  - 1-мин свечи: движения 0.05-0.15%, комиссии 0.11% = edge = 0
  - Нет фиксации прибыли: 52 сделки отдали peak назад

ФИКСЫ v5:
  1. 5-мин свечи: движения 0.3-0.8%, комиссии = 14% от движения (не 70%)
  2. BTC_WEAK exit УБРАН (он убивал систему, не спасал)
  3. Trailing TP: если peak ≥ 0.20%, ставим floor на peak - 0.10%
  4. BTC_DOWN exit оставлен (реальный разворот)
  5. TIMEOUT = 6 свечей (30 мин на 5-мин = ~столько же реального времени)
"""

SYMBOLS = [
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "SUIUSDT",
]

KLINE_INTERVAL = "5"            # 5 MIN (было 1)
WARMUP_CANDLES = 12             # 12 × 5 = 60 мин прогрев

WS_URL = "wss://stream.bybit.com/v5/public/linear"
WS_PING_SEC = 20
WS_RECONNECT_SEC = 5

EMA_FAST = 5; EMA_MID = 15; EMA_SLOW = 50
RSI_PERIOD = 14; VOLUME_AVG_PERIOD = 20; VWAP_PERIOD = 20
MOMENTUM_LOOKBACK = 5; HIGH_LOW_LOOKBACK = 20; DENSITY_HISTORY = 5
DELTA_VOLUME_MIN_MULT = 1.0
BTC_TREND_WEIGHT = True

# ─── ENTRY ────────────────────────────────────────────────────
DELTA_MIN = 0.50
DELTA_MAX = 0.80
VOL_MIN = 0.3
VOL_MAX = 5.0
DENSITY_MIN = 0.75

# ─── COMMISSIONS ──────────────────────────────────────────────
COMMISSION_PCT = 0.055          # per side

# ─── TRADING ──────────────────────────────────────────────────
LEVERAGE = 10
SHADOW_MODE = True
POSITION_SIZE_USDT = 100.0
MAX_SIMULTANEOUS = 4
MAX_HOLD_CANDLES = 6            # 6 × 5min = 30 min
COOLDOWN_CANDLES = 3            # 3 × 5min = 15 min

# ─── TRAILING TP (NEW) ───────────────────────────────────────
# Если peak ≥ 0.20%: ставим floor = peak - 0.10%
# Если цена упала ниже floor → фиксируем прибыль
TRAILING_ACTIVATE = 0.20        # peak % для активации trailing
TRAILING_DISTANCE = 0.10        # сколько отдаём от peak

# ─── BTC ──────────────────────────────────────────────────────
BTC_SYMBOL = "BTCUSDT"

# ─── NO KILL SWITCH ───────────────────────────────────────────
KILL_SWITCH_ENABLED = False

# ─── LOGS ─────────────────────────────────────────────────────
CSV_SIGNALS = "wolf_signals.csv"
CSV_TRADES = "wolf_trades.csv"
STATE_FILE = "wolf_state.json"
LOG_TO_CONSOLE = True
CONSOLE_TOP_N = 4
