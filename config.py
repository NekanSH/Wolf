"""
Wolf Matrix v13 — Simple Session Engine
════════════════════════════════════════
Оптимизированная конфигурация сессионного робота.
"""

SYMBOLS    = ["ETHUSDT", "SOLUSDT", "XRPUSDT", "SUIUSDT"]
BTC_SYMBOL = "BTCUSDT"

KLINE_INTERVAL   = "5"
WARMUP_CANDLES   = 12

WS_URL           = "wss://stream.bybit.com/v5/public/linear"
WS_PING_SEC      = 20
WS_RECONNECT_SEC = 5

EMA_FAST = 5
EMA_MID  = 15
VOLUME_AVG_PERIOD = 20

# ─── ВХОД (ОПТИМИЗИРОВАННЫЙ ИМПУЛЬС) ─────────────────────────
VOL_MIN = 1.2    # Вход только при объеме на 20% выше среднего
VOL_MAX = 7.0    # Фильтрация нерыночных ценовых аномалий

# ─── СЕССИОННЫЙ ФИЛЬТР ───────────────────────────────────────
SESSION_SHORT_HOURS = [9, 10, 11, 13, 14, 15]
SESSION_LONG_HOURS  = [16, 17, 18, 0, 1, 8]

# ─── СИМВОЛЬНЫЙ ФИЛЬТР ───────────────────────────────────────
LONG_SYMBOLS  = ["XRPUSDT", "SOLUSDT"]
SHORT_SYMBOLS = ["SUIUSDT", "XRPUSDT"]
WEAK_PAUSE    = True  # BTC=WEAK → пауза

# ─── TRAILING ПО СИМВОЛУ ─────────────────────────────────────
SUI_TRAILING_ACTIVATE = 0.20
SUI_TRAILING_DISTANCE = 0.03
XRP_TRAILING_ACTIVATE = 0.25
XRP_TRAILING_DISTANCE = 0.04
SOL_TRAILING_ACTIVATE = 0.25
SOL_TRAILING_DISTANCE = 0.04
ETH_TRAILING_ACTIVATE = 0.25
ETH_TRAILING_DISTANCE = 0.04
TRAILING_FLOOR_MIN    = 0.21  # Чистый профит минимум ~$1.00 с учетом комиссий

# ─── STOP LOSS (ЗАЩИТА АКТИВИРОВАНА) ─────────────────────────
STOP_LOSS_PCT = -0.45  # Жесткий системный стоп-лосс на свечу

# ─── COMMISSIONS ─────────────────────────────────────────────
COMMISSION_PCT = 0.055  # Сборы Bybit Futures (Market)

# ─── TRADING ─────────────────────────────────────────────────
LEVERAGE           = 10
SHADOW_MODE        = True
POSITION_SIZE_USDT = 100.0
MAX_SIMULTANEOUS   = 2   
MAX_HOLD_CANDLES   = 5
COOLDOWN_CANDLES   = 3   

# ─── STALE ───────────────────────────────────────────────────
STALE_CANDLES  = 2
STALE_PEAK_MIN = 0.07

# ─── BTC ТРЕНД ───────────────────────────────────────────────
BTC_VELOCITY_MIN    = 0.10
BTC_VELOCITY_DECAY  = 0.5

# ─── LOGS ────────────────────────────────────────────────────
CSV_SIGNALS    = "wolf_signals.csv"
CSV_TRADES     = "wolf_trades.csv"
STATE_FILE     = "wolf_state.json"
LOG_TO_CONSOLE = True
CONSOLE_TOP_N  = 4
