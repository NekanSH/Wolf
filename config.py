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

# ─── ENTRY — ТОЛЬКО СИЛЬНЫЕ СИГНАЛЫ ─────────────────────────
DELTA_LONG_MIN = 0.65           
DELTA_LONG_MAX = 0.90
DELTA_SHORT_MIN = -0.90
DELTA_SHORT_MAX = -0.65         
VOL_MIN = 1.0                   
VOL_MAX = 8.0
DENSITY_LONG_MIN = 0.70         
DENSITY_SHORT_MAX = 0.30        

# Entry mode: ALL | LONG_ONLY | SHORT_ONLY
ENTRY_MODE = "ALL"

# ─── STOP LOSS ─────────────────────────────────────────────────
STOP_LOSS_PCT = -99.0           # отключено

# ─── COMMISSIONS ──────────────────────────────────────────────
COMMISSION_PCT = 0.055          # per side

# ─── TRADING ──────────────────────────────────────────────────
LEVERAGE = 10
SHADOW_MODE = True
POSITION_SIZE_USDT = 100.0
MAX_SIMULTANEOUS = 6
MAX_HOLD_CANDLES = 5            
COOLDOWN_CANDLES = 2

# ─── STALE EXIT ──────────────────────────────────────────────
STALE_CANDLES = 4               
STALE_PEAK_MIN = 0.10           

# ─── TRAILING TP — ADAPTIVE ──────────────────────────────────
TRAILING_ACTIVATE_STRONG = 0.18
TRAILING_DISTANCE_STRONG = 0.09

TRAILING_ACTIVATE_WEAK = 0.12
TRAILING_DISTANCE_WEAK = 0.05

# ─── BTC ──────────────────────────────────────────────────────
# ─── ANTI-STALE CONFIRMATION ─────────────────────────────────
CONFIRM_VOL_MULT = 0.3          # нужно 30% от baseline volume в направлении
CONFIRM_BASE_VOL = 100.0        # минимальный baseline если тик пустой
CONFIRM_TIMEOUT_SEC = 30        # ФИКС: ТАЙМАУТ: сколько секунд ждем подтверждения

BTC_VELOCITY_MIN = 0.10         # предыдущее движение должно быть значимым
BTC_VELOCITY_DECAY = 0.5        # если текущее < 50% от предыдущего → WEAK

BTC_SYMBOL = "BTCUSDT"

# ─── NO KILL SWITCH ───────────────────────────────────────────
KILL_SWITCH_ENABLED = False

# ─── LOGS ─────────────────────────────────────────────────────
CSV_SIGNALS = "wolf_signals.csv"
CSV_TRADES = "wolf_trades.csv"
STATE_FILE = "wolf_state.json"
LOG_TO_CONSOLE = True
CONSOLE_TOP_N = 4
