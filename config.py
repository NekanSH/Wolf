"""
Wolf Matrix v10 — Session + Symbol Filter
══════════════════════════════════════════

НОВОЕ В v10 (на основе 4300+ свечей щенка):

  ФИЛЬТР 1 — BTC РЕЖИМ определяет направление:
    BTC=UP   → только LONG,  символы: XRP + SOL
    BTC=DOWN → только SHORT, символы: SUI + XRP
    BTC=WEAK → не торгуем вообще

  ФИЛЬТР 2 — ТОРГОВЫЕ СЕССИИ (p=0.0000, 5 файлов подряд):
    BTC=DOWN + SHORT → лучшие часы 9-15 UTC (Лондон + NY открытие)
    BTC=UP   + LONG  → лучшие часы 0,1,8,16,17,18 UTC (Азия + NY середина)

  ФИЛЬТР 3 — TRAILING ПО СИМВОЛУ:
    SUI → быстрый выход (activate=0.20, distance=0.03) — выстреливает и возвращается
    XRP → медленный выход (activate=0.25, distance=0.04) — идёт плавно
    SOL → стандартный

МАТЕМАТИКА ($1 net):
  Нотионал = 100 × 10 = 1000 USDT
  Комиссия = 0.055% × 2 = $1.10
  Floor min = 0.21% → net $1.00
"""

SYMBOLS = ["ETHUSDT", "SOLUSDT", "XRPUSDT", "SUIUSDT"]
BTC_SYMBOL = "BTCUSDT"

KLINE_INTERVAL   = "5"
WARMUP_CANDLES   = 12

WS_URL           = "wss://stream.bybit.com/v5/public/linear"
WS_PING_SEC      = 20
WS_RECONNECT_SEC = 5

EMA_FAST = 5; EMA_MID = 15; EMA_SLOW = 50
RSI_PERIOD = 14; VOLUME_AVG_PERIOD = 20; VWAP_PERIOD = 20
MOMENTUM_LOOKBACK = 5; HIGH_LOW_LOOKBACK = 20
DELTA_VOLUME_MIN_MULT = 1.0
BTC_TREND_WEIGHT = True

# ─── ENTRY (свечные условия) ──────────────────────────────────
DELTA_LONG_MIN   = 0.65;  DELTA_LONG_MAX  = 0.90
DELTA_SHORT_MIN  = -0.90; DELTA_SHORT_MAX = -0.65
VOL_MIN = 0.5;            VOL_MAX = 8.0
DENSITY_LONG_MIN  = 0.70
DENSITY_SHORT_MAX = 0.30

# ─── СЕССИОННЫЙ ФИЛЬТР (из данных щенка) ─────────────────────
# BTC=DOWN + SHORT: лучшие часы UTC
SESSION_SHORT_HOURS = [9, 10, 11, 13, 14, 15]

# BTC=UP + LONG: лучшие часы UTC
SESSION_LONG_HOURS  = [0, 1, 8, 16, 17, 18]

# ─── СИМВОЛЬНЫЙ ФИЛЬТР (из данных щенка) ─────────────────────
# BTC=UP → лонг только этими символами
LONG_SYMBOLS  = ["XRPUSDT", "SOLUSDT"]

# BTC=DOWN → шорт только этими символами
SHORT_SYMBOLS = ["SUIUSDT", "XRPUSDT"]

# BTC=WEAK → не торгуем (пауза)
WEAK_PAUSE = True

# ─── TRAILING ПО СИМВОЛУ ─────────────────────────────────────
# SUI — быстрый: выстреливает и сразу возвращается
SUI_TRAILING_ACTIVATE = 0.20   # ниже порога чтобы успеть поймать
SUI_TRAILING_DISTANCE = 0.03   # быстро фиксируем

# XRP — медленный: идёт плавно
XRP_TRAILING_ACTIVATE = 0.25
XRP_TRAILING_DISTANCE = 0.04

# SOL — стандартный
SOL_TRAILING_ACTIVATE = 0.25
SOL_TRAILING_DISTANCE = 0.04

# ETH — стандартный (для шорта если вдруг)
ETH_TRAILING_ACTIVATE = 0.25
ETH_TRAILING_DISTANCE = 0.04

# ─── СТАНДАРТНЫЙ TRAILING (fallback) ─────────────────────────
TRAILING_ACTIVATE_STRONG = 0.25
TRAILING_DISTANCE_STRONG = 0.04
TRAILING_ACTIVATE_WEAK   = 0.25
TRAILING_DISTANCE_WEAK   = 0.04
TRAILING_FLOOR_MIN       = 0.21    # floor никогда ниже → $1.00 net

# ─── STOP LOSS ────────────────────────────────────────────────
STOP_LOSS_PCT = -99.0

# ─── COMMISSIONS ─────────────────────────────────────────────
COMMISSION_PCT = 0.055

# ─── TRADING ─────────────────────────────────────────────────
LEVERAGE           = 10
SHADOW_MODE        = True
POSITION_SIZE_USDT = 100.0
MAX_SIMULTANEOUS   = 4     # было 6 — меньше символов = меньше одновременных
MAX_HOLD_CANDLES   = 5
COOLDOWN_CANDLES   = 2

# ─── STALE ───────────────────────────────────────────────────
STALE_CANDLES  = 2
STALE_PEAK_MIN = 0.07

# ─── ORDERFLOW ───────────────────────────────────────────────
BOOK_DEPTH          = 5
BOOK_IMBALANCE_MIN  = 1.2
TICK_VEL_WINDOW     = 5.0
TICK_VEL_MIN        = 1.0
FLOW_PERSIST_SEC    = 2.0
FLOW_CHECKS_MIN     = 2
CONFIRM_TIMEOUT_SEC = 45

# ─── BTC ─────────────────────────────────────────────────────
BTC_VELOCITY_MIN    = 0.10
BTC_VELOCITY_DECAY  = 0.5
BTC_MACRO_CANDLES   = 24
BTC_MACRO_MIN_MOVE  = 0.5
BTC_MACRO_FILTER    = False

# ─── LOGS ────────────────────────────────────────────────────
CSV_SIGNALS     = "wolf_signals.csv"
CSV_TRADES      = "wolf_trades.csv"
STATE_FILE      = "wolf_state.json"
LOG_TO_CONSOLE  = True
CONSOLE_TOP_N   = 4
