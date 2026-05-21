"""Wolf Matrix v13 — Simple Session Engine"""
from __future__ import annotations
import csv, json, os, time
from dataclasses import dataclass
from collections import defaultdict
from datetime import datetime, timezone
import config as cfg
from indicators import Candle, SymbolState

def current_hour_utc() -> int:
    return datetime.now(timezone.utc).hour

def get_trailing(symbol: str) -> tuple[float, float]:
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
    max_pnl: float = 0.0; trailing_floor: float = -999.0
    exit_reason: str = ""; btc_regime: str = "UP"
    entry_vol: float = 0.0; entry_hour: int = 0
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
        self.btc_macro_ok = False; self.btc_macro_dir = "NONE"
        self._btc_macro_prices: list[float] = []

        self.open: list[Position] = []; self.closed: list[Position] = []
        self.total_pnl = 0.0; self.tick = 0
        self.signals = 0; self.long_count = 0; self.short_count = 0
        self._daily_trades = 0; self._consecutive_losses = 0
        self.t0 = time.monotonic()
        self._last_trade_candle: dict[str, int] = defaultdict(int)
        self.current_leverage = cfg.LEVERAGE
        self.block_reasons: dict[str, int] = defaultdict(int)
        self._init_csv()

    def _init_csv(self):
        if not os.path.exists(cfg.CSV_TRADES):
            with open(cfg.CSV_TRADES, "w", newline="") as f:
                csv.writer(f).writerow([
                    "symbol","side","entry","exit","pnl_pct","pnl_usdt",
                    "leverage","hold_candles","vol_ratio","max_pnl",
                    "exit_reason","btc_regime","hour"
                ])
        if not os.path.exists(cfg.CSV_SIGNALS):
            with open(cfg.CSV_SIGNALS, "w", newline="") as f:
                csv.writer(f).writerow([
                    "ts","symbol","side","price","vol_ratio","btc_trend","hour"
                ])

    def _check_entry(self, symbol: str) -> tuple[str|None, str]:
        """
        Упрощённый вход: только час + BTC + символ.
        Возвращает (side, block_reason).
        """
        hour = current_hour_utc()

        if cfg.WEAK_PAUSE and self.btc_trend == "WEAK":
            return None, "btc_weak"

        # SHORT
        if (self.btc_trend == "DOWN" and
                symbol in cfg.SHORT_SYMBOLS and
                hour in cfg.SESSION_SHORT_HOURS):
            return "SHORT", ""

        # LONG
        if (self.btc_trend == "UP" and
                symbol in cfg.LONG_SYMBOLS and
                hour in cfg.SESSION_LONG_HOURS):
            return "LONG", ""

        # Блокировка — определяем причину
        if self.btc_trend == "DOWN":
            if symbol not in cfg.SHORT_SYMBOLS:
                return None, "short_sym_blocked"
            return None, f"short_bad_hour_{hour}utc"
        if self.btc_trend == "UP":
            if symbol not in cfg.LONG_SYMBOLS:
                return None, "long_sym_blocked"
            return None, f"long_bad_hour_{hour}utc"
        return None, "btc_mismatch"

    async def on_candle(self, symbol, cd):
        st = self.states.get(symbol)
        if not st: return
        c = Candle(ts=cd["ts"],o=cd["o"],h=cd["h"],l=cd["l"],c=cd["c"],v=cd["v"])

        # BTC update
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
                    r = (self._btc_prices[-1]-self._btc_prices[-4])/self._btc_prices[-4]*100
                    p = (self._btc_prices[-4]-self._btc_prices[-7])/self._btc_prices[-7]*100
                    if p > cfg.BTC_VELOCITY_MIN and r < p*cfg.BTC_VELOCITY_DECAY:
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
                t_act, t_dis = get_trailing(pos.symbol)
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
        if sym_candle - self._last_trade_candle[symbol] < cfg.COOLDOWN_CANDLES:
            self.block_reasons["cooldown"] += 1; return

        # Объём
        vol_r = c.v/st.avg_vol if st.avg_vol > 0 else 0
        if vol_r < cfg.VOL_MIN:
            self.block_reasons["vol_low"] += 1; return
        if vol_r >= cfg.VOL_MAX:
            self.block_reasons["vol_high"] += 1; return

        # Упрощённый фильтр входа
        side, block = self._check_entry(symbol)
        if side is None:
            self.block_reasons[block] = self.block_reasons.get(block,0)+1
            return

        # ВХОД
        hour = current_hour_utc()
        price = st.last_price if st.last_price > 0 else c.c
        self.signals += 1
        if side=="LONG": self.long_count += 1
        else: self.short_count += 1
        self._last_trade_candle[symbol] = sym_candle
        self._daily_trades += 1

        pos = Position(
            symbol=symbol, entry_price=price, entry_candle=sym_candle,
            side=side, entry_vol=round(vol_r,2), entry_hour=hour
        )
        pos.btc_regime = self.btc_trend
        self.open.append(pos)

        with open(cfg.CSV_SIGNALS, "a", newline="") as f:
            csv.writer(f).writerow([
                int(time.time()*1000), symbol, side, price,
                round(vol_r,2), self.btc_trend, hour
            ])
        if cfg.LOG_TO_CONSOLE:
            t_act, _ = get_trailing(symbol)
            sc = "\033[32m" if side=="LONG" else "\033[31m"
            print(f"  {sc}▶ {side} {symbol} @ {price:.4f} "
                  f"vol={vol_r:.1f}x BTC={self.btc_trend} "
                  f"{hour:02d}UTC trail={t_act}%\033[0m")

    # orderbook и trade — оставляем для обновления стакана
    async def on_orderbook(self, symbol: str, ob_type: str, data: dict):
        st = self.states.get(symbol)
        if not st: return
        if ob_type == "snapshot": st.book.apply_snapshot(data)
        else:                     st.book.apply_delta(data)

    async def on_trade(self, symbol, trade):
        st = self.states.get(symbol)
        if not st: return
        p = float(trade.get("p", 0))
        if p > 0: st.last_price = p
        s = trade.get("S",""); sz = float(trade.get("v", 0))
        if s == "Buy":  st.tick_buy_vol += sz
        elif s == "Sell": st.tick_sell_vol += sz

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
                pos.leverage, held, pos.entry_vol,
                round(pos.max_pnl,4), reason,
                pos.btc_regime, pos.entry_hour
            ])
        if cfg.LOG_TO_CONSOLE:
            col = "\033[32m" if pos.pnl_usdt>=0 else "\033[31m"
            fee = pos.size_usdt * pos.leverage * comm / 100
            print(f"  {col}◀ {pos.side} {pos.symbol} {pos.pnl_pct:+.3f}% "
                  f"${pos.pnl_usdt:+.2f} (fee:${fee:.2f}) "
                  f"held={held}×5m peak={pos.max_pnl:.3f}% "
                  f"[{reason}] {pos.entry_hour:02d}UTC\033[0m")

    def snapshot(self):
        hour = current_hour_utc()
        result = []
        for s in cfg.SYMBOLS:
            st = self.states[s]
            vol = round(st._vols[-1]/st.avg_vol,1) if st.avg_vol>0 and st._vols else 0
            side, _ = self._check_entry(s)
            if side:   session = f"{side}✓ {hour:02d}UTC"
            else:      session = f"pause {hour:02d}UTC"
            result.append({
                "symbol":s, "density":round(st.density,4),
                "delta":round(st.delta_ratio,4), "price":st.last_price,
                "vol":vol, "ready":st.ready, "candles":st.candle_count,
                "imbalance":0, "velocity":0, "session":session
            })
        return result

    def stats(self):
        cl = self.closed; reasons = defaultdict(int)
        for t in cl: reasons[t.exit_reason] += 1
        base = {
            "trades":0,"wr":0,"pnl":0,"avg":0,"best":0,"worst":0,
            "open":len(self.open),"lev":self.current_leverage,
            "blocked":0,"paused":False,"pause_count":0,
            "longs":self.long_count,"shorts":self.short_count,
            "btc_up":self.btc_up,"btc_trend":self.btc_trend,
            "btc_macro_ok":self.btc_macro_ok,"btc_macro_dir":self.btc_macro_dir,
            "daily_trades":self._daily_trades,
            "block_reasons":dict(self.block_reasons),
            "exit_reasons":dict(reasons),
            "tightened":False,"loss_streak":self._consecutive_losses
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
