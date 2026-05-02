"""
Wolf Matrix — AI Analyzer
═════════════════════════
Claude Haiku 4.5 анализирует каждый сигнал ПЕРЕД входом.
Стоимость: ~$0.27/месяц (20 сигналов/день × $0.009)

Обучен на 800+ реальных сделках:
  - STALE (мёртвые, 64%): delta слабый, нет продолжения
  - TIMEOUT/TRAILING (живые, 36%): реальный импульс

Отвечает одним словом: ENTER или SKIP
"""

import os
import json
import asyncio
import urllib.request
import urllib.error


HAIKU_MODEL = "claude-haiku-4-5-20251001"

# Системный промпт — обучен на наших данных
SYSTEM_PROMPT = """Ты фильтр входов для крипто-бота (BTC, ETH, SOL, XRP, SUI на Bybit).

Твоя задача: предсказать будет ли эта сделка прибыльной.

ПАТТЕРНЫ ИЗ 800+ РЕАЛЬНЫХ СДЕЛОК:

ПЛОХИЕ входы (64% всех — мёртвые, убыток):
- delta 0.40-0.65 без подтверждения объёмом → цена не идёт дальше
- vol < 1.0 → нет реального давления покупателей
- BTC WEAK + delta < 0.70 → сигнал слабый, импульс уже кончился
- SHORT в UP тренде → 0-15% WR
- Любая комбинация дающая peak < 0.10% за 20 мин → комиссия съедает всё

ХОРОШИЕ входы (36% — живые, прибыль 62-67% WR):
- delta ≥ 0.70 + vol ≥ 1.5 + BTC UP → сильный импульс, продолжение вероятно
- TRAILING_STRONG = 80% WR → лучший выход системы
- TIMEOUT = 62% WR → позиция шла самостоятельно
- delta зеркально для SHORT в DOWN тренде

ПРАВИЛО: если не уверен → SKIP. Лучше пропустить 10 хороших чем войти в 5 плохих.

Ответь ТОЛЬКО одним словом: ENTER или SKIP"""


async def analyze_signal(symbol: str, side: str, delta: float, density: float,
                          vol: float, btc_trend: str, btc_velocity: str) -> str:
    """
    Спрашивает Claude: входить или пропустить этот сигнал.
    
    Returns: "ENTER" или "SKIP"
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "ENTER"  # Если ключа нет — не блокируем систему

    # Формируем контекст сигнала
    user_msg = f"""Сигнал для оценки:
Symbol: {symbol}
Side: {side}
Delta: {delta:+.2f} ({'покупатели' if delta > 0 else 'продавцы'} {abs(delta)*100:.0f}% объёма)
Density (бычья среда): {density:.2f}
Vol ratio: {vol:.1f}x (относительно среднего)
BTC тренд: {btc_trend}
BTC momentum: {btc_velocity}

Входить или пропустить?"""

    payload = json.dumps({
        "model": HAIKU_MODEL,
        "max_tokens": 10,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_msg}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
    )

    try:
        loop = asyncio.get_event_loop()
        response_data = await loop.run_in_executor(None, _do_request, req)
        text = response_data.get("content", [{}])[0].get("text", "ENTER").strip().upper()
        return "ENTER" if "ENTER" in text else "SKIP"
    except Exception as e:
        # При любой ошибке API — не блокируем торговлю
        return "ENTER"


def _do_request(req):
    """Синхронный HTTP запрос (запускается в executor)."""
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


# Кэш решений — не спрашиваем Claude дважды для одинаковых условий
_decision_cache: dict[str, tuple[str, int]] = {}
_CACHE_TTL = 3  # свечи (15 мин на 5-мин)


def _cache_key(symbol, side, delta, vol, btc_trend):
    d = round(delta, 1)
    v = round(vol, 0)
    return f"{symbol}_{side}_{d}_{v}_{btc_trend}"


async def analyze_cached(symbol, side, delta, density, vol, btc_trend,
                          btc_velocity, current_candle):
    """Анализ с кэшированием — экономим API вызовы."""
    key = _cache_key(symbol, side, delta, vol, btc_trend)
    if key in _decision_cache:
        decision, cached_at = _decision_cache[key]
        if current_candle - cached_at < _CACHE_TTL:
            return decision

    decision = await analyze_signal(symbol, side, delta, density,
                                     vol, btc_trend, btc_velocity)
    _decision_cache[key] = (decision, current_candle)
    return decision
