"""
Wolf Matrix v8 — Anti-STALE Confirmation Engine
════════════════════════════════════════════════

ИСПРАВЛЕННЫЕ БАГИ (2026-05-10):

  БАГ #1 [КРИТИЧЕСКИЙ] — Trailing TP давал УБЫТОК:
    БЫЛО: STRONG floor = 0.18 - 0.09 = 0.09% → gross $0.90 → net -$0.20
    БЫЛО: WEAK  floor = 0.12 - 0.05 = 0.07% → gross $0.70 → net -$0.40
    СТАЛО: оба floor = 0.21% → gross $2.10 → net $1.00 ✓

  БАГ #2 [КРИТИЧЕСКИЙ] — max_pnl считался по CLOSE, не по HIGH/LOW:
    Цена ходила вверх ВНУТРИ свечи → trailing не активировался →
    позиция держалась до STALE/TIMEOUT с убытком.
    ИСПРАВЛЕНО в engine.py: используем c.h (LONG) / c.l (SHORT).

  БАГ #3 — CONFIRM_VOL_MULT = 0.05 — почти нет фильтра:
    0.5 единиц объёма подтверждало вход. Поднято до 0.15.

МАТЕМАТИКА (не меняй без пересчёта):
  Нотионал  = 100 USDT x 10x = 1000 USDT
  Комиссия  = 0.055% x 2 x 1000 = $1.10 за сделку
  $1 net -> нужно $2.10 gross -> нужно 0.21% движение цены
  Trailing floor min = 0.21%
"""

SYMBOLS = [
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "SUIUSDT",
]

KLINE_INTERVAL = "5"            # 5 MIN
WARMUP_CANDLES = 12             # 12 x 5 = 60 min prewarm

WS_URL = "wss://stream.bybit.com/v5/public/linear"
WS_PING_SEC = 20
WS_RECONNECT_SEC = 5

EMA_FAST = 5; EMA_MID = 15; EMA_SLOW = 50
RSI_PERIOD = 14; VOLUME_AVG_PERIOD = 20; VWAP_PERIOD = 20
MOMENTUM_LOOKBACK = 5; HIGH_LOW_LOOKBACK = 20; DENSITY_HISTORY = 5
DELTA_VOLUME_MIN_MULT = 1.0
BTC_TREND_WEIGHT = True

# --- ENTRY ---------------------------------------------------
DELTA_LONG_MIN = 0.65
DELTA_LONG_MAX = 0.90
DELTA_SHORT_MIN = -0.90
DELTA_SHORT_MAX = -0.65
VOL_MIN = 1.0
VOL_MAX = 8.0
DENSITY_LONG_MIN = 0.70
DENSITY_SHORT_MAX = 0.30

ENTRY_MODE = "ALL"  # ALL | LONG_ONLY | SHORT_ONLY

# --- STOP LOSS -----------------------------------------------
STOP_LOSS_PCT = -99.0           # disabled

# --- COMMISSIONS ---------------------------------------------
COMMISSION_PCT = 0.055          # per side (x2 = 0.11% round-trip)

# --- TRADING -------------------------------------------------
LEVERAGE = 10
SHADOW_MODE = True
POSITION_SIZE_USDT = 100.0
MAX_SIMULTANEOUS = 6
MAX_HOLD_CANDLES = 5
COOLDOWN_CANDLES = 2

# --- STALE EXIT ----------------------------------------------
# Dead trade control: if HIGH never reached STALE_PEAK_MIN in STALE_CANDLES
# -> exit immediately. Limits loss to commission only (damage control).
# NOTE: 0.07% < 0.21% breakeven is intentional - we exit with ONLY commission
# instead of holding and potentially losing more.
STALE_CANDLES  = 2              # 10 min no movement = dead
STALE_PEAK_MIN = 0.07           # if H/L never moved 0.07% -> STALE

# --- TRAILING TP (FIXED: guaranteed $1 net profit) -----------
#
# OLD (BUGS):
#   STRONG: activate=0.18, distance=0.09 -> floor=0.09% -> net -$0.20  BUG!
#   WEAK:   activate=0.12, distance=0.05 -> floor=0.07% -> net -$0.40  BUG!
#
# NEW ($1 net guarantee):
#   Commission = $1.10 per trade
#   $1 net requires $2.10 gross = 0.21% price move
#   STRONG: activate=0.25%, distance=0.04% -> floor=0.21% -> net=$1.00
#   WEAK:   activate=0.25%, distance=0.04% -> floor=0.21% -> net=$1.00
#
# TRAILING_FLOOR_MIN: hard floor - engine raises floor to this if math goes below it.
#
TRAILING_ACTIVATE_STRONG = 0.25    # was 0.18 (floor was 0.09% = LOSS)
TRAILING_DISTANCE_STRONG = 0.04    # was 0.09
                                    # floor = 0.25 - 0.04 = 0.21% -> $1.00 net

TRAILING_ACTIVATE_WEAK   = 0.25    # was 0.12 (floor was 0.07% = LOSS)
TRAILING_DISTANCE_WEAK   = 0.04    # was 0.05
                                    # floor = 0.25 - 0.04 = 0.21% -> $1.00 net

TRAILING_FLOOR_MIN       = 0.21    # NEW: hard minimum floor = $1.00 net minimum

# --- BTC -----------------------------------------------------
BTC_VELOCITY_MIN   = 0.10
BTC_VELOCITY_DECAY = 0.5

BTC_MACRO_CANDLES  = 24
BTC_MACRO_MIN_MOVE = 0.5
BTC_MACRO_FILTER   = False

BTC_SYMBOL = "BTCUSDT"

# --- ANTI-STALE CONFIRMATION ---------------------------------
# BUG #3 FIXED: was 0.05 = 0.5 units = anything confirms entry (no filter).
# Raised to 0.15 = 15% of baseline volume required (moderate filter).
CONFIRM_VOL_MULT    = 0.15         # was 0.05
CONFIRM_BASE_VOL    = 10.0
CONFIRM_TIMEOUT_SEC = 60

# --- NO KILL SWITCH ------------------------------------------
KILL_SWITCH_ENABLED = False

# --- LOGS ----------------------------------------------------
CSV_SIGNALS    = "wolf_signals.csv"
CSV_TRADES     = "wolf_trades.csv"
STATE_FILE     = "wolf_state.json"
LOG_TO_CONSOLE = True
CONSOLE_TOP_N  = 4
