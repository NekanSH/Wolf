"""
Wolf Matrix v5 — Clean Engine
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
        self._btc_prices: list[float] = []  # last 7 candles for velocity

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

        self._consecutive_losses = 0
        self._tightened = False

        self._pending: dict[str, dict] = {}
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

        if symbol == cfg.BTC_SYMBOL:
            st.on_candle(c, True)
            if st.ema_fast.ready and st.ema_mid.ready:
                ema5 = st.ema_fast.value
                ema15 = st.ema_mid.value
                self.btc_up = ema5 > ema15

                self._btc_prices.append(c.c)
                # ФИКС: Увеличен размер окна до 7 для корректного расчета velocity
                if len(self._btc_prices) > 7:
                    self._btc_prices.pop(0)

                ema_rising = ema5 > self._btc_prev_ema5 if self._btc_prev_ema5 > 0 else True
                self._btc_prev_ema5 = ema5

                vel_weak = False
                # ФИКС: Индексы исправлены на равные промежутки времени
                if len(self._btc_prices) >= 7:
                    recent = (self._btc_prices[-1] - self._btc_prices[-4]) / self._btc_prices[-4] * 100
                    prev = (self._btc_prices[-4] - self._btc_prices[-7]) / self._btc_prices[-7] * 100
                    
                    if prev > cfg.BTC_VELOCITY_MIN and recent < prev * cfg.BTC_VELOCITY_DECAY:
                        vel_weak = True

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

        for pos in self.open:
            if pos.symbol != symbol: continue
            if pos.side == "LONG":
                current_pnl = (c.c - pos.entry_price) / pos.entry_price * 100
            else:  
                current_pnl = (pos.entry_price - c.c) / pos.entry_price * 100
            
            if current_pnl > pos.max_pnl:
                pos.max_pnl = current_pnl
            held = sym_candle - pos.entry_candle

            exit_reason = None

            if not exit_reason and held >= cfg.STALE_CANDLES and pos.max_pnl < cfg.STALE_PEAK_MIN:
                exit_reason = "STALE"

            if not exit_reason and current_pnl <= cfg.STOP_LOSS_PCT:
                exit_reason = "STOP_LOSS"

            if not exit_reason:
                if self.btc_momentum:  
                    t_activate = cfg.TRAILING_ACTIVATE_STRONG
                    t_distance = cfg.TRAILING_DISTANCE_STRONG
                else:                  
                    t_activate = cfg.TRAILING_ACTIVATE_WEAK
                    t_distance = cfg.TRAILING_DISTANCE_WEAK

                if pos.max_pnl >= t_activate:
                    new_floor = pos.max_pnl - t_distance
                    if new_floor > pos.trailing_floor:
                        pos.trailing_floor = new_floor
                    if current_pnl <= pos.trailing_floor:
                        mode = "STRONG" if self.btc_momentum else "WEAK"
                        exit_reason = f"TRAILING_{mode}"

            if not exit_reason and held >= cfg.MAX_HOLD_CANDLES:
                exit_reason = "TIMEOUT"

            if exit_reason:
                self._close(pos, c.c, held, exit_reason)

        self.open = [p for p in self.open if p.status == "OPEN"]

        if any(p.symbol == symbol for p in self.open): return
        if len(self.open) >= cfg.MAX_SIMULTANEOUS: return

        if sym_candle - self._last_trade_candle[symbol] < cfg.COOLDOWN_CANDLES:
            self.block_reasons["cooldown"] += 1; return

        delta = st.delta_ratio
        density = st.density
        vol_r = c.v / st.avg_vol if st.avg_vol > 0 else 0

        if vol_r < cfg.VOL_MIN:
            self.block_reasons["vol_low"] += 1; return
        if vol_r >= cfg.VOL_MAX:
            self.block_reasons["vol_high"] += 1; return

        side = None

        long_ok = (cfg.ENTRY_MODE in ("ALL", "LONG_ONLY") and
                   delta >= cfg.DELTA_LONG_MIN and
                   delta <= cfg.DELTA_LONG_MAX and
                   density >= cfg.DENSITY_LONG_MIN and
                   st.candle_green)

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

        if symbol in self._pending:
            old = self._pending[symbol]
            if sym_candle > old["candle"]:
                self.block_reasons["pending_expired"] = self.block_reasons.get("pending_expired",0) + 1
                del self._pending[symbol]

        if symbol in self._pending: return

        current_tick_vol = st.tick_buy_vol if side == "LONG" else st.tick_sell_vol

        self._pending[symbol] = {
            "side": side,
            "delta": delta,
            "density": density,
            "vol_r": vol_r,
            "entry_price": c.c,
            "entry_vol": max(current_tick_vol, cfg.CONFIRM_BASE_VOL),
            "confirm_vol": 0.0,
            "candle": sym_candle,
            "btc_regime": self.btc_trend,
            "ts": time.time() # ФИКС: Добавлена временная метка
        }

        if cfg.LOG_TO_CONSOLE:
            sc = "\033[33m"  
            print(f"  {sc}⏳ PENDING {side} {symbol} @ {c.c:.4f}  "
                  f"δ={delta:+.0%} ρ={density:.0%} vol={vol_r:.1f}x "
                  f"BTC={self.btc_trend} — ждём подтверждения...\033[0m")

    async def on_trade(self, symbol, trade):
        st = self.states.get(symbol)
        if not st: return
        
        # ФИКС: Извлекаем цену и обновляем last_price
        p = float(trade.get("p", st.last_price))
        st.last_price = p
        
        s = trade.get("S",""); sz = float(trade.get("v",0))
        if s == "Buy": st.tick_buy_vol += sz
        elif s == "Sell": st.tick_sell_vol += sz

        if symbol not in self._pending: return
        pend = self._pending[symbol]

        # ФИКС: Проверка тайм-аута реального времени (30 секунд)
        if time.time() - pend["ts"] > getattr(cfg, 'CONFIRM_TIMEOUT_SEC', 30):
            self.block_reasons["pending_timeout"] = self.block_reasons.get("pending_timeout",0) + 1
            del self._pending[symbol]
            if cfg.LOG_TO_CONSOLE:
                print(f"  \033[31m⏳ PENDING {pend['side']} {symbol} TIMEOUT ({getattr(cfg, 'CONFIRM_TIMEOUT_SEC', 30)}s)\033[0m")
            return

        if pend["side"] == "LONG" and s == "Buy":
            pend["confirm_vol"] += sz
        elif pend["side"] == "SHORT" and s == "Sell":
            pend["confirm_vol"] += sz

        needed = pend["entry_vol"] * cfg.CONFIRM_VOL_MULT
        if pend["confirm_vol"] >= needed:
            self._enter_confirmed(symbol, pend)
            del self._pending[symbol]

    def _enter_confirmed(self, symbol: str, pend: dict):
        st = self.states.get(symbol)
        if not st: return

        if any(p.symbol == symbol for p in self.open): return
        if len(self.open) >= cfg.MAX_SIMULTANEOUS: return

        side = pend["side"]
        price = st.last_price if st.last_price > 0 else pend["entry_price"]
        sym_candle = pend["candle"]

        self.signals += 1
        if side == "LONG": self.long_count += 1
        else: self.short_count += 1
        self._last_trade_candle[symbol] = sym_candle
        self._daily_trades += 1

        pos = Position(symbol=symbol, entry_price=price,
                       entry_candle=sym_candle,
                       entry_density=pend["density"],
                       entry_delta=pend["delta"],
                       entry_vol_ratio=pend["vol_r"],
                       side=side)
        pos.btc_regime = pend["btc_regime"]
        self.open.append(pos)

        with open(cfg.CSV_SIGNALS, "a", newline="") as f:
            csv.writer(f).writerow([int(time.time()*1000), symbol, side, price,
                round(pend["delta"],4), round(pend["density"],4),
                round(pend["vol_r"],2), pend["btc_regime"]])

        if cfg.LOG_TO_CONSOLE:
            sc = "\033[32m" if side == "LONG" else "\033[31m"
            print(f"  {sc}▶ CONFIRMED {side} {symbol} @ {price:.4f}  "
                  f"δ={pend['delta']:+.0%} vol={pend['vol_r']:.1f}x "
                  f"BTC={pend['btc_regime']}\033[0m")

    def _close(self, pos, price, held, reason):
        pos.exit_price = price
        if pos.side == "LONG":
            raw_pnl = (price - pos.entry_price) / pos.entry_price * 100
        else:
            raw_pnl = (pos.entry_price - price) / pos.entry_price * 100
        commission = cfg.COMMISSION_PCT * 2
        pos.pnl_pct = raw_pnl - commission
        pos.pnl_usdt = pos.size_usdt * pos.leverage * pos.pnl_pct / 100
        pos.status = "DONE"
        pos.exit_reason = reason
        self.total_pnl += pos.pnl_usdt
        self.closed.append(pos)
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
            col = "\033[32m" if pos.pnl_usdt >= 0 else "\033[31m"
            fee = pos.size_usdt * pos.leverage * commission / 100
            print(f"  {col}◀ {pos.side} {pos.symbol} {pos.pnl_pct:+.3f}% "
                  f"${pos.pnl_usdt:+.2f} (fee:${fee:.2f}) "
                  f"held={held}×5m [{reason}]\033[0m")

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
                "longs":self.long_count,
                "shorts":self.short_count, # ФИКС: Прокинута статистика для шортов
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
