"""
Wolf Matrix v6 — Research Mode (LONG+SHORT, 5-min)
═══════════════════════════════════════════════════

ДАННЫЕ: 189 live сделок
  - Stop Loss -0.20%: 53t, WR:0%, -$217 = ВСЯ ПОТЕРЯ
  - Без SL: -$0.66 (ноль!)
  - TRAILING_TP: 24t, 54% WR, +$47 → работает
  - TIMEOUT: 67t, 40% WR, +$26 → работает

ВЫВОД: SL на 5-мин = убиваем себя на шуме. Убран.
ВЫВОД: BTC_REVERSAL: 45t, 18% WR, -$73 → тоже убран.
Оставить только TRAILING_TP + TIMEOUT.
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

# ─── ENTRY (RESEARCH MODE - широкие фильтры для сбора данных) ──
DELTA_LONG_MIN = 0.40           # было 0.50 — собираем больше данных
DELTA_LONG_MAX = 0.90           # было 0.70
DELTA_SHORT_MIN = -0.90         # SHORT зеркально
DELTA_SHORT_MAX = -0.40
VOL_MIN = 0.2                   # было 0.3
VOL_MAX = 8.0                   # было 2.0
DENSITY_LONG_MIN = 0.60         # было 0.75 — мягче
DENSITY_SHORT_MAX = 0.40        # SHORT зеркально

# Entry mode: ALL | LONG_ONLY | SHORT_ONLY
ENTRY_MODE = "ALL"              # собираем данные во всех режимах

# ─── STOP LOSS ─────────────────────────────────────────────────
# ОТКЛЮЧЁН: данные 189 сделок → SL -0.20% = 53t, -$217 (весь убыток)
# 5-мин шум легко -0.20%, потом цена возвращается. SL = убиваем себя.
# Без SL система = -$0.66. Выходим только TRAILING + TIMEOUT.
STOP_LOSS_PCT = -99.0           # отключено

# ─── COMMISSIONS ──────────────────────────────────────────────
COMMISSION_PCT = 0.055          # per side

# ─── TRADING ──────────────────────────────────────────────────
LEVERAGE = 10
SHADOW_MODE = True
POSITION_SIZE_USDT = 100.0
MAX_SIMULTANEOUS = 6            # было 4 — больше одновременных для данных
MAX_HOLD_CANDLES = 6
COOLDOWN_CANDLES = 2            # было 3 — меньше ждём между сделками

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
