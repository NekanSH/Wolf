"""
Wolf Matrix v7 — Smart Timeout
════════════════════════════════

537 СДЕЛОК АНАЛИЗ:
  hold=6 TIMEOUT: 483t, 17% WR, -$783 ← ВЕСЬ УБЫТОК
  hold≤5 (ранний): 54t, 70% WR, +$51  ← ЗАРАБАТЫВАЕТ
  TRAILING_TP: 73t, 63% WR, +$72      ← ЗАРАБАТЫВАЕТ
  44% позиций peak<0.05% = мертвые грузы 30 мин

ВЫВОД: 30-мин timeout убивает систему.
       Позиция которая не двинулась за 15 мин → мертвая → выходим.

НОВЫЕ ПРАВИЛА:
  1. Если hold≥3 и peak<0.07% → STALE_EXIT (мертвая позиция)
  2. Trailing TP остается (работает)
  3. Hard timeout = 5 свечей (25 мин) вместо 6 (30 мин)
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
MAX_SIMULTANEOUS = 6
MAX_HOLD_CANDLES = 5            # было 6 (30мин) → 5 (25мин), hold=5 даёт 55% WR
COOLDOWN_CANDLES = 2

# ─── STALE EXIT (ключевой фикс) ──────────────────────────────
# Если за 3 свечи (15 мин) пик не достиг 0.07% → мертвая позиция → выход
# Данные: 44% позиций peak<0.05%, сидят 30 мин до timeout
STALE_CANDLES = 3               # сколько свечей ждём
STALE_PEAK_MIN = 0.07           # если peak ниже этого → мертвая

# ─── TRAILING TP ─────────────────────────────────────────────
# Было 0.20% → только 20% сделок активировали trailing
# Снизили до 0.10% → поймаем ~30% сделок (вместо 20%)
# Данные: TRAILING_TP даёт 63% WR +$72 — это лучший выход
TRAILING_ACTIVATE = 0.10        # было 0.20
TRAILING_DISTANCE = 0.06        # было 0.10 (ближе = меньше отдаём)

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
