"""Wolf Matrix v9 — Orderflow Confirmation Engine"""
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
    exit_price: float = 0.0; pnl_pct: float = 0.0; pnl_usdt: float = 0.0
    status: str = "OPEN"; side: str = "LONG"
    entry_density: float = 0.0; entry_delta: float = 0.0
    entry_vol_ratio: float = 0.0; max_pnl: float = 0.0
    trailing_floor: float = -999.0; exit_reason: str = ""; btc_regime: str = "UP"
    entry_imbalance: float = 0.0; entry_velocity: float = 0.0   # НОВОЕ для анализа
    def __post_init__(self):
        if not self.size_usdt: self.size_usdt = cfg.POSITION_SIZE_USDT
        if self.leverage == 10: self.leverage = cfg.LEVERAGE

class WolfEngine:
    def __init__(self):
        all_s = list(cfg.SYMBOLS)
        if cfg.BTC_SYMBOL not in all_s: all_s.append(cfg.BTC_SYMBOL)
        self.states = {s: SymbolState(s) for s in all_s}
        self.btc_up = True; self.btc_momentum = True; self.btc_trend = "UP"
        self._btc_prev_ema5 = 0.0; self._btc_prices: list[float] = []
        self._btc_macro_prices: list[float] = []
        self.btc_macro_ok = False; self.btc_macro_dir = "NONE"
        self.open: list[Position] = []; self.closed: list[Position] = []
        self.total_pnl = 0.0; self.tick = 0
        self.signals = 0; self.blocked = 0; self.long_count = 0; self.short_count = 0
        self.t0 = time.monotonic()
        self._last_trade_candle: dict[str, int] = defaultdict(int)
        self.current_leverage = cfg.LEVERAGE
        self.block_reasons: dict[str, int] = defaultdict(int)
        self._daily_trades = 0; self._consecutive_losses = 0; self._tightened = False
        # PENDING: {symbol → {..., flow_ok_since, flow_checks}}
        self._pending: dict[str, dict] = {}
        self._init_csv()

    def _init_csv(self):
        if not os.path.exists(cfg.CSV_TRADES):
            with open(cfg.CSV_TRADES, "w", newline="") as f:
                csv.writer(f).writerow([
                    "symbol","side","entry","exit","pnl_pct","pnl_usdt",
                    "leverage","hold_candles","density","delta","vol_ratio",
                    "max_pnl","exit_reason","btc_regime","imbalance","velocity"
                ])
        if not os.path.exists(cfg.CSV_SIGNALS):
            with open(cfg.CSV_SIGNALS, "w", newline="") as f:
                csv.writer(f).writerow([
                    "ts","symbol","side","price","delta","density",
                    "vol_ratio","btc_trend","imbalance","velocity"
                ])

    # ── BTC & CANDLE ──────────────────────────────────────────
    async def on_candle(self, symbol, cd):
        st = self.states.get(symbol)
        if not st: return
        c = Candle(ts=cd["ts"],o=cd["o"],h=cd["h"],l=cd["l"],c=cd["c"],v=cd["v"])

        if symbol == cfg.BTC_SYMBOL:
            st.on_candle(c, True)
            if st.ema_fast.ready and st.ema_mid.ready:
                ema5 = st.ema_fast.value; ema15 = st.ema_mid.value
                self.btc_up = ema5 > ema15
                self._btc_prices.append(c.c)
                if len(self._btc_prices) > 7: self._btc_prices.pop(0)
                self._btc_macro_prices.append(c.c)
                if len(self._btc_macro_prices) > cfg.BTC_MACRO_CANDLES+1:
                    self._btc_macro_prices.pop(0)
                if len(self._btc_macro_prices) >= cfg.BTC_MACRO_CANDLES:
                    oldest = self._btc_macro_prices[0]; newest = self._btc_macro_prices[-1]
                    move = (newest-oldest)/oldest*100
                    if   move >=  cfg.BTC_MACRO_MIN_MOVE: self.btc_macro_ok=True;  self.btc_macro_dir="UP"
                    elif move <= -cfg.BTC_MACRO_MIN_MOVE: self.btc_macro_ok=True;  self.btc_macro_dir="DOWN"
                    else:                                  self.btc_macro_ok=False; self.btc_macro_dir="SIDE"
                ema_rising = ema5 > self._btc_prev_ema5 if self._btc_prev_ema5 > 0 else True
                self._btc_prev_ema5 = ema5
                vel_weak = False
                if len(self._btc_prices) >= 7:
                    recent = (self._btc_prices[-1]-self._btc_prices[-4])/self._btc_prices[-4]*100
                    prev   = (self._btc_prices[-4]-self._btc_prices[-7])/self._btc_prices[-7]*100
                    if prev > cfg.BTC_VELOCITY_MIN and recent < prev*cfg.BTC_VELOCITY_DECAY:
                        vel_weak = True
                if self.btc_up and ema_rising and not vel_weak:
                    self.btc_trend="UP";   self.btc_momentum=True
                elif self.btc_up:
                    self.btc_trend="WEAK"; self.btc_momentum=False
                else:
                    self.btc_trend="DOWN"; self.btc_momentum=False
            return

        st.on_candle(c, self.btc_up)
        self.tick += 1
        if not st.ready: return
        sym_candle = st.candle_count

        # Expire pending on new candle
        if symbol in self._pending and sym_candle > self._pending[symbol]["candle"]:
            self.block_reasons["pending_expired"] = self.block_reasons.get("pending_expired",0)+1
            del self._pending[symbol]

        # ── EXIT ────────────────────────────────────────────────
        for pos in self.open:
            if pos.symbol != symbol: continue
            if pos.side == "LONG":
                intra_best = (c.h - pos.entry_price)/pos.entry_price*100
                cur        = (c.c - pos.entry_price)/pos.entry_price*100
            else:
                intra_best = (pos.entry_price - c.l)/pos.entry_price*100
                cur        = (pos.entry_price - c.c)/pos.entry_price*100
            if intra_best > pos.max_pnl: pos.max_pnl = intra_best
            held   = sym_candle - pos.entry_candle
            reason = None
            if held >= cfg.STALE_CANDLES and pos.max_pnl < cfg.STALE_PEAK_MIN:
                reason = "STALE"
            if not reason and cur <= cfg.STOP_LOSS_PCT:
                reason = "STOP_LOSS"
            if not reason:
                t_act = cfg.TRAILING_ACTIVATE_STRONG if self.btc_momentum else cfg.TRAILING_ACTIVATE_WEAK
                t_dis = cfg.TRAILING_DISTANCE_STRONG if self.btc_momentum else cfg.TRAILING_DISTANCE_WEAK
                if pos.max_pnl >= t_act:
                    nf = max(pos.max_pnl - t_dis, cfg.TRAILING_FLOOR_MIN)
                    if nf > pos.trailing_floor: pos.trailing_floor = nf
                    if cur <= pos.trailing_floor:
                        reason = "TRAILING_STRONG" if self.btc_momentum else "TRAILING_WEAK"
            if not reason and held >= cfg.MAX_HOLD_CANDLES:
                reason = "TIMEOUT"
            if reason: self._close(pos, c.c, held, reason)
        self.open = [p for p in self.open if p.status=="OPEN"]

        # ── ENTRY (свечные условия → PENDING) ────────────────────
        if any(p.symbol==symbol for p in self.open): return
        if len(self.open) >= cfg.MAX_SIMULTANEOUS: return
        if symbol in self._pending: return
        if sym_candle - self._last_trade_candle[symbol] < cfg.COOLDOWN_CANDLES:
            self.block_reasons["cooldown"] += 1; return

        delta = st.delta_ratio; density = st.density
        vol_r = c.v/st.avg_vol if st.avg_vol > 0 else 0
        if vol_r < cfg.VOL_MIN: self.block_reasons["vol_low"] += 1;  return
        if vol_r >= cfg.VOL_MAX: self.block_reasons["vol_high"] += 1; return

        if cfg.BTC_MACRO_FILTER and not self.btc_macro_ok:
            self.block_reasons["macro_side"] = self.block_reasons.get("macro_side",0)+1; return

        long_ok  = (cfg.ENTRY_MODE in ("ALL","LONG_ONLY") and
                    cfg.DELTA_LONG_MIN <= delta <= cfg.DELTA_LONG_MAX and
                    density >= cfg.DENSITY_LONG_MIN and st.candle_green and
                    (not cfg.BTC_MACRO_FILTER or self.btc_macro_dir != "DOWN"))
        short_ok = (cfg.ENTRY_MODE in ("ALL","SHORT_ONLY") and
                    cfg.DELTA_SHORT_MIN <= delta <= cfg.DELTA_SHORT_MAX and
                    density <= cfg.DENSITY_SHORT_MAX and not st.candle_green and
                    (not cfg.BTC_MACRO_FILTER or self.btc_macro_dir != "UP"))
        if long_ok:    side = "LONG"
        elif short_ok: side = "SHORT"
        else: return

        # Сигнал прошёл свечные фильтры → ставим в PENDING
        # Ждём orderflow подтверждения
        self._pending[symbol] = {
            "side": side, "delta": delta, "density": density, "vol_r": vol_r,
            "entry_price": c.c, "candle": sym_candle,
            "btc_regime": self.btc_trend, "ts": time.monotonic(),
            "flow_ok_since": None,   # когда оба условия (imbalance+velocity) стали True
            "flow_checks":   0,      # сколько раз подряд оба условия выполнены
        }
        if cfg.LOG_TO_CONSOLE:
            print(f"  \033[33m⏳ {side} {symbol} @ {c.c:.4f} "
                  f"δ={delta:+.0%} ρ={density:.0%} vol={vol_r:.1f}x "
                  f"BTC={self.btc_trend} → ждём orderflow...\033[0m")

    # ── ORDERBOOK ─────────────────────────────────────────────
    async def on_orderbook(self, symbol: str, ob_type: str, data: dict) -> None:
        """Обновляем локальный стакан; если символ в PENDING — проверяем imbalance."""
        st = self.states.get(symbol)
        if not st: return
        if ob_type == "snapshot":
            st.book.apply_snapshot(data)
        else:
            st.book.apply_delta(data)
        # Проверяем PENDING при каждом обновлении стакана
        if symbol in self._pending and st.book.ready:
            await self._check_flow(symbol)

    # ── TRADE STREAM ─────────────────────────────────────────
    async def on_trade(self, symbol, trade):
        st = self.states.get(symbol)
        if not st: return
        p  = float(trade.get("p", 0))
        if p > 0: st.last_price = p
        s  = trade.get("S",""); sz = float(trade.get("v", 0))
        if s == "Buy":  st.tick_buy_vol += sz; st.velocity.add_tick(sz,  0.0)
        elif s == "Sell": st.tick_sell_vol += sz; st.velocity.add_tick(0.0, sz)
        # Проверяем PENDING при каждом тике
        if symbol in self._pending:
            await self._check_flow(symbol)

    # ── FLOW CHECK (persistence logic) ───────────────────────
    async def _check_flow(self, symbol: str) -> None:
        """
        Главный фильтр: проверяем что orderflow ДЕРЖИТСЯ.
        Условия (оба должны быть True):
          1. book imbalance согласован со стороной
          2. tick velocity ускоряется (импульс не затухает)
        Если оба выполнены FLOW_PERSIST_SEC сек подряд
        И минимум FLOW_CHECKS_MIN раз → входим.
        """
        if symbol not in self._pending: return
        pend = self._pending[symbol]
        st   = self.states.get(symbol)
        if not st: return
        now  = time.monotonic()

        # Таймаут ожидания
        if now - pend["ts"] > cfg.CONFIRM_TIMEOUT_SEC:
            self.block_reasons["flow_timeout"] = self.block_reasons.get("flow_timeout",0)+1
            if cfg.LOG_TO_CONSOLE:
                print(f"  \033[31m⌛ SKIP {pend['side']} {symbol} — "
                      f"orderflow не подтвердил за {cfg.CONFIRM_TIMEOUT_SEC}с\033[0m")
            del self._pending[symbol]; return

        side = pend["side"]

        # 1. Book imbalance
        if st.book.ready:
            imbalance = st.book.imbalance
            if side == "LONG":
                book_ok = imbalance >= cfg.BOOK_IMBALANCE_MIN
            else:
                book_ok = imbalance <= (1.0 / cfg.BOOK_IMBALANCE_MIN)
        else:
            book_ok = True   # стакан ещё не пришёл — не блокируем

        # 2. Tick velocity
        vel = st.velocity.velocity
        vel_ok = vel >= cfg.TICK_VEL_MIN

        # 3. Net delta согласован со стороной (дополнительная проверка)
        net = st.velocity.current_net_delta()
        net_ok = (net > 0) if side == "LONG" else (net < 0)

        flow_ok = book_ok and vel_ok and net_ok

        if flow_ok:
            if pend["flow_ok_since"] is None:
                pend["flow_ok_since"] = now
            pend["flow_checks"] += 1

            elapsed = now - pend["flow_ok_since"]
            if elapsed >= cfg.FLOW_PERSIST_SEC and pend["flow_checks"] >= cfg.FLOW_CHECKS_MIN:
                # ✓ Всё сошлось — входим
                self._enter_confirmed(symbol, pend, imbalance if st.book.ready else 0.0, vel)
                del self._pending[symbol]
        else:
            # Сигнал прервался → сбрасываем persistence
            if pend["flow_ok_since"] is not None and cfg.LOG_TO_CONSOLE:
                elapsed = now - pend["flow_ok_since"]
                print(f"  \033[31m⚡ {side} {symbol} flow прервался "
                      f"(book={'✓' if book_ok else '✗'} "
                      f"vel={'✓' if vel_ok else '✗'} "
                      f"net={'✓' if net_ok else '✗'}) "
                      f"держался {elapsed:.1f}с\033[0m")
            pend["flow_ok_since"] = None
            pend["flow_checks"]   = 0

    # ── ENTER ────────────────────────────────────────────────
    def _enter_confirmed(self, symbol: str, pend: dict, imbalance: float, velocity: float) -> None:
        st = self.states.get(symbol)
        if not st: return
        if any(p.symbol==symbol for p in self.open): return
        if len(self.open) >= cfg.MAX_SIMULTANEOUS: return
        side  = pend["side"]
        price = st.last_price if st.last_price > 0 else pend["entry_price"]
        sym_candle = pend["candle"]
        self.signals += 1
        if side=="LONG": self.long_count += 1
        else: self.short_count += 1
        self._last_trade_candle[symbol] = sym_candle
        self._daily_trades += 1
        pos = Position(
            symbol=symbol, entry_price=price, entry_candle=sym_candle,
            entry_density=pend["density"], entry_delta=pend["delta"],
            entry_vol_ratio=pend["vol_r"], side=side,
            entry_imbalance=round(imbalance,3), entry_velocity=round(velocity,3)
        )
        pos.btc_regime = pend["btc_regime"]
        self.open.append(pos)
        with open(cfg.CSV_SIGNALS, "a", newline="") as f:
            csv.writer(f).writerow([
                int(time.time()*1000), symbol, side, price,
                round(pend["delta"],4), round(pend["density"],4),
                round(pend["vol_r"],2), pend["btc_regime"],
                round(imbalance,3), round(velocity,3)
            ])
        if cfg.LOG_TO_CONSOLE:
            sc = "\033[32m" if side=="LONG" else "\033[31m"
            elapsed = time.monotonic() - pend["ts"]
            print(f"  {sc}▶ FLOW CONFIRMED {side} {symbol} @ {price:.4f} "
                  f"δ={pend['delta']:+.0%} imb={imbalance:.2f}x "
                  f"vel={velocity:.2f}x BTC={pend['btc_regime']} "
                  f"({elapsed:.1f}с)\033[0m")

    # ── CLOSE ────────────────────────────────────────────────
    def _close(self, pos, price, held, reason):
        pos.exit_price = price
        raw  = (price-pos.entry_price)/pos.entry_price*100 if pos.side=="LONG" \
               else (pos.entry_price-price)/pos.entry_price*100
        comm = cfg.COMMISSION_PCT * 2
        pos.pnl_pct  = raw - comm
        pos.pnl_usdt = pos.size_usdt * pos.leverage * pos.pnl_pct / 100
        pos.status   = "DONE"; pos.exit_reason = reason
        self.total_pnl += pos.pnl_usdt; self.closed.append(pos)
        if pos.pnl_usdt <= 0: self._consecutive_losses += 1
        else: self._consecutive_losses = 0
        with open(cfg.CSV_TRADES, "a", newline="") as f:
            csv.writer(f).writerow([
                pos.symbol, pos.side,
                round(pos.entry_price,6), round(pos.exit_price,6),
                round(pos.pnl_pct,4), round(pos.pnl_usdt,4),
                pos.leverage, held,
                round(pos.entry_density,4), round(pos.entry_delta,4),
                round(pos.entry_vol_ratio,2), round(pos.max_pnl,4),
                reason, getattr(pos,"btc_regime","UP"),
                round(pos.entry_imbalance,3), round(pos.entry_velocity,3)
            ])
        if cfg.LOG_TO_CONSOLE:
            col = "\033[32m" if pos.pnl_usdt>=0 else "\033[31m"
            fee = pos.size_usdt * pos.leverage * comm / 100
            print(f"  {col}◀ {pos.side} {pos.symbol} {pos.pnl_pct:+.3f}% "
                  f"${pos.pnl_usdt:+.2f} (fee:${fee:.2f}) "
                  f"held={held}×5m peak={pos.max_pnl:.3f}% [{reason}]\033[0m")

    # ── RUN.PY HOOKS ─────────────────────────────────────────
    def snapshot(self):
        result = []
        for s in cfg.SYMBOLS:
            st = self.states[s]
            vol = round(st._vols[-1]/st.avg_vol, 1) if st.avg_vol>0 and st._vols else 0
            imb = round(st.book.imbalance, 2) if st.book.ready else 0.0
            vel = round(st.velocity.velocity, 2)
            result.append({
                "symbol": s, "density": round(st.density,4),
                "delta": round(st.delta_ratio,4), "price": st.last_price,
                "vol": vol, "ready": st.ready, "candles": st.candle_count,
                "imbalance": imb, "velocity": vel
            })
        return result

    def stats(self):
        cl = self.closed; reasons = defaultdict(int)
        for t in cl: reasons[t.exit_reason] += 1
        base = {
            "trades":0,"wr":0,"pnl":0,"avg":0,"best":0,"worst":0,
            "open":len(self.open),"lev":self.current_leverage,
            "blocked":self.blocked,"paused":False,"pause_count":0,
            "longs":self.long_count,"shorts":self.short_count,
            "btc_up":self.btc_up,"btc_trend":self.btc_trend,
            "btc_macro_ok":self.btc_macro_ok,"btc_macro_dir":self.btc_macro_dir,
            "daily_trades":self._daily_trades,
            "block_reasons":dict(self.block_reasons),
            "exit_reasons":dict(reasons),
            "tightened":self._tightened,"loss_streak":self._consecutive_losses
        }
        if not cl: return base
        w = [p for p in cl if p.pnl_usdt > 0]
        base.update({
            "trades":len(cl),"wr":round(len(w)/len(cl)*100,1),
            "pnl":round(self.total_pnl,2),"avg":round(self.total_pnl/len(cl),2),
            "best":round(max(p.pnl_pct for p in cl),2),
            "worst":round(min(p.pnl_pct for p in cl),2)
        })
        return base

    def save(self):
        try:
            with open(cfg.STATE_FILE,"w") as f:
                json.dump({"tick":self.tick,"pnl":self.total_pnl,
                           "btc":self.btc_trend,"stats":self.stats()},f,indent=2)
        except: pass
