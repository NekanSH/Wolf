"""
Wolf Matrix — Bybit WebSocket Feed
Подписки: kline + publicTrade + orderbook.50
"""
from __future__ import annotations
import asyncio, json, time
from typing import Callable, Optional
import config as cfg

try:
    import websockets
    import websockets.client
    HAS_WS = True
except ImportError:
    HAS_WS = False


class BybitFeed:
    def __init__(
        self,
        symbols: list[str],
        on_candle_close: Optional[Callable] = None,
        on_trade:        Optional[Callable] = None,
        on_orderbook:    Optional[Callable] = None,   # НОВОЕ
    ) -> None:
        self.symbols       = symbols
        self.on_candle_close = on_candle_close
        self.on_trade        = on_trade
        self.on_orderbook    = on_orderbook            # НОВОЕ

        self._ws      = None
        self._running = False
        self._last_candle_ts: dict[str, int] = {}

    async def start(self) -> None:
        self._running = True
        while self._running:
            try:
                await self._connect_and_listen()
            except Exception as e:
                if not self._running: break
                print(f"[FEED] Error: {e}, reconnect in {cfg.WS_RECONNECT_SEC}s")
                await asyncio.sleep(cfg.WS_RECONNECT_SEC)

    async def stop(self) -> None:
        self._running = False
        if self._ws:
            await self._ws.close()

    async def _connect_and_listen(self) -> None:
        async with websockets.connect(
            cfg.WS_URL,
            ping_interval=cfg.WS_PING_SEC,
            ping_timeout=cfg.WS_PING_SEC * 2,
            close_timeout=5,
        ) as ws:
            self._ws = ws
            print(f"[FEED] Connected to {cfg.WS_URL}")
            await self._subscribe(ws)
            async for msg in ws:
                if not self._running: break
                await self._handle_message(msg)

    async def _subscribe(self, ws) -> None:
        kline_args = [f"kline.{cfg.KLINE_INTERVAL}.{s}" for s in self.symbols]
        trade_args = [f"publicTrade.{s}"               for s in self.symbols]
        book_args  = [f"orderbook.50.{s}"              for s in self.symbols]  # НОВОЕ

        all_args = kline_args + trade_args + book_args
        batch_size = 10
        for i in range(0, len(all_args), batch_size):
            batch = all_args[i:i+batch_size]
            await ws.send(json.dumps({"op": "subscribe", "args": batch}))
            await asyncio.sleep(0.1)

        print(f"[FEED] Subscribed: {len(self.symbols)} symbols × (kline + trades + orderbook)")

    async def _handle_message(self, raw: str) -> None:
        try: data = json.loads(raw)
        except: return
        topic = data.get("topic", "")
        if   topic.startswith("kline."):       await self._on_kline(data)
        elif topic.startswith("publicTrade."): await self._on_public_trade(data)
        elif topic.startswith("orderbook."):   await self._on_orderbook(data)   # НОВОЕ

    async def _on_kline(self, data: dict) -> None:
        topic  = data.get("topic", "")
        parts  = topic.split(".")
        if len(parts) < 3: return
        symbol = parts[2]
        for item in data.get("data", []):
            if not item.get("confirm", False): continue
            ts = int(item.get("start", 0))
            if self._last_candle_ts.get(symbol) == ts: continue
            self._last_candle_ts[symbol] = ts
            candle = {
                "ts": ts,
                "o": float(item.get("open",   0)),
                "h": float(item.get("high",   0)),
                "l": float(item.get("low",    0)),
                "c": float(item.get("close",  0)),
                "v": float(item.get("volume", 0)),
            }
            if self.on_candle_close:
                await self.on_candle_close(symbol, candle)

    async def _on_public_trade(self, data: dict) -> None:
        topic  = data.get("topic", "")
        parts  = topic.split(".")
        if len(parts) < 2: return
        symbol = parts[1]
        for trade in data.get("data", []):
            if self.on_trade:
                await self.on_trade(symbol, trade)

    async def _on_orderbook(self, data: dict) -> None:
        """
        Bybit orderbook stream:
          type='snapshot' → полный снепшот
          type='delta'    → инкрементальные изменения
        """
        topic  = data.get("topic", "")
        parts  = topic.split(".")
        if len(parts) < 3: return
        symbol  = parts[2]
        ob_type = data.get("type", "delta")
        ob_data = data.get("data", {})

        if self.on_orderbook:
            await self.on_orderbook(symbol, ob_type, ob_data)


# ──────────────────────────────────────────────────────────────
#  OfflineFeed — для тестов без интернета
# ──────────────────────────────────────────────────────────────

class OfflineFeed:
    def __init__(
        self,
        symbols: list[str],
        on_candle_close: Optional[Callable] = None,
        on_trade:        Optional[Callable] = None,
        on_orderbook:    Optional[Callable] = None,
        candles_per_symbol: int   = 200,
        tick_delay:         float = 0.01,
    ) -> None:
        self.symbols         = symbols
        self.on_candle_close = on_candle_close
        self.on_trade        = on_trade
        self.on_orderbook    = on_orderbook
        self.candles_per_symbol = candles_per_symbol
        self.tick_delay      = tick_delay
        self._running        = False

    async def start(self) -> None:
        import random
        self._running = True
        prices = {s: random.uniform(0.5, 3000.0) for s in self.symbols}
        ts = int(time.time() * 1000) - self.candles_per_symbol * 300_000

        # Синтетический снепшот стакана на старте
        for s in self.symbols:
            if self.on_orderbook:
                p = prices[s]
                snap = {
                    "b": [[str(round(p - i*0.01, 4)), str(random.uniform(100, 1000))] for i in range(50)],
                    "a": [[str(round(p + i*0.01, 4)), str(random.uniform(100, 1000))] for i in range(50)],
                }
                await self.on_orderbook(s, "snapshot", snap)

        print(f"[OFFLINE] {self.candles_per_symbol} candles × {len(self.symbols)} symbols")

        for i in range(self.candles_per_symbol):
            if not self._running: break

            for s in self.symbols:
                p = prices[s]
                change = random.gauss(0.0001, 0.003)
                p_new  = p * (1 + change)
                o=p; c=p_new
                h=max(o,c)*(1+random.uniform(0,0.002))
                l=min(o,c)*(1-random.uniform(0,0.002))
                v=random.uniform(100, 10000)

                buy_ratio = random.uniform(0.52, 0.85) if c > o else random.uniform(0.15, 0.48)

                # Имитация сильного сигнала изредка
                if random.random() < 0.05:
                    buy_ratio = random.uniform(0.75, 0.95)

                buy_vol = v * buy_ratio; sell_vol = v * (1 - buy_ratio)

                # Тики с velocity
                for _ in range(random.randint(3, 8)):
                    if self.on_trade:
                        await self.on_trade(s, {"S": "Buy",  "v": str(buy_vol/5),  "p": str(p_new)})
                        await self.on_trade(s, {"S": "Sell", "v": str(sell_vol/5), "p": str(p_new)})

                # Orderbook delta
                if self.on_orderbook:
                    spread = p_new * 0.0001
                    delta = {
                        "b": [[str(round(p_new - spread, 4)), str(buy_vol)]],
                        "a": [[str(round(p_new + spread, 4)), str(sell_vol)]],
                    }
                    await self.on_orderbook(s, "delta", delta)

                candle = {
                    "ts": ts + i * 300_000,
                    "o": round(o,6), "h": round(h,6),
                    "l": round(l,6), "c": round(c,6), "v": round(v,2),
                }
                prices[s] = p_new
                if self.on_candle_close:
                    await self.on_candle_close(s, candle)

            if self.tick_delay > 0:
                await asyncio.sleep(self.tick_delay)

        print("[OFFLINE] Done.")

    async def stop(self) -> None:
        self._running = False
