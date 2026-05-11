"""
Wolf Matrix v9 — Orderflow Confirmation
════════════════════════════════════════

АРХИТЕКТУРА ВХОДА:
  Было:  свеча сильная → ждём объём (CONFIRM_VOL_MULT) → ENTER
  Стало: свеча сильная → стакан+velocity держится FLOW_PERSIST_SEC → ENTER

НОВЫЕ ПАРАМЕТРЫ:
  BOOK_DEPTH          — сколько уровней стакана суммируем
  BOOK_IMBALANCE_MIN  — минимальный bid/ask ratio (1.4 = 58% bid)
  TICK_VEL_WINDOW     — окно в секундах для velocity (текущее vs предыдущее)
  TICK_VEL_MIN        — минимальное ускорение (1.2 = +20% к предыдущему окну)
  FLOW_PERSIST_SEC    — сколько секунд сигнал должен ДЕРЖАТЬСЯ перед входом
  FLOW_CHECKS_MIN     — минимум отдельных проверок (антиспуф)

МАТЕМАТИКА ($1 net):
  Нотионал = 100 x 10 = 1000 USDT
  Комиссия = 0.055% x 2 = $1.10
  Trailing floor min = 0.21% → net $1.00
"""

SYMBOLS = ["ETHUSDT", "SOLUSDT", "XRPUSDT", "SUIUSDT"]

KLINE_INTERVAL  = "5"
WARMUP_CANDLES  = 12

WS_URL          = "wss://stream.bybit.com/v5/public/linear"
WS_PING_SEC     = 20
WS_RECONNECT_SEC = 5

EMA_FAST = 5; EMA_MID = 15; EMA_SLOW = 50
RSI_PERIOD = 14; VOLUME_AVG_PERIOD = 20; VWAP_PERIOD = 20
MOMENTUM_LOOKBACK = 5; HIGH_LOW_LOOKBACK = 20
DELTA_VOLUME_MIN_MULT = 1.0
BTC_TREND_WEIGHT = True

# ─── ENTRY (свечные условия — первый фильтр) ─────────────────
DELTA_LONG_MIN   = 0.65;  DELTA_LONG_MAX  = 0.90
DELTA_SHORT_MIN  = -0.90; DELTA_SHORT_MAX = -0.65
VOL_MIN = 1.0;            VOL_MAX = 8.0
DENSITY_LONG_MIN  = 0.70
DENSITY_SHORT_MAX = 0.30
ENTRY_MODE = "ALL"

# ─── ORDERFLOW CONFIRMATION (второй фильтр, тиковый) ─────────
# Book imbalance: bid_vol / ask_vol топ BOOK_DEPTH уровней
# Если LONG: imbalance > BOOK_IMBALANCE_MIN (покупателей больше)
# Если SHORT: imbalance < 1/BOOK_IMBALANCE_MIN (продавцов больше)
BOOK_DEPTH          = 5      # топ-5 уровней стакана
BOOK_IMBALANCE_MIN  = 1.4   # bid/ask >= 1.4 для LONG (58% bid давление)

# Tick velocity: delta за последние TICK_VEL_WINDOW сек vs предыдущие
# Ускорение > TICK_VEL_MIN означает импульс разгоняется, не затухает
TICK_VEL_WINDOW = 5.0        # секунд на одно окно
TICK_VEL_MIN    = 1.2        # текущее окно >= 1.2x предыдущего

# Persistence: сигнал должен держаться FLOW_PERSIST_SEC секунд
# И пройти минимум FLOW_CHECKS_MIN отдельных проверок (антиспуф)
FLOW_PERSIST_SEC = 4.0       # 4 секунды удержания
FLOW_CHECKS_MIN  = 3         # минимум 3 подтверждения за это время

# Таймаут ожидания подтверждения (если за это время не набрали → SKIP)
CONFIRM_TIMEOUT_SEC = 45     # было 60

# ─── STOP LOSS ───────────────────────────────────────────────
STOP_LOSS_PCT = -99.0        # отключён

# ─── COMMISSIONS ─────────────────────────────────────────────
COMMISSION_PCT = 0.055       # per side

# ─── TRADING ─────────────────────────────────────────────────
LEVERAGE = 10
SHADOW_MODE = True
POSITION_SIZE_USDT = 100.0
MAX_SIMULTANEOUS   = 6
MAX_HOLD_CANDLES   = 5
COOLDOWN_CANDLES   = 2

# ─── STALE EXIT ──────────────────────────────────────────────
STALE_CANDLES  = 2
STALE_PEAK_MIN = 0.07

# ─── TRAILING TP (floor min = $1.00 net) ─────────────────────
TRAILING_ACTIVATE_STRONG = 0.25
TRAILING_DISTANCE_STRONG = 0.04
TRAILING_ACTIVATE_WEAK   = 0.25
TRAILING_DISTANCE_WEAK   = 0.04
TRAILING_FLOOR_MIN       = 0.21

# ─── BTC ─────────────────────────────────────────────────────
BTC_VELOCITY_MIN    = 0.10
BTC_VELOCITY_DECAY  = 0.5
BTC_MACRO_CANDLES   = 24
BTC_MACRO_MIN_MOVE  = 0.5
BTC_MACRO_FILTER    = False
BTC_SYMBOL          = "BTCUSDT"

# ─── LOGS ────────────────────────────────────────────────────
CSV_SIGNALS     = "wolf_signals.csv"
CSV_TRADES      = "wolf_trades.csv"
STATE_FILE      = "wolf_state.json"
LOG_TO_CONSOLE  = True
CONSOLE_TOP_N   = 4
