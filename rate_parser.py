"""
Парсер курса USDT → RUB.
Источник: Binance API. Fallback: ручной курс из DEBT_BOT_RATE (.env).
"""
import logging

import aiohttp

logger = logging.getLogger(__name__)

BINANCE_URL = "https://api.binance.com/api/v3/ticker/price?symbol=USDTRUB"


def _get_connector():
    """HTTP-коннектор с прокси (если задан в .env)."""
    try:
        from config import PROXY
    except ImportError:
        return aiohttp.TCPConnector()
    if PROXY:
        from aiohttp_socks import ProxyConnector
        return ProxyConnector.from_url(PROXY)
    return aiohttp.TCPConnector()


async def get_usdt_to_rub_rate() -> float | None:
    """
    Получить курс 1 USDT = X RUB.
    Binance API → ручной из .env (DEBT_BOT_RATE).
    """
    logger.info("Парсер: запрос курса Binance")

    connector = _get_connector()
    timeout = aiohttp.ClientTimeout(total=10)
    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(BINANCE_URL) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
        price = float(data.get("price", 0))
        if 70 <= price <= 130:
            logger.info("Парсер Binance: курс %s ₽", round(price, 2))
            return round(price, 2)
    except Exception as e:
        logger.warning("Парсер Binance: %s", e)

    try:
        from config import MANUAL_RATE
        if MANUAL_RATE:
            r = float(MANUAL_RATE.replace(",", ".").strip())
            if 70 <= r <= 130:
                logger.info("Парсер: ручной курс %s ₽ (DEBT_BOT_RATE)", round(r, 2))
                return round(r, 2)
    except (ImportError, ValueError):
        pass

    logger.warning("Парсер: курс не найден. Добавьте DEBT_BOT_RATE=83.5 в .env")
    return None
