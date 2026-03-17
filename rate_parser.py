"""
Парсер курса USDT → RUB.
Источник: CoinMarketCap API. Fallback: Binance, ручной DEBT_BOT_RATE.
"""
import logging

import aiohttp

logger = logging.getLogger(__name__)

CMC_URL = "https://pro-api.coinmarketcap.com/v1/tools/price-conversion"
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


def _valid_rate(price: float) -> bool:
    return 70 <= price <= 130


async def _get_rate_via_coinmarketcap() -> float | None:
    """CoinMarketCap API — курс как на https://coinmarketcap.com/currencies/tether/usdt/rub/"""
    try:
        from config import CMC_API_KEY
    except ImportError:
        return None
    if not CMC_API_KEY or not CMC_API_KEY.strip():
        return None

    connector = _get_connector()
    timeout = aiohttp.ClientTimeout(total=10)
    params = {"amount": "1", "symbol": "USDT", "convert": "RUB"}
    headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY.strip(), "Accept": "application/json"}

    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(CMC_URL, params=params, headers=headers) as resp:
                if resp.status != 200:
                    logger.warning("Парсер CMC: HTTP %s", resp.status)
                    return None
                data = await resp.json()
        quote = data.get("data", {}).get("quote", {}).get("RUB", {})
        price = float(quote.get("price", 0))
        if _valid_rate(price):
            logger.info("Парсер CoinMarketCap: курс %s ₽", round(price, 2))
            return round(price, 2)
    except Exception as e:
        logger.warning("Парсер CoinMarketCap: %s", e)
    return None


async def _get_rate_via_binance() -> float | None:
    """Binance API — fallback без API-ключа."""
    connector = _get_connector()
    timeout = aiohttp.ClientTimeout(total=10)
    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(BINANCE_URL) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
        price = float(data.get("price", 0))
        if _valid_rate(price):
            logger.info("Парсер Binance: курс %s ₽", round(price, 2))
            return round(price, 2)
    except Exception as e:
        logger.debug("Парсер Binance: %s", e)
    return None


async def get_usdt_to_rub_rate() -> float | None:
    """
    Получить курс 1 USDT = X RUB.
    CoinMarketCap → Binance → ручной DEBT_BOT_RATE.
    """
    logger.info("Парсер: запрос курса (CoinMarketCap → Binance)")

    rate = await _get_rate_via_coinmarketcap()
    if rate is not None:
        return rate

    rate = await _get_rate_via_binance()
    if rate is not None:
        return rate

    try:
        from config import MANUAL_RATE
        if MANUAL_RATE:
            r = float(MANUAL_RATE.replace(",", ".").strip())
            if _valid_rate(r):
                logger.info("Парсер: ручной курс %s ₽ (DEBT_BOT_RATE)", round(r, 2))
                return round(r, 2)
    except (ImportError, ValueError):
        pass

    logger.warning("Парсер: курс не найден. Добавьте DEBT_BOT_CMC_API_KEY и/или DEBT_BOT_RATE в .env")
    return None
