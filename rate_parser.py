"""
Парсер курса Альфа-Банк RUB → USDT TRC-20 с BestChange.
Направление: отдаём рубли, получаем USDT (покупка — 1 USDT = X RUB).
Лучший курс = МИНИМУМ рублей за 1 USDT.
"""
import logging
import re
import aiohttp

logger = logging.getLogger(__name__)

# alfaclick = Альфа-Банк (206 обменников). alfabank-cash-in пуст.
BESTCHANGE_URL = "https://www.bestchange.ru/alfaclick-to-tether-trc20.html"

# Колонка "Отдаёте": "83.1181 RUB Альфа-Банк" — руб за 1 USDT TRC20
# Между RUB и Альфа может быть пробел или HTML-теги
RATE_PATTERN = re.compile(
    r"(\d{2,3}[.,]\d{2,4})\s*RUB[\s\S]{0,80}?(?:Альфа|alfabank|Банк)",
    re.I | re.DOTALL,
)
# Fallback: только число + RUB (если основной не сработал из‑за разметки)
RATE_PATTERN_FALLBACK = re.compile(r"(\d{2,3}[.,]\d{2,4})\s*RUB", re.I)


def _get_connector():
    """HTTP-коннектор с прокси, если задан в env."""
    from config import PROXY
    if PROXY:
        from aiohttp_socks import ProxyConnector
        return ProxyConnector.from_url(PROXY)
    return aiohttp.TCPConnector()


async def get_usdt_to_rub_rate() -> float | None:
    """
    Получить лучший курс 1 USDT = X RUB.
    Направление: покупка USDT за рубли. Лучший = МИНИМУМ руб. за 1 USDT.
    """
    logger.info("Парсер: запрос курса с %s", BESTCHANGE_URL)
    connector = _get_connector()
    timeout = aiohttp.ClientTimeout(total=10)

    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(BESTCHANGE_URL) as resp:
                if resp.status != 200:
                    logger.warning("Парсер: HTTP %s вместо 200", resp.status)
                    return None
                # BestChange отдаёт страницу в windows-1251, иначе кириллица ломается
                html = await resp.text(encoding="windows-1251")
    except aiohttp.ClientError as e:
        logger.warning("Парсер: ошибка запроса — %s: %s", type(e).__name__, e)
        return None
    except Exception as e:
        logger.exception("Парсер: неожиданная ошибка — %s", e)
        return None

    matches = list(RATE_PATTERN.finditer(html))
    if not matches:
        matches = list(RATE_PATTERN_FALLBACK.finditer(html))
        if matches:
            logger.info("Парсер: основной паттерн 0 совпадений, использован fallback")

    logger.debug("Парсер: найдено совпадений: %s", len(matches))

    rates = []
    for m in matches:
        try:
            v = float(m.group(1).replace(",", "."))
            if 70 <= v <= 130:
                rates.append(v)
            else:
                logger.debug("Парсер: отброшено (вне 70–130): %s", v)
        except ValueError:
            continue

    if not rates:
        snippet = html[:2000] if len(html) > 2000 else html
        logger.warning(
            "Парсер: курс не найден. Совпадений: %s. Фрагмент ответа (первые 500 симв.): %s",
            len(matches),
            snippet[:500].replace("\n", " "),
        )
        return None

    result = round(min(rates), 2)
    logger.info("Парсер: курс %s ₽ (найдено %s значений)", result, len(rates))
    return result
