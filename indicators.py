"""
Wolf Matrix — Indicators
Те же 24 индикатора + трекинг delta из trade stream по свечам.
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from typing import Optional
import config as cfg

@dataclass
class Candle:
    ts: int; o: float; h: float; l: float; c: float; v: float
    bv: float = 0.0; sv: float = 0.0

class EMA:
    __slots__ = ("period","k","value","_count")
    def __init__(self, p):
        self.period=p; self.k=2.0/(p+1); self.value=0.0; self._count=0
    def update(self, price):
        if self._count==0: self.value=price
        else: self.value=price*self.k+self.value*(1-self.k)
        self._count+=1; return self.value
    @property
    def ready(self): return self._count>=self.period

class RSI:
    __slots__ = ("period","avg_gain","avg_loss","_prev","_count")
    def __init__(self, p=14):
        self.period=p; self.avg_gain=0.0; self.avg_loss=0.0; self._prev=0.0; self._count=0
    def update(self, price):
        if self._count==0: self._prev=price; self._count+=1; return 50.0
        d=price-self._prev; self._prev=price; g=max(d,0); l=max(-d,0); self._count+=1
        if self._count<=self.period+1:
            self.avg_gain+=g/self.period; self.avg_loss+=l/self.period; return 50.0
        self.avg_gain=(self.avg_gain*(self.period-1)+g)/self.period
        self.avg_loss=(self.avg_loss*(self.period-1)+l)/self.period
        if self.avg_loss==0: return 100.0
        return 100-100/(1+self.avg_gain/self.avg_loss)
    @property
    def ready(self): return self._count>self.period+1

class RollingVWAP:
    __slots__ = ("period","_pv","_vol")
    def __init__(self, p=20):
        self.period=p; self._pv=deque(maxlen=p); self._vol=deque(maxlen=p)
    def update(self, tp, vol):
        self._pv.append(tp*vol); self._vol.append(vol)
        s=sum(self._vol); return sum(self._pv)/s if s>0 else tp

NUM_FEATURES = 24

class SymbolState:
    def __init__(self, symbol):
        self.symbol = symbol
        self.ema_fast = EMA(cfg.EMA_FAST)
        self.ema_mid = EMA(cfg.EMA_MID)
        self.ema_slow = EMA(cfg.EMA_SLOW)
        self._pef = 0.0; self._pem = 0.0
        self.rsi = RSI(cfg.RSI_PERIOD)
        self.vwap = RollingVWAP(cfg.VWAP_PERIOD)
        self._vols: deque = deque(maxlen=cfg.VOLUME_AVG_PERIOD)
        self._closes: deque = deque(maxlen=max(cfg.MOMENTUM_LOOKBACK+2, cfg.HIGH_LOW_LOOKBACK+1))
        self._highs: deque = deque(maxlen=cfg.HIGH_LOW_LOOKBACK)
        self._lows: deque = deque(maxlen=cfg.HIGH_LOW_LOOKBACK)
        self._cg = 0
        self._prev: Optional[Candle] = None
        self.candle_count = 0
        self.last_price = 0.0

        # ── WOLF: delta из trade stream ──
        self.tick_buy_vol = 0.0   # заполняется из on_trade
        self.tick_sell_vol = 0.0

        # ── Результаты ──
        self.density = 0.0
        self.delta_ratio = 0.0    # (buy-sell)/(buy+sell) текущей свечи
        self.candle_green = False  # close > open
        self.vol_above_avg = False # объём выше среднего
        self.avg_vol = 0.0

    @property
    def ready(self):
        return self.candle_count >= cfg.WARMUP_CANDLES

    def on_candle(self, c: Candle, btc_up=True):
        self.candle_count += 1
        self.last_price = c.c

        # Забираем delta из trade stream
        c.bv = self.tick_buy_vol
        c.sv = self.tick_sell_vol
        self.tick_buy_vol = 0.0
        self.tick_sell_vol = 0.0

        # WOLF: delta ratio
        total = c.bv + c.sv
        self.delta_ratio = (c.bv - c.sv) / total if total > 0 else 0.0
        self.candle_green = c.c > c.o

        # Индикаторы
        pef = self.ema_fast.value; pem = self.ema_mid.value
        ef = self.ema_fast.update(c.c)
        em = self.ema_mid.update(c.c)
        es = self.ema_slow.update(c.c)
        self._pef = pef; self._pem = pem

        rsi = self.rsi.update(c.c)
        tp = (c.h + c.l + c.c) / 3
        vw = self.vwap.update(tp, c.v) if c.v > 0 else tp

        self._vols.append(c.v)
        self._closes.append(c.c)
        self._highs.append(c.h)
        self._lows.append(c.l)

        self.avg_vol = sum(self._vols) / len(self._vols) if self._vols else 1
        self.vol_above_avg = c.v > self.avg_vol * cfg.DELTA_VOLUME_MIN_MULT

        d = c.bv - c.sv
        dr = abs(d) / total if total > 0 else 0

        if c.c > c.o: self._cg = max(self._cg + 1, 1)
        elif c.c < c.o: self._cg = min(self._cg - 1, -1)
        else: self._cg = 0

        rng = c.h - c.l; body = abs(c.c - c.o)
        br = body / rng if rng > 0 else 0

        mu = ma = False
        if len(self._closes) > cfg.MOMENTUM_LOOKBACK:
            oc = self._closes[-(cfg.MOMENTUM_LOOKBACK + 1)]; mu = c.c > oc
            if len(self._closes) > cfg.MOMENTUM_LOOKBACK + 1:
                oc2 = self._closes[-(cfg.MOMENTUM_LOOKBACK + 2)]
                ma = (c.c - oc) > (oc - oc2)

        nh = nnl = True
        if len(self._highs) >= 2: nh = c.h > max(list(self._highs)[:-1])
        if len(self._lows) >= 2: nnl = c.l >= min(list(self._lows)[:-1])

        hl = hh = False
        if self._prev: hl = c.l > self._prev.l; hh = c.h > self._prev.h

        # Бинаризация → density (фильтр, не сигнал)
        f = [0] * NUM_FEATURES
        f[0]=int(c.c>ef); f[1]=int(c.c>em); f[2]=int(c.c>es)
        f[3]=int(ef>em); f[4]=int(em>es)
        f[5]=int(ef>pef) if self.candle_count>1 else 0
        f[6]=int(em>pem) if self.candle_count>1 else 0
        f[7]=int(rsi>50); f[8]=int(rsi<75); f[9]=int(rsi>25)
        f[10]=int(c.v>self.avg_vol*1.5)
        f[11]=int(d>0); f[12]=int(dr>0.3)
        f[13]=int(c.c>vw); f[14]=int(c.c>c.o); f[15]=int(br>0.5)
        f[16]=int(mu); f[17]=int(ma); f[18]=int(nh); f[19]=int(nnl)
        f[20]=int(self._cg>=2); f[21]=int(hl); f[22]=int(hh)
        f[23]=int(btc_up) if cfg.BTC_TREND_WEIGHT else 1

        self.density = sum(f) / NUM_FEATURES
        self._prev = c
        return self.delta_ratio
