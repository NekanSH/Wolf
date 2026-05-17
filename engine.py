"""Wolf Matrix v11 — Full Pattern Engine"""
from __future__ import annotations
import csv, json, os, time
from dataclasses import dataclass, field
from collections import defaultdict, deque
from datetime import datetime, timezone
import config as cfg
from indicators import Candle, SymbolState

def current_hour_utc() -> int:
    return datetime.now(timezone.utc).hour

def get_trailing_params(symbol: str) -> tuple[float, float]:
    s = symbol.upper()
    if "SUI" in s: return cfg.SUI_TRAILING_ACTIVATE, cfg.SUI_TRAILING_DISTANCE
    if "XRP" in s: return cfg.XRP_TRAILING_ACTIVATE, cfg.XRP_TRAILING_DISTANCE
    if "SOL" in s: return cfg.SOL_TRAILING_ACTIVATE, cfg.SOL_TRAILING_DISTANCE
    return cfg.ETH_TRAILING_ACTIVATE, cfg.ETH_TRAILING_DISTANCE

@dataclass
class Position:
    symbol: str; entry_price: float; entry_candle: int
    size_usdt: float = 0.0; leverage: int = 10
    exit_price: float = 0.0; pnl_pct: float = 0.0; pnl_usdt: float = 0.0
    status: str = "OPEN"; side: str = "LONG"
    entry_density: float = 0.0; entry_delta: float = 0.0
    entry_vol_ratio: float = 0.0; max_pnl: float = 0.0
    trailing_floor: float = -999.0; exit_reason: str = ""
    btc_regime: str = "UP"; entry_imbalance: float = 0.0
    entry_velocity: float = 0.0; entry_hour: int = 0
    entry_green_count: int = 0; entry_spread: float = 0.0
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
        self.signals = 0; self.long_count = 0; self.short_count = 0
        self.blocked = 0; self._daily_trades = 0
        self._consecutive_losses = 0; self._tightened = False
        self.t0 = time.monotonic()
        self._last_trade_candle: dict[str, int] = defaultdict(int)
        self.current_leverage = cfg.LEVERAGE
        self.block_reasons: dict[str, int] = defaultdict(int)
        self._pending: dict[str, dict] = {}

        # ── Консенсус: цвет последней свечи по каждому символу
        self._last_green: dict[str, bool] = {s: False for s in cfg.SYMBOLS}

        # ── Спред история (для динамического порога)
        self._spread_history: deque = deque(maxlen=200)

        # ── Средний размер сделки история
        self._trade_size_history: deque = deque(maxlen=200)
        self._current_trade_sizes: dict[str, list] = defaultdict(list)

        self._init_csv()

    def _init_csv(self):
        if not os.path.exists(cfg.CSV_TRADES):
            with open(cfg.CSV_TRADES, "w", newline="") as f:
                csv.writer(f).writerow([
                    "symbol","side","entry","exit","pnl_pct","pnl_usdt",
                    "leverage","hold_candles","density","delta","vol_ratio",
                    "max_pnl","exit_reason","btc_regime",
                    "imbalance","velocity","hour","green_count","spread"
                ])
        if not os.path.exists(cfg.CSV_SIGNALS):
            with open(cfg.CSV_SIGNALS, "w", newline="") as f:
                csv.writer(f).writerow([
                    "ts","symbol","side","price","delta","density",
                    "vol_ratio","btc_trend","imbalance","velocity",
                    "hour","green_count","spread"
                ])

    @property
    def green_count(self) -> int:
        """Сколько символов сейчас зелёные."""
        return sum(1 for v in self._last_green.values() if v)

    def _get_spread(self, symbol: str) -> float:
        """Текущий спред символа из стакана."""
        st = self.states.get(symbol)
        if not st or not st.book.ready: return 0.0
        if not st.book.bids or not st.book.asks: return 0.0
        best_bid = max(st.book.bids.keys())
        best_ask = min(st.book.asks.keys())
        mid = (best_bid + best_ask) / 2
        return (best_ask - best_bid) / mid * 100 if mid > 0 else 0.0

    def _spread_is_wide(self, spread: float) -> bool:
        """Спред выше медианы исторических значений."""
        if not cfg.SPREAD_FILTER_ENABLED: return True
        if len(self._spread_history) < 20: return True  # нет данных — не блокируем
        threshold = sorted(self._spread_history)[len(self._spread_history) * cfg.SPREAD_PERCENTILE // 100]
        return spread >= threshold

    def _trades_are_whale(self, symbol: str) -> bool:
        """Средний размер сделки крупнее обычного."""
        if not cfg.WHALE_FILTER_ENABLED: return True
        sizes = self._current_trade_sizes.get(symbol, [])
        if not sizes or not self._trade_size_history or len(self._trade_size_history) < 20:
            return True  # нет данных — не блокируем
        avg_now    = sum(sizes) / len(sizes)
        avg_hist   = sum(self._trade_size_history) / len(self._trade_size_history)
        return avg_now >= avg_hist * cfg.WHALE_SIZE_MULT

    def _check_session(self, side: str, symbol: str) -> tuple[bool, str]:
        hour = current_hour_utc()
        if cfg.WEAK_PAUSE and self.btc_trend == "WEAK":
            return False, "btc_weak_pause"
        if side == "LONG":
            if self.btc_trend != "UP":
                return False, "long_needs_btc_up"
            if symbol not in cfg.LONG_SYMBOLS:
                return False, f"long_sym_blocked"
            if hour not in cfg.SESSION_LONG_HOURS:
                return False, f"long_bad_hour_{hour}utc"
        elif side == "SHORT":
            if self.btc_trend != "DOWN":
                return False, "short_needs_btc_down"
            if symbol not in cfg.SHORT_SYMBOLS:
                return False, f"short_sym_blocked"
            if hour not in cfg.SESSION_SHORT_HOURS:
                return False, f"short_bad_hour_{hour}utc"
        return True, ""

    def _check_consensus(self, side: str) -> tuple[bool, str]:
        gc = self.green_count
        if side == "LONG" and gc < cfg.CONSENSUS_LONG_MIN:
            return False, f"consensus_long_fail_{gc}green"
        if side == "SHORT" and gc > cfg.CONSENSUS_SHORT_MAX:
            return False, f"consensus_short_fail_{gc}green"
        return True, ""

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

        # Обновляем цвет свечи для консенсуса
        if symbol in cfg.SYMBOLS:
            self._last_green[symbol] = c.c > c.o

        # Обновляем историю размера сделок
        sizes = self._current_trade_sizes.pop(symbol, [])
        if sizes:
            avg_size = sum(sizes) / len(sizes)
            self._trade_size_history.append(avg_size)

        st.on_candle(c, self.btc_up)
        self.tick += 1
        if not st.ready: return
        sym_candle = st.candle_count

        # Expire pending
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
            held = sym_candle - pos.entry_candle; reason = None
            if held >= cfg.STALE_CANDLES and pos.max_pnl < cfg.STALE_PEAK_MIN:
                reason = "STALE"
            if not reason and cur <= cfg.STOP_LOSS_PCT:
                reason = "STOP_LOSS"
            if not reason:
                t_act, t_dis = get_trailing_params(pos.symbol)
                if pos.max_pnl >= t_act:
                    nf = max(pos.max_pnl - t_dis, cfg.TRAILING_FLOOR_MIN)
                    if nf > pos.trailing_floor: pos.trailing_floor = nf
                    if cur <= pos.trailing_floor:
                        reason = f"TRAILING_{pos.symbol[:3]}"
            if not reason and held >= cfg.MAX_HOLD_CANDLES:
                reason = "TIMEOUT"
            if reason: self._close(pos, c.c, held, reason)
        self.open = [p for p in self.open if p.status=="OPEN"]

        # ── ENTRY ─────────────────────────────────────────────
        if any(p.symbol==symbol for p in self.open): return
        if len(self.open) >= cfg.MAX_SIMULTANEOUS: return
        if symbol in self._pending: return
        if sym_candle - self._last_trade_candle[symbol] < cfg.COOLDOWN_CANDLES:
            self.block_reasons["cooldown"] += 1; return

        delta = st.delta_ratio; density = st.density
        vol_r = c.v/st.avg_vol if st.avg_vol > 0 else 0
        if vol_r < cfg.VOL_MIN: self.block_reasons["vol_low"] += 1;  return
        if vol_r >= cfg.VOL_MAX: self.block_reasons["vol_high"] += 1; return

        long_ok  = (cfg.DELTA_LONG_MIN  <= delta <= cfg.DELTA_LONG_MAX and
                    density >= cfg.DENSITY_LONG_MIN and st.candle_green)
        short_ok = (cfg.DELTA_SHORT_MIN <= delta <= cfg.DELTA_SHORT_MAX and
                    density <= cfg.DENSITY_SHORT_MAX and not st.candle_green)

        if long_ok:    side = "LONG"
        elif short_ok: side = "SHORT"
        else: return

        # ── ФИЛЬТР 1: СЕССИЯ + СИМВОЛ ────────────────────────
        ok, reason = self._check_session(side, symbol)
        if not ok:
            self.block_reasons[reason] = self.block_reasons.get(reason,0)+1; return

        # ── ФИЛЬТР 2: КОНСЕНСУС МОНЕТ ─────────────────────────
        ok, reason = self._check_consensus(side)
        if not ok:
            self.block_reasons[reason] = self.block_reasons.get(reason,0)+1; return

        # ── ФИЛЬТР 3: СПРЕД ───────────────────────────────────
        spread = self._get_spread(symbol)
        if spread > 0: self._spread_history.append(spread)
        if not self._spread_is_wide(spread):
            self.block_reasons["spread_narrow"] = self.block_reasons.get("spread_narrow",0)+1; return

        # ── ФИЛЬТР 4: КИТЫ ────────────────────────────────────
        if not self._trades_are_whale(symbol):
            self.block_reasons["whale_fail"] = self.block_reasons.get("whale_fail",0)+1; return

        hour = current_hour_utc()
        gc   = self.green_count
        self._pending[symbol] = {
            "side": side, "delta": delta, "density": density, "vol_r": vol_r,
            "entry_price": c.c, "candle": sym_candle,
            "btc_regime": self.btc_trend, "ts": time.monotonic(),
            "flow_ok_since": None, "flow_checks": 0,
            "hour": hour, "green_count": gc, "spread": round(spread, 5),
        }
        if cfg.LOG_TO_CONSOLE:
            print(f"  \033[33m⏳ {side} {symbol} @ {c.c:.4f} "
                  f"δ={delta:+.0%} ρ={density:.0%} "
                  f"BTC={self.btc_trend} {hour:02d}UTC "
                  f"green={gc}/4 spr={spread:.4f}% → flow...\033[0m")

    async def on_orderbook(self, symbol: str, ob_type: str, data: dict):
        st = self.states.get(symbol)
        if not st: return
        if ob_type == "snapshot": st.book.apply_snapshot(data)
        else:                     st.book.apply_delta(data)
        if symbol in self._pending and st.book.ready:
            await self._check_flow(symbol)

    async def on_trade(self, symbol, trade):
        st = self.states.get(symbol)
        if not st: return
        p  = float(trade.get("p", 0))
        if p > 0: st.last_price = p
        s  = trade.get("S",""); sz = float(trade.get("v", 0))
        if s == "Buy":  st.tick_buy_vol += sz; st.velocity.add_tick(sz, 0.0)
        elif s == "Sell": st.tick_sell_vol += sz; st.velocity.add_tick(0.0, sz)
        if sz > 0: self._current_trade_sizes[symbol].append(sz)
        if symbol in self._pending:
            await self._check_flow(symbol)

    async def _check_flow(self, symbol: str):
        if symbol not in self._pending: return
        pend = self._pending[symbol]; st = self.states.get(symbol)
        if not st: return
        now = time.monotonic()
        if now - pend["ts"] > cfg.CONFIRM_TIMEOUT_SEC:
            self.block_reasons["flow_timeout"] = self.block_reasons.get("flow_timeout",0)+1
            del self._pending[symbol]; return
        side = pend["side"]
        if st.book.ready:
            imbalance = st.book.imbalance
            book_ok = (imbalance >= cfg.BOOK_IMBALANCE_MIN if side=="LONG"
                       else imbalance <= 1.0/cfg.BOOK_IMBALANCE_MIN)
        else:
            imbalance = 1.0; book_ok = True
        vel = st.velocity.velocity; vel_ok = vel >= cfg.TICK_VEL_MIN
        net = st.velocity.current_net_delta()
        net_ok = (net > 0) if side=="LONG" else (net < 0)
        flow_ok = book_ok and vel_ok and net_ok
        if flow_ok:
            if pend["flow_ok_since"] is None: pend["flow_ok_since"] = now
            pend["flow_checks"] += 1
            if (now - pend["flow_ok_since"] >= cfg.FLOW_PERSIST_SEC and
                    pend["flow_checks"] >= cfg.FLOW_CHECKS_MIN):
                self._enter_confirmed(symbol, pend, imbalance, vel)
                del self._pending[symbol]
        else:
            pend["flow_ok_since"] = None; pend["flow_checks"] = 0

    def _enter_confirmed(self, symbol, pend, imbalance, velocity):
        st = self.states.get(symbol)
        if not st: return
        if any(p.symbol==symbol for p in self.open): return
        if len(self.open) >= cfg.MAX_SIMULTANEOUS: return
        side  = pend["side"]
        price = st.last_price if st.last_price > 0 else pend["entry_price"]
        self.signals += 1
        if side=="LONG": self.long_count += 1
        else: self.short_count += 1
        self._last_trade_candle[symbol] = pend["candle"]
        self._daily_trades += 1
        pos = Position(
            symbol=symbol, entry_price=price, entry_candle=pend["candle"],
            entry_density=pend["density"], entry_delta=pend["delta"],
            entry_vol_ratio=pend["vol_r"], side=side,
            entry_imbalance=round(imbalance,3),
            entry_velocity=round(velocity,3),
            entry_hour=pend["hour"],
            entry_green_count=pend["green_count"],
            entry_spread=pend["spread"],
        )
        pos.btc_regime = pend["btc_regime"]
        self.open.append(pos)
        t_act, t_dis = get_trailing_params(symbol)
        with open(cfg.CSV_SIGNALS, "a", newline="") as f:
            csv.writer(f).writerow([
                int(time.time()*1000), symbol, side, price,
                round(pend["delta"],4), round(pend["density"],4),
                round(pend["vol_r"],2), pend["btc_regime"],
                round(imbalance,3), round(velocity,3),
                pend["hour"], pend["green_count"], pend["spread"]
            ])
        if cfg.LOG_TO_CONSOLE:
            sc = "\033[32m" if side=="LONG" else "\033[31m"
            elapsed = time.monotonic() - pend["ts"]
            print(f"  {sc}▶ {side} {symbol} @ {price:.4f} "
                  f"δ={pend['delta']:+.0%} BTC={pend['btc_regime']} "
                  f"{pend['hour']:02d}UTC green={pend['green_count']}/4 "
                  f"spr={pend['spread']:.4f}% "
                  f"trail={t_act}% ({elapsed:.1f}с)\033[0m")

    def _close(self, pos, price, held, reason):
        pos.exit_price = price
        raw  = ((price-pos.entry_price)/pos.entry_price*100 if pos.side=="LONG"
                else (pos.entry_price-price)/pos.entry_price*100)
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
                reason, pos.btc_regime,
                round(pos.entry_imbalance,3), round(pos.entry_velocity,3),
                pos.entry_hour, pos.entry_green_count, pos.entry_spread
            ])
        if cfg.LOG_TO_CONSOLE:
            col = "\033[32m" if pos.pnl_usdt>=0 else "\033[31m"
            fee = pos.size_usdt * pos.leverage * comm / 100
            print(f"  {col}◀ {pos.side} {pos.symbol} {pos.pnl_pct:+.3f}% "
                  f"${pos.pnl_usdt:+.2f} (fee:${fee:.2f}) "
                  f"held={held}×5m peak={pos.max_pnl:.3f}% "
                  f"[{reason}] {pos.entry_hour:02d}UTC "
                  f"green={pos.entry_green_count}/4\033[0m")

    def snapshot(self):
        hour = current_hour_utc(); gc = self.green_count
        result = []
        for s in cfg.SYMBOLS:
            st = self.states[s]
            vol = round(st._vols[-1]/st.avg_vol,1) if st.avg_vol>0 and st._vols else 0
            imb = round(st.book.imbalance,2) if st.book.ready else 0.0
            vel = round(min(st.velocity.velocity,50.0),2)
            spd = round(self._get_spread(s),4)
            long_ok,  _ = self._check_session("LONG",  s)
            short_ok, _ = self._check_session("SHORT", s)
            if long_ok:    session = f"LONG✓ g={gc}/4"
            elif short_ok: session = f"SHORT✓ g={gc}/4"
            else:          session = f"pause {hour:02d}UTC g={gc}/4"
            result.append({
                "symbol":s, "density":round(st.density,4),
                "delta":round(st.delta_ratio,4), "price":st.last_price,
                "vol":vol, "ready":st.ready, "candles":st.candle_count,
                "imbalance":imb, "velocity":vel,
                "spread":spd, "session":session
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
            "tightened":self._tightened,
            "loss_streak":self._consecutive_losses
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
