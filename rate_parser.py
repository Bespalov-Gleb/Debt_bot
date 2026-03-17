"""
Парсер курса Альфа-Банк RUB → USDT TRC-20 с BestChange.
Направление: отдаём рубли, получаем USDT (покупка — 1 USDT = X RUB).
Лучший курс = МИНИМУМ рублей за 1 USDT.
"""
import re
import aiohttp

# alfaclick = Альфа-Банк (206 обменников). alfabank-cash-in пуст.
BESTCHANGE_URL = "https://www.bestchange.ru/alfaclick-to-tether-trc20.html"

# Колонка "Отдаёте": "83.1189 RUB Альфа-Банк" — руб за 1 USDT TRC20
RATE_PATTERN = re.compile(r"(\d{2,3}[.,]\d{2,4})\s*RUB\s*(?:Альфа|alfabank|руб)", re.I)


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
    connector = _get_connector()
    timeout = aiohttp.ClientTimeout(total=10)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        async with session.get(BESTCHANGE_URL) as resp:
            if resp.status != 200:
                return None
            html = await resp.text()

    # Только курс из таблицы: формат 81.99 или 137.50 (руб за 1 USDT)
    rates = []
    for m in RATE_PATTERN.finditer(html):
        try:
            v = float(m.group(1).replace(",", "."))
            if 70 <= v <= 130:  # Реалистичный курс USDT (отсекаем резервы в тыс.)
                rates.append(v)
        except ValueError:
            continue

    if not rates:
        return None
    # Лучший = МИНИМУМ рублей за 1 USDT
    return round(min(rates), 2)
