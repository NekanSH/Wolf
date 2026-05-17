"""
Wolf Matrix v11 — Full Pattern Engine
══════════════════════════════════════

ПАТТЕРНЫ ИЗ 5220 СВЕЧЕЙ ЩЕНКА (4.5 дня, p=0.00000000):

  1. СЕССИИ (p=0.00000000, 7 файлов подряд):
     SHORT: 9-15 UTC → avg -0.307% за свечу
     LONG:  16-18 UTC → avg +0.174% за свечу

  2. СИМВОЛЫ (по данным щенка):
     SHORT лидер: SUI (92% дают 0.25%+, avg -0.547%)
     LONG лидер:  XRP (+0.097% avg в 16-18 UTC)

  3. КОНСЕНСУС МОНЕТ:
     LONG:  green_count >= 3 из 4 (+0.010% vs -0.067%)
     SHORT: green_count <= 1 из 4

  4. СПРЕД (широкий = движение идёт):
     Широкий спред: 025=64% vs узкий 35%

  5. РАЗМЕР СДЕЛОК (киты двигают):
     Киты: 025=67% vs планктон 43%

  6. TRAILING ПО СИМВОЛУ:
     SUI: быстрый (выстреливает и возвращается)
     XRP: медленный (идёт плавно)

МАТЕМАТИКА ($1 net гарантия):
  Нотионал = 100 × 10 = 1000 USDT
  Комиссия = 0.055% × 2 = $1.10
  Floor min = 0.21% → net $1.00
"""

SYMBOLS    = ["ETHUSDT", "SOLUSDT", "XRPUSDT", "SUIUSDT"]
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

# ─── СВЕЧНЫЕ УСЛОВИЯ ВХОДА ────────────────────────────────────
DELTA_LONG_MIN   = 0.65;  DELTA_LONG_MAX  = 0.90
DELTA_SHORT_MIN  = -0.90; DELTA_SHORT_MAX = -0.65
VOL_MIN = 0.5;            VOL_MAX = 8.0
DENSITY_LONG_MIN  = 0.70
DENSITY_SHORT_MAX = 0.30

# ─── 1. СЕССИОННЫЙ ФИЛЬТР ─────────────────────────────────────
SESSION_SHORT_HOURS = [9, 10, 11, 13, 14, 15]
SESSION_LONG_HOURS  = [16, 17, 18, 0, 1, 8]

# ─── 2. СИМВОЛЬНЫЙ ФИЛЬТР ─────────────────────────────────────
LONG_SYMBOLS  = ["XRPUSDT", "SOLUSDT"]  # XRP лидер, SOL запасной
SHORT_SYMBOLS = ["SUIUSDT", "XRPUSDT"]  # SUI лидер (92%), XRP запасной
WEAK_PAUSE    = True  # BTC=WEAK → не торгуем

# ─── 3. КОНСЕНСУС МОНЕТ ───────────────────────────────────────
# Сколько из 4 монет должны быть зелёными
CONSENSUS_LONG_MIN  = 3   # для лонга: ≥ 3 зелёных
CONSENSUS_SHORT_MAX = 1   # для шорта: ≤ 1 зелёных

# ─── 4. СПРЕД ФИЛЬТР ─────────────────────────────────────────
# Широкий спред = рынок готовится к движению
# Порог: топ 33% спредов (динамически от текущего стакана)
SPREAD_FILTER_ENABLED = True
SPREAD_PERCENTILE     = 50   # входим только если спред выше медианы

# ─── 5. РАЗМЕР СДЕЛОК (КИТ ФИЛЬТР) ───────────────────────────
# Крупные сделки = киты = реальное движение
WHALE_FILTER_ENABLED  = True
WHALE_SIZE_MULT       = 1.3  # средний размер сделки > 1.3x от медианы

# ─── 6. TRAILING ПО СИМВОЛУ ───────────────────────────────────
SUI_TRAILING_ACTIVATE = 0.20   # быстрый — выстреливает и возвращается
SUI_TRAILING_DISTANCE = 0.03
XRP_TRAILING_ACTIVATE = 0.25   # медленный — идёт плавно
XRP_TRAILING_DISTANCE = 0.04
SOL_TRAILING_ACTIVATE = 0.25
SOL_TRAILING_DISTANCE = 0.04
ETH_TRAILING_ACTIVATE = 0.25
ETH_TRAILING_DISTANCE = 0.04

# ─── СТАНДАРТНЫЙ TRAILING (fallback) ─────────────────────────
TRAILING_ACTIVATE_STRONG = 0.25
TRAILING_DISTANCE_STRONG = 0.04
TRAILING_ACTIVATE_WEAK   = 0.25
TRAILING_DISTANCE_WEAK   = 0.04
TRAILING_FLOOR_MIN       = 0.21   # floor → $1.00 net минимум

# ─── STOP LOSS ────────────────────────────────────────────────
STOP_LOSS_PCT = -99.0   # отключён

# ─── COMMISSIONS ─────────────────────────────────────────────
COMMISSION_PCT = 0.055  # per side

# ─── TRADING ─────────────────────────────────────────────────
LEVERAGE           = 10
SHADOW_MODE        = True
POSITION_SIZE_USDT = 100.0
MAX_SIMULTANEOUS   = 4
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
CSV_SIGNALS    = "wolf_signals.csv"
CSV_TRADES     = "wolf_trades.csv"
STATE_FILE     = "wolf_state.json"
LOG_TO_CONSOLE = True
CONSOLE_TOP_N  = 4
