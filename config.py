"""
Wolf Matrix v13 — Simple Session Engine
════════════════════════════════════════

АРХИТЕКТУРА УПРОЩЕНА (18.05.2026):

  БЫЛО: delta + density + orderflow + консенсус + час + символ
  СТАЛО: час + BTC + символ + vol_ratio

  ПОЧЕМУ: delta/density пропускали только трупы движений.
  Щенок доказал (7044 свечи): в правильный час движение
  происходит в 68-92% случаев БЕЗ фильтра delta/density.

  ВХОД: первая свеча с vol_ratio>0.5 в правильном окне.
  ВЫХОД: trailing по символу (SUI быстрый, XRP медленный).

СТАТИСТИКА (7044 свечи, 6.1 дней):
  Шорт (DOWN+час+SUI/XRP): 68% reached_025, dn=0.375%
  Лонг (UP+час+XRP/SOL):   43% reached_025, up=0.188%
  Ожидаемых сделок: ~5-8 в день
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

# ─── ВХОД (упрощённый) ───────────────────────────────────────
# Убраны: DELTA, DENSITY, ORDERFLOW, CONSENSUS
# Оставлено: ЧАС + BTC + СИМВОЛ + ОБЪЁМ

VOL_MIN = 0.5    # минимальный объём (не мёртвая свеча)
VOL_MAX = 10.0   # защита от аномальных всплесков

# ─── СЕССИОННЫЙ ФИЛЬТР ───────────────────────────────────────
SESSION_SHORT_HOURS = [13, 14, 15]
SESSION_LONG_HOURS  = [16, 17]

# ─── СИМВОЛЬНЫЙ ФИЛЬТР ───────────────────────────────────────
LONG_SYMBOLS  = ["XRPUSDT", "SOLUSDT"]
SHORT_SYMBOLS = ["SUIUSDT", "XRPUSDT"]
WEAK_PAUSE    = True  # BTC=WEAK → не торгуем


# ─── ДЛЯ INDICATORS.PY (OrderBook + TickVelocity) ────────────
BOOK_DEPTH      = 5
TICK_VEL_WINDOW = 5.0
DENSITY_HISTORY = 5

# ─── TRAILING ПО СИМВОЛУ ─────────────────────────────────────
SUI_TRAILING_ACTIVATE = 0.20
SUI_TRAILING_DISTANCE = 0.03
XRP_TRAILING_ACTIVATE = 0.25
XRP_TRAILING_DISTANCE = 0.04
SOL_TRAILING_ACTIVATE = 0.25
SOL_TRAILING_DISTANCE = 0.04
ETH_TRAILING_ACTIVATE = 0.25
ETH_TRAILING_DISTANCE = 0.04
TRAILING_FLOOR_MIN    = 0.21  # floor → $1.00 net минимум

# ─── STOP LOSS ────────────────────────────────────────────────
STOP_LOSS_PCT = -99.0  # отключён

# ─── COMMISSIONS ─────────────────────────────────────────────
COMMISSION_PCT = 0.055  # per side

# ─── TRADING ─────────────────────────────────────────────────
LEVERAGE           = 10
SHADOW_MODE        = True
POSITION_SIZE_USDT = 100.0
MAX_SIMULTANEOUS   = 2   # максимум 2 одновременных (SUI+XRP)
MAX_HOLD_CANDLES   = 5
COOLDOWN_CANDLES   = 3   # пауза между сделками по символу

# ─── STALE ───────────────────────────────────────────────────
STALE_CANDLES  = 2
STALE_PEAK_MIN = 0.07

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
