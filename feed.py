"""
Matrix Market Scanner — Bybit WebSocket Feed
Публичные данные: kline + trades. Без API ключей.

Подписки:
  • kline.{interval}.{symbol}  — OHLCV свечи
  • publicTrade.{symbol}       — сделки (для дельты buy/sell)
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Callable, Optional

import config as cfg

# websockets — единственная внешняя зависимость для WS
try:
    import websockets
    import websockets.client
    HAS_WS = True
except ImportError:
    HAS_WS = False


class BybitFeed:
    """
    Асинхронный клиент Bybit public WebSocket.
    Вызывает коллбэки при закрытии свечи и при каждой сделке.
    """

    def __init__(
        self,
        symbols: list[str],
        on_candle_close: Optional[Callable] = None,
        on_trade: Optional[Callable] = None,
    ) -> None:
        self.symbols = symbols
        self.on_candle_close = on_candle_close  # async (symbol, candle_dict)
        self.on_trade = on_trade                # async (symbol, trade_dict)

        self._ws = None
        self._running = False
        self._last_pong: float = 0.0

        # Трекинг: последний confirm-timestamp по символу
        # чтобы не дублировать свечи
        self._last_candle_ts: dict[str, int] = {}

    async def start(self) -> None:
        """Запуск с автоматическим реконнектом."""
        self._running = True
        while self._running:
            try:
                await self._connect_and_listen()
            except Exception as e:
                if not self._running:
                    break
                print(f"[FEED] Connection error: {e}, reconnect in {cfg.WS_RECONNECT_SEC}s")
                await asyncio.sleep(cfg.WS_RECONNECT_SEC)

    async def stop(self) -> None:
        self._running = False
        if self._ws:
            await self._ws.close()

    async def _connect_and_listen(self) -> None:
        async with websockets.connect(       # type: ignore
            cfg.WS_URL,
            ping_interval=cfg.WS_PING_SEC,
            ping_timeout=cfg.WS_PING_SEC * 2,
            close_timeout=5,
        ) as ws:
            self._ws = ws
            print(f"[FEED] Connected to {cfg.WS_URL}")

            # Подписки пачками по 10 (лимит Bybit)
            await self._subscribe(ws)

            async for msg in ws:
                if not self._running:
                    break
                await self._handle_message(msg)

    async def _subscribe(self, ws) -> None:
        """Подписка на kline и trades для всех символов."""
        # kline подписки
        kline_args = [f"kline.{cfg.KLINE_INTERVAL}.{s}" for s in self.symbols]
        # trade подписки
        trade_args = [f"publicTrade.{s}" for s in self.symbols]

        all_args = kline_args + trade_args

        # Bybit принимает до 10 аргументов за раз
        batch_size = 10
        for i in range(0, len(all_args), batch_size):
            batch = all_args[i: i + batch_size]
            msg = json.dumps({
                "op": "subscribe",
                "args": batch,
            })
            await ws.send(msg)
            # Маленькая пауза между пачками
            await asyncio.sleep(0.1)

        print(f"[FEED] Subscribed: {len(self.symbols)} symbols × (kline + trades)")

    async def _handle_message(self, raw: str) -> None:
        """Роутер входящих сообщений."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return

        topic = data.get("topic", "")

        if topic.startswith("kline."):
            await self._on_kline(data)
        elif topic.startswith("publicTrade."):
            await self._on_public_trade(data)

    async def _on_kline(self, data: dict) -> None:
        """
        Обработка kline. Вызываем on_candle_close только когда свеча confirm=true.
        """
        topic = data.get("topic", "")
        items = data.get("data", [])
        # topic = "kline.1.ETHUSDT"
        parts = topic.split(".")
        if len(parts) < 3:
            return
        symbol = parts[2]

        for item in items:
            confirm = item.get("confirm", False)
            if not confirm:
                continue  # свеча ещё открыта

            ts = int(item.get("start", 0))

            # Дедупликация
            if self._last_candle_ts.get(symbol) == ts:
                continue
            self._last_candle_ts[symbol] = ts

            candle = {
                "ts": ts,
                "o": float(item.get("open", 0)),
                "h": float(item.get("high", 0)),
                "l": float(item.get("low", 0)),
                "c": float(item.get("close", 0)),
                "v": float(item.get("volume", 0)),
            }

            if self.on_candle_close:
                await self.on_candle_close(symbol, candle)

    async def _on_public_trade(self, data: dict) -> None:
        """
        Обработка потока сделок → агрегация buy/sell volume для дельты.
        """
        topic = data.get("topic", "")
        items = data.get("data", [])
        parts = topic.split(".")
        if len(parts) < 2:
            return
        symbol = parts[1]

        for trade in items:
            if self.on_trade:
                await self.on_trade(symbol, trade)


# =====================================================================
#  Offline Feed — для тестирования без интернета
# =====================================================================

class OfflineFeed:
    """
    Имитатор фида: читает CSV с историческими свечами
    или генерирует синтетические данные для тестирования.
    """

    def __init__(
        self,
        symbols: list[str],
        on_candle_close: Optional[Callable] = None,
        on_trade: Optional[Callable] = None,
        candles_per_symbol: int = 200,
        tick_delay: float = 0.01,
    ) -> None:
        self.symbols = symbols
        self.on_candle_close = on_candle_close
        self.on_trade = on_trade
        self.candles_per_symbol = candles_per_symbol
        self.tick_delay = tick_delay
        self._running = False

    async def start(self) -> None:
        """Генерирует синтетические свечи + delta для тестирования Wolf."""
        import random
        self._running = True

        prices = {}
        for s in self.symbols:
            prices[s] = random.uniform(0.5, 3000.0)

        print(f"[OFFLINE] Generating {self.candles_per_symbol} candles × {len(self.symbols)} symbols")
        ts = int(time.time() * 1000) - self.candles_per_symbol * 60000

        for i in range(self.candles_per_symbol):
            if not self._running:
                break

            for s in self.symbols:
                p = prices[s]
                change_pct = random.gauss(0.0001, 0.003)
                p_new = p * (1 + change_pct)

                o = p; c = p_new
                h = max(o, c) * (1 + random.uniform(0, 0.002))
                l = min(o, c) * (1 - random.uniform(0, 0.002))
                v = random.uniform(100, 10000)

                # Wolf: имитация buy/sell volume
                # Зелёная свеча → больше buy, красная → больше sell
                # Иногда сильный дисбаланс (имитация wolf-сигнала)
                if c > o:
                    buy_ratio = random.uniform(0.52, 0.85)
                else:
                    buy_ratio = random.uniform(0.15, 0.48)
                buy_vol = v * buy_ratio
                sell_vol = v * (1 - buy_ratio)

                # Имитация trade stream → накапливает delta в SymbolState
                if self.on_trade:
                    await self.on_trade(s, {"S": "Buy", "v": str(buy_vol)})
                    await self.on_trade(s, {"S": "Sell", "v": str(sell_vol)})

                candle = {
                    "ts": ts + i * 60000,
                    "o": round(o, 6), "h": round(h, 6),
                    "l": round(l, 6), "c": round(c, 6),
                    "v": round(v, 2),
                }
                prices[s] = p_new

                if self.on_candle_close:
                    await self.on_candle_close(s, candle)

            if self.tick_delay > 0:
                await asyncio.sleep(self.tick_delay)

        print(f"[OFFLINE] Done. {self.candles_per_symbol} candles generated.")

    async def stop(self) -> None:
        self._running = False
