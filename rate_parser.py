"""
Парсер курса Альфа-Банк RUB → USDT TRC-20 с BestChange.
Направление: отдаём рубли, получаем USDT (покупка — 1 USDT = X RUB).
Лучший курс = МИНИМУМ рублей за 1 USDT.

Стратегия: bestchange-api (официальные данные) → HTML-парсинг (fallback).
"""
import asyncio
import logging
import re
import aiohttp

logger = logging.getLogger(__name__)

# bestchange-api: from=52 (alfaclick/Альфа-Банк), to=10 (USDT TRC20)
DIR_FROM_ALFACLICK = 52
DIR_TO_USDT_TRC20 = 10

BESTCHANGE_URL = "https://www.bestchange.ru/alfaclick-to-tether-trc20.html"
RATE_PATTERN = re.compile(r"(\d{2,3}[.,]\d{2,4})\s*RUB[\s\S]{0,80}?(?:Альфа|alfabank|Банк)", re.I | re.DOTALL)
RATE_PATTERN_FALLBACK = re.compile(r"(\d{2,3}[.,]\d{2,4})\s*RUB", re.I)


def _get_connector():
    """HTTP-коннектор с прокси (для доступа к BestChange с сервера)."""
    from config import PROXY
    if PROXY:
        from aiohttp_socks import ProxyConnector
        return ProxyConnector.from_url(PROXY)
    return aiohttp.TCPConnector()


def _get_rate_via_api() -> float | None:
    """
    bestchange-api: загружает bm_cy.zip с BestChange.
    С прокси — bestchange-api может не поддерживать SOCKS5, тогда полагаемся на HTML.
    """
    try:
        from bestchange_api import BestChange
        from config import PROXY

        kwargs = {}
        if PROXY:
            kwargs["proxy"] = PROXY  # socks5://... или http://...
        api = BestChange(**kwargs)
        if api.is_error():
            logger.warning("Парсер API: ошибка загрузки данных — %s", api.is_error())
            return None

        rows = api.rates().filter(DIR_FROM_ALFACLICK, DIR_TO_USDT_TRC20)
        if not rows:
            logger.warning("Парсер API: нет курсов для направления 52→10")
            return None

        # rate_give = руб, rate_get = USDT. 1 USDT = rate_give/rate_get руб
        rates = []
        for r in rows:
            try:
                give = float(r.get("rate_give", 0))
                get_val = float(r.get("rate_get", 0))
                if get_val > 0:
                    rub_per_usdt = give / get_val
                    if 70 <= rub_per_usdt <= 130:
                        rates.append(rub_per_usdt)
            except (ValueError, TypeError):
                continue

        if not rates:
            return None
        result = min(rates)
        logger.info("Парсер API: курс %s ₽ (из %s предложений)", round(result, 2), len(rates))
        return round(result, 2)
    except ImportError:
        logger.debug("Парсер API: bestchange-api не установлен")
        return None
    except Exception as e:
        logger.warning("Парсер API: ошибка — %s: %s", type(e).__name__, e)
        return None


async def _get_rate_via_html() -> float | None:
    """HTML-парсинг (fallback). Использует прокси из .env."""
    connector = _get_connector()
    timeout = aiohttp.ClientTimeout(total=10)
    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(BESTCHANGE_URL) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text(encoding="windows-1251")
    except Exception as e:
        logger.warning("Парсер HTML: ошибка запроса — %s", e)
        return None

    matches = list(RATE_PATTERN.finditer(html))
    if not matches:
        matches = list(RATE_PATTERN_FALLBACK.finditer(html))

    rates = []
    for m in matches:
        try:
            v = float(m.group(1).replace(",", "."))
            if 70 <= v <= 130:
                rates.append(v)
        except ValueError:
            continue

    if not rates:
        return None
    logger.info("Парсер HTML: курс %s ₽ (fallback)", round(min(rates), 2))
    return round(min(rates), 2)


async def get_usdt_to_rub_rate() -> float | None:
    """
    Получить лучший курс 1 USDT = X RUB.
    1. HTML (aiohttp + proxy, стабильно с SOCKS5)
    2. API (fallback, может дать 502 через прокси)
    """
    logger.info("Парсер: запрос курса (HTML → API)")

    rate = await _get_rate_via_html()
    if rate is not None:
        return rate

    loop = asyncio.get_event_loop()
    rate = await loop.run_in_executor(None, _get_rate_via_api)
    if rate is not None:
        return rate

    logger.warning("Парсер: курс не найден (ни HTML, ни API)")
    return None
