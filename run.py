#!/usr/bin/env python3
"""Wolf Matrix — Simple Session Dash Loop"""
from __future__ import annotations
import argparse, asyncio, os, signal, sys, time
import config as cfg
from engine import WolfEngine

RST="\033[0m"; B="\033[1m"; D="\033[2m"
G="\033[32m"; R="\033[31m"; Y="\033[33m"; C="\033[36m"

def cls(): os.system("cls" if os.name=="nt" else "clear")

def banner(mode):
    e=cfg.POSITION_SIZE_USDT*cfg.LEVERAGE
    print(f"""
{C}{B}╔═══════════════════════════════════════════════════╗
║  WOLF MATRIX v13 — SIMPLE SESSION ENGINE          ║
║  Pure Momentum Engine (Hours + BTC Trend + Vol)   ║
╚═══════════════════════════════════════════════════╝{RST}
  {mode} │ {len(cfg.SYMBOLS)} symbols │ {cfg.KLINE_INTERVAL}min │ {Y}{cfg.LEVERAGE}x{RST} ${e:.0f}
  LONG:  {cfg.LONG_SYMBOLS}  │ SHORT: {cfg.SHORT_SYMBOLS}
  Vol Filter: {cfg.VOL_MIN}x - {cfg.VOL_MAX}x │ SL: {cfg.STOP_LOSS_PCT}% │ Hold Max: {cfg.MAX_HOLD_CANDLES} candles
""")

def render(eng: WolfEngine):
    sn = eng.snapshot(); eq = eng.stats()
    el = time.monotonic() - eng.t0
    ready = [s for s in sn if s["ready"]]
    warm = [s for s in sn if not s["ready"]]
    cls()
    
    trend = eq.get("btc_trend","WEAK")
    ba = f"{G}▲{RST}" if trend == "UP" else (f"{R}▼{RST}" if trend == "DOWN" else f"{Y}~{RST}")
    pc = G if eq["pnl"] >= 0 else R
    
    print(f"{B}WOLF v13 PRO{RST} │ BTC {ba} {trend} │ {Y}{cfg.LEVERAGE}x{RST} │ PnL: {pc}${eq['pnl']:+.2f}{RST} │ WR: {eq['wr']:.0f}% │ Open: {eq['open']}")
    print(f"{D}{'─'*74}{RST}")
    if eq["trades"] > 0:
        print(f"  Trades: {eq['trades']} │ Avg: {pc}${eq['avg']:+.2f}{RST} │ Best: {G}{eq['best']:+.2f}%{RST} │ Worst: {R}{eq['worst']:+.2f}%{RST}")
        exits = eq.get("exit_reasons",{})
        if exits: print(f"  {D}Exits: {dict(exits)}{RST}")
        blk = eq.get("block_reasons",{})
        if blk:   print(f"  {D}Blocked: {dict(blk)}{RST}")
        print(f"{D}{'─'*74}{RST}")

    n = min(cfg.CONSOLE_TOP_N, len(ready))
    if n == 0:
        wp = warm[0]["candles"]/cfg.WARMUP_CANDLES*100 if warm else 0
        print(f"  {Y}Warming State: {wp:.0f}%{RST}")
    else:
        print(f"  {'Symbol':<10} {'Price':<12} {'Volume':<8} {'Session Status':<15}")
        for it in ready[:n]:
            s = it["symbol"].replace("USDT","")
            v = it["vol"]
            vc = f"{Y}{v:>5.1f}x{RST}" if v >= cfg.VOL_MIN else f"{D}{v:>5.1f}x{RST}"
            
            sig = f"  {D}Standby{RST}"
            for pos in eng.open:
                if pos.symbol == it["symbol"]:
                    pnl = (it["price"] - pos.entry_price) / pos.entry_price * 100 if pos.side == "LONG" else (pos.entry_price - it["price"]) / pos.entry_price * 100
                    sig = f"  {G if pnl>=0 else R}[{pos.side} {pnl:+.2f}%]{RST}"

            print(f"  {s:<10} {it['price']:<12.4f} {vc} {it['session']:<15} {sig}")

    if warm:
        print(f"\n  {D}Warming nodes: {len(warm)} ({warm[0]['candles']}/{cfg.WARMUP_CANDLES}){RST}")
    print(f"  {D}Ctrl+C → Safety Shutdown & Dump Json{RST}")

async def dash_loop(eng, iv=2.0):
    while True:
        try:
            if cfg.LOG_TO_CONSOLE: render(eng)
            await asyncio.sleep(iv)
        except asyncio.CancelledError: break

async def run_live(eng):
    from feed import BybitFeed, HAS_WS
    if not HAS_WS: print(f"{R}pip install websockets{RST}"); return
    syms = list(cfg.SYMBOLS)
    if cfg.BTC_SYMBOL not in syms: syms.append(cfg.BTC_SYMBOL)
    feed = BybitFeed(syms, on_candle_close=eng.on_candle, on_trade=eng.on_trade, on_orderbook=eng.on_orderbook)
    d = asyncio.create_task(dash_loop(eng, 3.0))
    f = asyncio.create_task(feed.start())
    try: await asyncio.gather(f, d)
    except asyncio.CancelledError: 
        await feed.stop()
        d.cancel()

async def run_offline(eng):
    from feed import OfflineFeed
    feed = OfflineFeed(cfg.SYMBOLS, on_candle_close=eng.on_candle, on_trade=eng.on_trade, on_orderbook=eng.on_orderbook, candles_per_symbol=300, tick_delay=0.001)
    d = asyncio.create_task(dash_loop(eng, 0.3))
    await feed.start()
    d.cancel()
    if cfg.LOG_TO_CONSOLE: render(eng)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--port", type=int, default=8888, help="Dashboard port")
    args = ap.parse_args()
    banner("OFFLINE" if args.offline else "LIVE")
    eng = WolfEngine()

    try:
        from web import start_dashboard
        start_dashboard(eng, args.port)
    except: pass

    def shut(*_):
        print(f"\n{C}Saving matrix state…{RST}"); eng.save()
        eq = eng.stats(); pc = G if eq["pnl"]>=0 else R
        print(f"{G}✓{RST} Session closed: {eq['trades']} trades. Final Net PnL: {pc}${eq['pnl']:+.2f}{RST}")
        sys.exit(0)

    signal.signal(signal.SIGINT, shut)
    if hasattr(signal,"SIGTERM"): signal.signal(signal.SIGTERM, shut)

    loop = asyncio.new_event_loop()
    try:
        if args.offline: loop.run_until_complete(run_offline(eng))
        else:            loop.run_until_complete(run_live(eng))
    except SystemExit: pass
    finally:
        eng.save()
        loop.close()

if __name__ == "__main__":
    main()
