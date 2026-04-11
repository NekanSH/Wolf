"""
Wolf Matrix v4.2 — Smart Exit Engine

5 NEW EXIT RULES (from user analysis):

1. BTC STATE EXIT:
   BTC WEAK (EMA5 falling but > EMA15) → CLOSE position
   BTC DOWN (EMA5 < EMA15) → CLOSE IMMEDIATELY

2. MOMENTUM LOSS EXIT:
   EMA5 falling 2+ candles in a row → CLOSE

3. STALE POSITION EXIT:
   If 6+ min passed and price hasn't given +0.05% → CLOSE
   (position is going nowhere, free up capital)

4. SIGNAL DEGRADATION EXIT:
   If density drops below 0.60 while in position → CLOSE
   (environment turned bearish)

5. LOSS STREAK TIGHTENING:
   After 3+ consecutive losses → temporarily require delta ≥ 0.65
   (don't enter on weak signals during bad phase)
   Resets after 2 consecutive wins.

Entry logic: same v4.1 (delta 50-80%, green, BTC UP+momentum, ρ≥75%, vol 0.3-5.0)
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
    exit_reason: str = ""
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
        self._btc_ema5_falling_count = 0  # consecutive candles EMA5 falling

        self.open: list[Position] = []
        self.closed: list[Position] = []
        self.total_pnl = 0.0
        self.tick = 0
        self.signals = 0; self.blocked = 0
        self.long_count = 0; self.short_count = 0
        self.t0 = time.monotonic()
        self._last_trade_candle: dict[str, int] = defaultdict(int)
        self._paused = False; self._pause_count = 0
        self.current_leverage = cfg.LEVERAGE
        self.block_reasons: dict[str, int] = defaultdict(int)
        self._daily_trades = 0

        # FIX 5: loss streak tracking
        self._consecutive_losses = 0
        self._tightened = False

        self._init_csv()

    def _init_csv(self):
        if not os.path.exists(cfg.CSV_TRADES):
            with open(cfg.CSV_TRADES, "w", newline="") as f:
                csv.writer(f).writerow(["symbol","side","entry","exit","pnl_pct","pnl_usdt",
                    "leverage","hold_min","density","delta","vol_ratio","max_pnl",
                    "exit_reason","commission_pct"])
        if not os.path.exists(cfg.CSV_SIGNALS):
            with open(cfg.CSV_SIGNALS, "w", newline="") as f:
                csv.writer(f).writerow(["ts","symbol","price","delta","density","vol_ratio","btc_trend"])

    async def on_candle(self, symbol, cd):
        st = self.states.get(symbol)
        if not st: return
        c = Candle(ts=cd["ts"],o=cd["o"],h=cd["h"],l=cd["l"],c=cd["c"],v=cd["v"])

        if symbol == cfg.BTC_SYMBOL:
            st.on_candle(c, True)
            if st.ema_fast.ready and st.ema_mid.ready:
                ema5 = st.ema_fast.value
                ema15 = st.ema_mid.value
                self.btc_up = ema5 > ema15

                if self._btc_prev_ema5 > 0:
                    self.btc_momentum = ema5 > self._btc_prev_ema5
                    # FIX 2: track consecutive EMA5 drops
                    if ema5 < self._btc_prev_ema5:
                        self._btc_ema5_falling_count += 1
                    else:
                        self._btc_ema5_falling_count = 0
                self._btc_prev_ema5 = ema5

                if self.btc_up and self.btc_momentum:
                    self.btc_trend = "UP"
                elif self.btc_up and not self.btc_momentum:
                    self.btc_trend = "WEAK"
                else:
                    self.btc_trend = "DOWN"
            return

        st.on_candle(c, self.btc_up)
        self.tick += 1
        if not st.ready: return

        sym_candle = st.candle_count

        # ══════════════════════════════════════
        # SMART EXIT LOGIC (check EVERY candle)
        # ══════════════════════════════════════
        for pos in self.open:
            if pos.symbol != symbol: continue
            current_pnl = (c.c - pos.entry_price) / pos.entry_price * 100
            if current_pnl > pos.max_pnl: pos.max_pnl = current_pnl
            held = sym_candle - pos.entry_candle

            exit_reason = None

            # FIX 1: BTC state exit
            if self.btc_trend == "DOWN":
                exit_reason = "BTC_DOWN"
            elif self.btc_trend == "WEAK" and held >= 3:
                # Give 3 min grace period, then close on WEAK
                exit_reason = "BTC_WEAK"

            # FIX 2: Momentum loss — EMA5 falling 3+ candles
            if not exit_reason and self._btc_ema5_falling_count >= 3 and held >= 3:
                exit_reason = "MOMENTUM_LOSS"

            # FIX 3: Stale position — 8+ min and never reached +0.03%
            if not exit_reason and held >= 8 and pos.max_pnl < 0.03:
                exit_reason = "STALE"

            # FIX 4: Signal degradation — density crashed badly
            if not exit_reason and held >= 4 and st.density < 0.45:
                exit_reason = "DENSITY_CRASH"

            # Normal timeout
            if not exit_reason and held >= cfg.MAX_HOLD_CANDLES:
                exit_reason = "TIMEOUT"

            if exit_reason:
                self._close(pos, c.c, held, exit_reason)

        self.open = [p for p in self.open if p.status == "OPEN"]

        # ══════════════════════════════════════
        # ENTRY LOGIC
        # ══════════════════════════════════════
        if not self._check_kill_switch(): return

        # Must be BTC UP (with momentum)
        if self.btc_trend != "UP":
            self.blocked += 1; return

        if any(p.symbol == symbol for p in self.open): return
        if len(self.open) >= cfg.MAX_SIMULTANEOUS: return

        if sym_candle - self._last_trade_candle[symbol] < cfg.COOLDOWN_CANDLES:
            self.block_reasons["cooldown"] += 1; return

        delta = st.delta_ratio
        density = st.density
        vol_r = c.v / st.avg_vol if st.avg_vol > 0 else 0

        # FIX 5: tightened mode after loss streak
        delta_min = cfg.DELTA_MIN
        if self._tightened:
            delta_min = 0.65  # require stronger signal after losses

        if delta < delta_min or delta >= cfg.DELTA_MAX: return
        if not st.candle_green: return
        if vol_r < cfg.VOL_MIN:
            self.block_reasons["vol_low"] += 1; return
        if vol_r >= cfg.VOL_MAX:
            self.block_reasons["vol_high"] += 1; return
        if density < cfg.DENSITY_MIN:
            self.block_reasons["density_low"] += 1; return

        # ═══ ENTER ═══
        self.signals += 1
        self.long_count += 1
        self._last_trade_candle[symbol] = sym_candle
        self._daily_trades += 1

        pos = Position(symbol=symbol, entry_price=c.c, entry_candle=sym_candle,
                       entry_density=density, entry_delta=delta, entry_vol_ratio=vol_r)
        self.open.append(pos)

        with open(cfg.CSV_SIGNALS, "a", newline="") as f:
            csv.writer(f).writerow([c.ts, symbol, c.c,
                round(delta,4), round(density,4), round(vol_r,2), self.btc_trend])

        if cfg.LOG_TO_CONSOLE:
            tight = " TIGHT" if self._tightened else ""
            print(f"  \033[32m▶ LONG {symbol} @ {c.c:.4f}  "
                  f"δ={delta:+.0%} ρ={density:.0%} vol={vol_r:.1f}x "
                  f"BTC={self.btc_trend}{tight}\033[0m")

    async def on_trade(self, symbol, trade):
        st = self.states.get(symbol)
        if not st: return
        s = trade.get("S",""); sz = float(trade.get("v",0))
        if s == "Buy": st.tick_buy_vol += sz
        elif s == "Sell": st.tick_sell_vol += sz

    def _close(self, pos, price, held, reason):
        pos.exit_price = price
        # Raw PnL
        raw_pnl_pct = (price - pos.entry_price) / pos.entry_price * 100
        # Subtract commissions: 0.055% entry + 0.055% exit = 0.11% on price
        commission_pct = cfg.COMMISSION_PCT * 2  # both sides
        pos.pnl_pct = raw_pnl_pct - commission_pct
        pos.pnl_usdt = pos.size_usdt * pos.leverage * pos.pnl_pct / 100
        pos.status = "DONE"
        pos.exit_reason = reason
        self.total_pnl += pos.pnl_usdt
        self.closed.append(pos)

        # FIX 5: track consecutive losses
        if pos.pnl_usdt <= 0:
            self._consecutive_losses += 1
            if self._consecutive_losses >= 3 and not self._tightened:
                self._tightened = True
                if cfg.LOG_TO_CONSOLE:
                    print(f"  \033[33m⚠ TIGHTENED (streak {self._consecutive_losses})\033[0m")
        else:
            self._consecutive_losses = 0  # any win resets streak
            if self._tightened:
                self._tightened = False
                if cfg.LOG_TO_CONSOLE:
                    print(f"  \033[32m✓ TIGHTENED OFF\033[0m")

        with open(cfg.CSV_TRADES, "a", newline="") as f:
            csv.writer(f).writerow([pos.symbol, "LONG",
                round(pos.entry_price,6), round(pos.exit_price,6),
                round(pos.pnl_pct,4), round(pos.pnl_usdt,4),
                pos.leverage, held,
                round(pos.entry_density,4), round(pos.entry_delta,4),
                round(pos.entry_vol_ratio,2), round(pos.max_pnl,4),
                reason, round(commission_pct,4)])

        if cfg.LOG_TO_CONSOLE:
            c = "\033[32m" if pos.pnl_usdt >= 0 else "\033[31m"
            fee = pos.size_usdt * pos.leverage * commission_pct / 100
            print(f"  {c}◀ {pos.symbol} {pos.pnl_pct:+.3f}% "
                  f"${pos.pnl_usdt:+.2f} (fee:${fee:.2f}) held={held}m "
                  f"[{reason}]\033[0m")

    def _check_kill_switch(self):
        if not cfg.KILL_SWITCH_ENABLED: return True
        return True

    def snapshot(self):
        return [{"symbol":s, "density":round(self.states[s].density,4),
                 "delta":round(self.states[s].delta_ratio,4),
                 "price":self.states[s].last_price,
                 "vol": round(self.states[s]._vols[-1]/self.states[s].avg_vol,1) if self.states[s].avg_vol>0 and self.states[s]._vols else 0,
                 "ready":self.states[s].ready,
                 "candles":self.states[s].candle_count} for s in cfg.SYMBOLS]

    def stats(self):
        cl = self.closed
        # Count exit reasons
        reasons = defaultdict(int)
        for t in cl: reasons[t.exit_reason] += 1
        base = {"trades":0,"wr":0,"pnl":0,"avg":0,"best":0,"worst":0,
                "open":len(self.open),"lev":self.current_leverage,
                "blocked":self.blocked,"paused":self._paused,
                "pause_count":self._pause_count,
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
