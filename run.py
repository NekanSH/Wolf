#!/usr/bin/env python3
"""Wolf Matrix — python run.py [--offline]"""
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
║  WOLF MATRIX v4.1 — Momentum Filter Edition         ║
║  LONG │ δ50-80% │ BTC UP+momentum │ ρ≥75% │ 10x   ║
╚═══════════════════════════════════════════════════╝{RST}
  {mode} │ {len(cfg.SYMBOLS)} symbols │ {cfg.KLINE_INTERVAL}min │ {Y}{cfg.LEVERAGE}x{RST} ${e:.0f}
  Entry: δ {cfg.DELTA_MIN:.0%}-{cfg.DELTA_MAX:.0%} + green + BTC▲+momentum + ρ≥{cfg.DENSITY_MIN:.0%}
  Vol:   {cfg.VOL_MIN}-{cfg.VOL_MAX}x │ Exit: TIMEOUT {cfg.MAX_HOLD_CANDLES}min
  Warmup: {cfg.WARMUP_CANDLES}min
""")

def render(eng: WolfEngine):
    sn = eng.snapshot(); eq = eng.stats()
    el = time.monotonic() - eng.t0
    ready = [s for s in sn if s["ready"]]
    warm = [s for s in sn if not s["ready"]]
    # Сортировка: самый сильный delta наверху
    ready.sort(key=lambda x: x["delta"], reverse=True)
    cls()
    trend = eq.get("btc_trend","?")
    if trend == "UP": ba = f"{G}▲ LONG{RST}"
    elif trend == "WEAK": ba = f"{Y}▲ WEAK{RST}"
    else: ba = f"{R}▼ WAIT{RST}"
    pc = G if eq["pnl"] >= 0 else R
    longs = eq.get("longs",0)
    blk = eq.get("block_reasons",{})
    blk_str = " ".join(f"{k}:{v}" for k,v in blk.items()) if blk else ""
    print(f"{B}WOLF v4.1{RST} │ BTC{ba} │ {Y}{cfg.LEVERAGE}x{RST} │ "
          f"PnL:{pc}${eq['pnl']:+.2f}{RST} │ "
          f"{eq['trades']}t WR:{eq['wr']:.0f}% │ "
          f"{G}L:{longs}{RST} │ "
          f"open:{eq['open']} │ "
          f"{R+'⏸'+RST+' │ ' if eq.get('paused') else ''}"
          f"{D}{el:.0f}s{RST}")
    print(f"{D}{'─'*74}{RST}")
    if eq["trades"] > 0:
        pause_info = f" │ pauses:{eq.get('pause_count',0)}" if eq.get('pause_count',0) else ""
        print(f"  avg:${eq['avg']:+.2f} │ "
              f"best:{G}{eq['best']:+.2f}%{RST} worst:{R}{eq['worst']:+.2f}%{RST}{pause_info}")
        exits = eq.get("exit_reasons",{})
        if exits:
            ex_str = " ".join(f"{k}:{v}" for k,v in exits.items())
            print(f"  {D}exits: {ex_str}{RST}")
        if eq.get("tightened"):
            print(f"  {Y}⚠ TIGHTENED (streak:{eq.get('loss_streak',0)}){RST}")
        if blk_str: print(f"  {D}blocked: {blk_str}{RST}")
        print(f"{D}{'─'*74}{RST}")

    n = min(cfg.CONSOLE_TOP_N, len(ready))
    if n == 0:
        wp = warm[0]["candles"]/cfg.WARMUP_CANDLES*100 if warm else 0
        print(f"  {Y}Warmup {wp:.0f}%{RST}")
    else:
        print(f"  {'Symbol':<8} {'δ buy':>6} {'ρ':>5} {'vol':>5}  {'Price':>10}  Status")
        for it in ready[:n]:
            s = it["symbol"].replace("USDT","")
            d = it["delta"]; dens = it["density"]
            # Delta coloring
            if d >= cfg.DELTA_MIN and d < cfg.DELTA_MAX:
                dc = f"{G}{d:>+5.0%}{RST}"
            else:
                dc = f"{D}{d:>+5.0%}{RST}"

            if dens >= 0.60: db = f"{G}{dens:>4.0%}{RST}"
            elif dens <= 0.40: db = f"{R}{dens:>4.0%}{RST}"
            else: db = f"{D}{dens:>4.0%}{RST}"

            # Vol
            v = it["vol"]
            vc = f"{Y}{v:>4.1f}x{RST}" if v >= 1.2 else f"{D}{v:>4.1f}x{RST}"

            sig = ""
            if (eng.btc_up and d >= cfg.DELTA_MIN and d < cfg.DELTA_MAX):
                sig = f"{G}◄ WOLF{RST}"

            for pos in eng.open:
                if pos.symbol == it["symbol"]:
                    pnl = (it["price"] - pos.entry_price) / pos.entry_price * 100
                    c = G if pnl >= 0 else R
                    sig = f"{c}[LONG {pnl:+.2f}%]{RST}"

            print(f"  {s:<8} {dc} {db} {vc}  {it['price']:>10.4f}  {sig}")

    if warm:
        print(f"  {D}warming: {len(warm)} ({warm[0]['candles']}/{cfg.WARMUP_CANDLES}){RST}")
    print(f"  {D}Ctrl+C → save{RST}")

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
    feed = BybitFeed(syms, on_candle_close=eng.on_candle, on_trade=eng.on_trade)
    d = asyncio.create_task(dash_loop(eng, 3.0))
    f = asyncio.create_task(feed.start())
    try: await asyncio.gather(f, d)
    except asyncio.CancelledError: await feed.stop(); d.cancel()

async def run_offline(eng):
    from feed import OfflineFeed
    feed = OfflineFeed(cfg.SYMBOLS, on_candle_close=eng.on_candle,
                       on_trade=eng.on_trade,
                       candles_per_symbol=300, tick_delay=0.001)
    d = asyncio.create_task(dash_loop(eng, 0.3))
    await feed.start(); d.cancel()
    if cfg.LOG_TO_CONSOLE: render(eng)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--port", type=int, default=8888, help="Dashboard port")
    args = ap.parse_args()
    banner("OFFLINE" if args.offline else "LIVE")
    eng = WolfEngine()

    # Start web dashboard
    from web import start_dashboard
    start_dashboard(eng, args.port)

    def shut(*_):
        print(f"\n{C}Saving…{RST}"); eng.save()
        eq = eng.stats(); pc = G if eq["pnl"]>=0 else R
        print(f"{G}✓{RST} {eq['trades']}t {pc}${eq['pnl']:+.2f}{RST}")
        sys.exit(0)

    signal.signal(signal.SIGINT, shut)
    if hasattr(signal,"SIGTERM"): signal.signal(signal.SIGTERM, shut)

    loop = asyncio.new_event_loop()
    try:
        if args.offline: loop.run_until_complete(run_offline(eng))
        else: loop.run_until_complete(run_live(eng))
    except SystemExit: pass
    finally: eng.save(); loop.close()

    eq = eng.stats()
    if eq["trades"] > 0:
        pc = G if eq["pnl"]>=0 else R
        print(f"\n{B}═══ WOLF RESULT ═══{RST}")
        print(f"  {eq['trades']}t │ {pc}${eq['pnl']:+.2f}{RST} │ WR:{eq['wr']:.0f}%")
        print(f"  blocked:{eq['blocked']}\n")

if __name__ == "__main__": main()
