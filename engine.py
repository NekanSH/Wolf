"""
Wolf Matrix v5 — Clean Engine

ENTRY: delta 50-80% + green candle + BTC UP (EMA5>EMA15 + rising)
EXIT (3 reasons only):
  1. BTC_DOWN → EMA5 < EMA15 = real reversal, close immediately
  2. TRAILING_TP → peak hit 0.20%, then price fell back 0.10% → lock profit
  3. TIMEOUT → 6 candles (30 min) = time's up

NO BTC_WEAK exit (killed 92/112 trades in v4.2)
NO STALE exit (over-engineered)
NO DENSITY_CRASH exit (over-engineered)

Commissions: 0.055% × 2 = 0.11% deducted from every trade.
"""
from __future__ import annotations
import csv, json, os, time
from dataclasses import dataclass
from collections import defaultdict
import config as cfg
from indicators import Candle, SymbolState

@dataclass
class Position:
    symbol: str; entry_price: float; entry_candle: int
    size_usdt: float = 0.0; leverage: int = 10
    exit_price: float = 0.0
    pnl_pct: float = 0.0; pnl_usdt: float = 0.0
    status: str = "OPEN"; side: str = "LONG"
    entry_density: float = 0.0; entry_delta: float = 0.0
    entry_vol_ratio: float = 0.0; max_pnl: float = 0.0
    trailing_floor: float = -999.0
    exit_reason: str = ""
    btc_regime: str = "UP"
    def __post_init__(self):
        if not self.size_usdt: self.size_usdt = cfg.POSITION_SIZE_USDT
        if self.leverage == 10: self.leverage = cfg.LEVERAGE

class WolfEngine:
    def __init__(self):
        all_s = list(cfg.SYMBOLS)
        if cfg.BTC_SYMBOL not in all_s: all_s.append(cfg.BTC_SYMBOL)
        self.states = {s: SymbolState(s) for s in all_s}
        self.btc_up = True
        self.btc_momentum = True
        self.btc_trend = "UP"
        self._btc_prev_ema5 = 0.0
        self._btc_prices: list[float] = []  # last 6 candles for velocity

        self.open: list[Position] = []
        self.closed: list[Position] = []
        self.total_pnl = 0.0
        self.tick = 0
        self.signals = 0; self.blocked = 0
        self.long_count = 0; self.short_count = 0
        self.t0 = time.monotonic()
        self._last_trade_candle: dict[str, int] = defaultdict(int)
        self.current_leverage = cfg.LEVERAGE
        self.block_reasons: dict[str, int] = defaultdict(int)
        self._daily_trades = 0

        # Loss streak
        self._consecutive_losses = 0
        self._tightened = False

        self._init_csv()

    def _init_csv(self):
        if not os.path.exists(cfg.CSV_TRADES):
            with open(cfg.CSV_TRADES, "w", newline="") as f:
                csv.writer(f).writerow(["symbol","side","entry","exit",
                    "pnl_pct","pnl_usdt","leverage","hold_candles",
                    "density","delta","vol_ratio","max_pnl",
                    "exit_reason","btc_regime"])
        if not os.path.exists(cfg.CSV_SIGNALS):
            with open(cfg.CSV_SIGNALS, "w", newline="") as f:
                csv.writer(f).writerow(["ts","symbol","side","price","delta",
                    "density","vol_ratio","btc_trend"])

    async def on_candle(self, symbol, cd):
        st = self.states.get(symbol)
        if not st: return
        c = Candle(ts=cd["ts"],o=cd["o"],h=cd["h"],l=cd["l"],c=cd["c"],v=cd["v"])

        # ── BTC STATE: velocity-based, not just EMA ──
        if symbol == cfg.BTC_SYMBOL:
            st.on_candle(c, True)
            if st.ema_fast.ready and st.ema_mid.ready:
                ema5 = st.ema_fast.value
                ema15 = st.ema_mid.value
                self.btc_up = ema5 > ema15

                # Track BTC price history for velocity
                self._btc_prices.append(c.c)
                if len(self._btc_prices) > 6:
                    self._btc_prices.pop(0)

                # EMA momentum (existing)
                ema_rising = ema5 > self._btc_prev_ema5 if self._btc_prev_ema5 > 0 else True
                self._btc_prev_ema5 = ema5

                # VELOCITY: compare last 3 candles vs previous 3 candles
                # This catches impulse decay BEFORE EMA catches it
                vel_weak = False
                if len(self._btc_prices) >= 6:
                    # Movement in last 3 candles
                    recent = (self._btc_prices[-1] - self._btc_prices[-3]) / self._btc_prices[-3] * 100
                    # Movement in previous 3 candles
                    prev = (self._btc_prices[-3] - self._btc_prices[-6]) / self._btc_prices[-6] * 100
                    # If momentum decelerating significantly → WEAK
                    if prev > cfg.BTC_VELOCITY_MIN and recent < prev * cfg.BTC_VELOCITY_DECAY:
                        vel_weak = True

                # STRONG: EMA rising AND no velocity decay
                # WEAK: either EMA falling OR velocity decaying
                if self.btc_up and ema_rising and not vel_weak:
                    self.btc_trend = "UP"
                    self.btc_momentum = True
                elif self.btc_up:
                    self.btc_trend = "WEAK"
                    self.btc_momentum = False
                else:
                    self.btc_trend = "DOWN"
                    self.btc_momentum = False
            return

        st.on_candle(c, self.btc_up)
        self.tick += 1
        if not st.ready: return

        sym_candle = st.candle_count

        # ══════════════════════════════════
        # EXIT RULES — works for both LONG and SHORT
        # ══════════════════════════════════
        for pos in self.open:
            if pos.symbol != symbol: continue
            # Calculate PnL based on side
            if pos.side == "LONG":
                current_pnl = (c.c - pos.entry_price) / pos.entry_price * 100
            else:  # SHORT
                current_pnl = (pos.entry_price - c.c) / pos.entry_price * 100
            if current_pnl > pos.max_pnl:
                pos.max_pnl = current_pnl
            held = sym_candle - pos.entry_candle

            exit_reason = None

            # 1. STALE EXIT — мертвая позиция (ключевой фикс)
            # Если за 3 свечи (15 мин) цена не дала 0.07% → выходим
            # Данные: 44% позиций peak<0.05%, тянутся до timeout -$783
            if not exit_reason and held >= cfg.STALE_CANDLES and pos.max_pnl < cfg.STALE_PEAK_MIN:
                exit_reason = "STALE"

            # 2. STOP LOSS (фактически отключён - cfg.STOP_LOSS_PCT = -99)
            if not exit_reason and current_pnl <= cfg.STOP_LOSS_PCT:
                exit_reason = "STOP_LOSS"

            # 3. ADAPTIVE TRAILING TP
            # BTC STRONG → ждём 0.18%, отдаём 0.09% (даём дышать)
            # BTC WEAK   → фиксируем раньше: 0.12%, отдаём 0.05%
            # Не выходим по BTC_WEAK — меняем поведение trailing
            if not exit_reason:
                if self.btc_momentum:  # EMA5 растёт → STRONG
                    t_activate = cfg.TRAILING_ACTIVATE_STRONG
                    t_distance = cfg.TRAILING_DISTANCE_STRONG
                else:                  # EMA5 падает → WEAK
                    t_activate = cfg.TRAILING_ACTIVATE_WEAK
                    t_distance = cfg.TRAILING_DISTANCE_WEAK

                if pos.max_pnl >= t_activate:
                    new_floor = pos.max_pnl - t_distance
                    if new_floor > pos.trailing_floor:
                        pos.trailing_floor = new_floor
                    if current_pnl <= pos.trailing_floor:
                        mode = "STRONG" if self.btc_momentum else "WEAK"
                        exit_reason = f"TRAILING_{mode}"

            # 4. TIMEOUT (25 мин = 5 свечей)
            if not exit_reason and held >= cfg.MAX_HOLD_CANDLES:
                exit_reason = "TIMEOUT"

            if exit_reason:
                self._close(pos, c.c, held, exit_reason)

        self.open = [p for p in self.open if p.status == "OPEN"]

        # ══════════════════════════════════
        # ENTRY — RESEARCH MODE: LONG + SHORT
        # BTC state tagged per trade, no hard block
        # ══════════════════════════════════

        if any(p.symbol == symbol for p in self.open): return
        if len(self.open) >= cfg.MAX_SIMULTANEOUS: return

        if sym_candle - self._last_trade_candle[symbol] < cfg.COOLDOWN_CANDLES:
            self.block_reasons["cooldown"] += 1; return

        delta = st.delta_ratio
        density = st.density
        vol_r = c.v / st.avg_vol if st.avg_vol > 0 else 0

        # Volume filter (applies to both sides)
        if vol_r < cfg.VOL_MIN:
            self.block_reasons["vol_low"] += 1; return
        if vol_r >= cfg.VOL_MAX:
            self.block_reasons["vol_high"] += 1; return

        # Determine direction
        side = None

        # LONG conditions
        long_ok = (cfg.ENTRY_MODE in ("ALL", "LONG_ONLY") and
                   delta >= cfg.DELTA_LONG_MIN and
                   delta <= cfg.DELTA_LONG_MAX and
                   density >= cfg.DENSITY_LONG_MIN and
                   st.candle_green)

        # SHORT conditions
        short_ok = (cfg.ENTRY_MODE in ("ALL", "SHORT_ONLY") and
                    delta <= cfg.DELTA_SHORT_MAX and
                    delta >= cfg.DELTA_SHORT_MIN and
                    density <= cfg.DENSITY_SHORT_MAX and
                    not st.candle_green)

        if long_ok:
            side = "LONG"
        elif short_ok:
            side = "SHORT"
        else:
            return

        # ═══ ENTER ═══
        self.signals += 1
        if side == "LONG": self.long_count += 1
        else: self.short_count += 1
        self._last_trade_candle[symbol] = sym_candle
        self._daily_trades += 1

        pos = Position(symbol=symbol, entry_price=c.c, entry_candle=sym_candle,
                       entry_density=density, entry_delta=delta,
                       entry_vol_ratio=vol_r, side=side)
        # Tag with market regime
        pos.btc_regime = self.btc_trend  # UP / WEAK / DOWN
        self.open.append(pos)

        with open(cfg.CSV_SIGNALS, "a", newline="") as f:
            csv.writer(f).writerow([c.ts, symbol, side, c.c,
                round(delta,4), round(density,4), round(vol_r,2),
                self.btc_trend])

        if cfg.LOG_TO_CONSOLE:
            sc = "\033[32m" if side == "LONG" else "\033[31m"
            print(f"  {sc}▶ {side} {symbol} @ {c.c:.4f}  "
                  f"δ={delta:+.0%} ρ={density:.0%} vol={vol_r:.1f}x "
                  f"BTC={self.btc_trend}\033[0m")

    async def on_trade(self, symbol, trade):
        st = self.states.get(symbol)
        if not st: return
        s = trade.get("S",""); sz = float(trade.get("v",0))
        if s == "Buy": st.tick_buy_vol += sz
        elif s == "Sell": st.tick_sell_vol += sz

    def _close(self, pos, price, held, reason):
        pos.exit_price = price
        if pos.side == "LONG":
            raw_pnl = (price - pos.entry_price) / pos.entry_price * 100
        else:  # SHORT
            raw_pnl = (pos.entry_price - price) / pos.entry_price * 100
        commission = cfg.COMMISSION_PCT * 2
        pos.pnl_pct = raw_pnl - commission
        pos.pnl_usdt = pos.size_usdt * pos.leverage * pos.pnl_pct / 100
        pos.status = "DONE"
        pos.exit_reason = reason
        self.total_pnl += pos.pnl_usdt
        self.closed.append(pos)

        # Loss streak
        if pos.pnl_usdt <= 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

        with open(cfg.CSV_TRADES, "a", newline="") as f:
            csv.writer(f).writerow([pos.symbol, pos.side,
                round(pos.entry_price,6), round(pos.exit_price,6),
                round(pos.pnl_pct,4), round(pos.pnl_usdt,4),
                pos.leverage, held,
                round(pos.entry_density,4), round(pos.entry_delta,4),
                round(pos.entry_vol_ratio,2), round(pos.max_pnl,4),
                reason, getattr(pos, 'btc_regime', 'UP')])

        if cfg.LOG_TO_CONSOLE:
            c = "\033[32m" if pos.pnl_usdt >= 0 else "\033[31m"
            fee = pos.size_usdt * pos.leverage * commission / 100
            print(f"  {c}◀ {pos.side} {pos.symbol} {pos.pnl_pct:+.3f}% "
                  f"${pos.pnl_usdt:+.2f} (fee:${fee:.2f}) "
                  f"held={held}×5m [{reason}] BTC={getattr(pos,'btc_regime','?')}\033[0m")

    def snapshot(self):
        return [{"symbol":s, "density":round(self.states[s].density,4),
                 "delta":round(self.states[s].delta_ratio,4),
                 "price":self.states[s].last_price,
                 "vol": round(self.states[s]._vols[-1]/self.states[s].avg_vol,1) if self.states[s].avg_vol>0 and self.states[s]._vols else 0,
                 "ready":self.states[s].ready,
                 "candles":self.states[s].candle_count} for s in cfg.SYMBOLS]

    def stats(self):
        cl = self.closed
        reasons = defaultdict(int)
        for t in cl: reasons[t.exit_reason] += 1
        base = {"trades":0,"wr":0,"pnl":0,"avg":0,"best":0,"worst":0,
                "open":len(self.open),"lev":self.current_leverage,
                "blocked":self.blocked,"paused":False,"pause_count":0,
                "longs":self.long_count,"shorts":0,
                "btc_up":self.btc_up,"btc_trend":self.btc_trend,
                "daily_trades":self._daily_trades,
                "block_reasons":dict(self.block_reasons),
                "exit_reasons":dict(reasons),
                "tightened":self._tightened,
                "loss_streak":self._consecutive_losses}
        if not cl: return base
        w = [p for p in cl if p.pnl_usdt > 0]
        base.update({"trades":len(cl), "wr":round(len(w)/len(cl)*100,1),
                "pnl":round(self.total_pnl,2),
                "avg":round(self.total_pnl/len(cl),2),
                "best":round(max(p.pnl_pct for p in cl),2),
                "worst":round(min(p.pnl_pct for p in cl),2)})
        return base

    def save(self):
        try:
            with open(cfg.STATE_FILE,"w") as f:
                json.dump({"tick":self.tick,"pnl":self.total_pnl,
                           "btc":self.btc_trend,"stats":self.stats()},f,indent=2)
        except: pass
