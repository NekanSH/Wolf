"""
Wolf Matrix v14 — Session + Quality Filter
═══════════════════════════════════════════

ИЗМЕНЕНИЯ v14 (на основе 11256 свечей щенка):

  1. BODY_RATIO_MIN = 0.30
     Свеча должна иметь реальное тело.
     Хвосты без тела = STALE. Убирает ~30% мёртвых входов.

  2. Цвет свечи совпадает со стороной:
     SHORT → только красная свеча
     LONG  → только зелёная свеча

  3. SHORT_SYMBOLS добавлен SOL
     SOL: 74% reached_025, dn=0.339% — лучше XRP в шорт

  4. VOL_MIN = 1.0 (было 0.5)
     Только свечи с объёмом выше среднего

МАТЕМАТИКА ($1 net):
  Нотионал = 100 × 10 = 1000 USDT
  Комиссия = 0.055% × 2 = $1.10
  Floor min = 0.21% → net $1.00
"""

SYMBOLS    = ["ETHUSDT", "SOLUSDT", "XRPUSDT", "SUIUSDT"]
BTC_SYMBOL = "BTCUSDT"
BOOK_DEPTH = 5

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

# ─── ВХОД ────────────────────────────────────────────────────
VOL_MIN  = 1.0    # объём выше среднего
VOL_MAX  = 10.0

BODY_RATIO_MIN = 0.30  # тело свечи ≥ 30% диапазона

# ─── СЕССИОННЫЙ ФИЛЬТР ───────────────────────────────────────
SESSION_SHORT_HOURS = [13, 14, 15]
SESSION_LONG_HOURS  = [16, 17]

# ─── СИМВОЛЬНЫЙ ФИЛЬТР ───────────────────────────────────────
LONG_SYMBOLS  = ["XRPUSDT", "SOLUSDT"]
SHORT_SYMBOLS = ["SUIUSDT", "SOLUSDT", "XRPUSDT"]  # SOL добавлен
WEAK_PAUSE    = True

# ─── TRAILING ПО СИМВОЛУ ─────────────────────────────────────
SUI_TRAILING_ACTIVATE = 0.20
SUI_TRAILING_DISTANCE = 0.03
XRP_TRAILING_ACTIVATE = 0.25
XRP_TRAILING_DISTANCE = 0.04
SOL_TRAILING_ACTIVATE = 0.25
SOL_TRAILING_DISTANCE = 0.04
ETH_TRAILING_ACTIVATE = 0.25
ETH_TRAILING_DISTANCE = 0.04
TRAILING_FLOOR_MIN    = 0.21

# ─── STOP LOSS ────────────────────────────────────────────────
STOP_LOSS_PCT = -99.0

# ─── COMMISSIONS ─────────────────────────────────────────────
COMMISSION_PCT = 0.055

# ─── TRADING ─────────────────────────────────────────────────
LEVERAGE           = 10
SHADOW_MODE        = True
POSITION_SIZE_USDT = 100.0
MAX_SIMULTANEOUS   = 3
MAX_HOLD_CANDLES   = 5
COOLDOWN_CANDLES   = 3

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
