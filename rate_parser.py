"""
Парсер курса USDT TRC-20 → Альфа-Банк RUB с BestChange.
Направление: продаём USDT, получаем рубли (1 USDT = X RUB).
"""
import asyncio
import re
import aiohttp
from bs4 import BeautifulSoup


def _get_connector():
    """HTTP-коннектор с прокси, если задан в env."""
    from config import PROXY
    if PROXY:
        from aiohttp_socks import ProxyConnector
        return ProxyConnector.from_url(PROXY)
    return aiohttp.TCPConnector()


# URL: USDT TRC-20 → Альфа cash-in RUB
BESTCHANGE_URL = "https://www.bestchange.ru/tether-trc20-to-alfabank-cash-in.html"


def _get_rate_sync() -> float | None:
    """Синхронный вызов bestchange-api (в executor)."""
    try:
        from bestchange_api import BestChange

        api = BestChange()
        if api.is_error():
            return None
        # dir_from=10 (USDT TRC20), dir_to=62 (Alfa cash-in RUB)
        rows = api.rates().filter(10, 62)
        if not rows:
            return None
        best = rows[0]
        rate_give = float(best.get("rate_give", 1))
        rate_get = float(best.get("rate_get", 0))
        if rate_give <= 0:
            return None
        return rate_get / rate_give
    except Exception:
        return None


async def get_rate_via_api() -> float | None:
    """Получить лучший курс через bestchange-api (1 USDT = X RUB)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_rate_sync)


async def get_rate_via_html() -> float | None:
    """Парсинг курса из HTML BestChange. Ищем курс в таблице."""
    connector = _get_connector()
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.get(BESTCHANGE_URL) as resp:
            if resp.status != 200:
                return None
            html = await resp.text()

    soup = BeautifulSoup(html, "html.parser")
    # Таблица: обменник | отдаёте (1 USDT) | получаете (X RUB) | резерв
    # Ищем строки с курсом — обычно "XX.XX" или "XXX" RUB в диапазоне 70-120
    rates = []
    for td in soup.find_all(["td", "span"]):
        text = td.get_text(strip=True)
        # Паттерн: число с точкой/запятой (курс)
        for part in re.split(r"[\s/]+", text):
            m = re.match(r"^(\d{2,3}[,.]?\d*)$", part)
            if m:
                try:
                    v = float(m.group(1).replace(",", "."))
                    if 70 < v < 150:
                        rates.append(v)
                except ValueError:
                    continue
    return round(max(rates), 2) if rates else None


async def get_usdt_to_rub_rate() -> float | None:
    """Получить курс 1 USDT = X RUB. API → HTML парсинг."""
    rate = await get_rate_via_api()
    if rate is not None and 70 < rate < 150:
        return round(rate, 2)
    rate = await get_rate_via_html()
    return rate
