"""
Парсер курса USDT → RUB.
BestChange (Альфа-Банк): Playwright → bestchange-api.
Fallback: Binance API, ручной курс из .env.
"""
import asyncio
import logging
import re
from urllib.parse import urlparse

import aiohttp

logger = logging.getLogger(__name__)

# bestchange-api: from=52 (alfaclick/Альфа-Банк), to=10 (USDT TRC20)
DIR_FROM_ALFACLICK = 52
DIR_TO_USDT_TRC20 = 10

BESTCHANGE_URL = "https://www.bestchange.ru/alfaclick-to-tether-trc20.html"
RATE_PATTERN = re.compile(r"(\d{2,3}[.,]\d{2,4})\s*RUB[\s\S]{0,80}?(?:Альфа|alfabank|Банк)", re.I | re.DOTALL)
RATE_PATTERN_FALLBACK = re.compile(r"(\d{2,3}[.,]\d{2,4})\s*RUB", re.I)


def _parse_proxy_for_playwright(proxy_url: str) -> dict | None:
    """Извлечь server, username, password для Playwright (без credentials в URL)."""
    if not proxy_url or not proxy_url.strip():
        return None
    try:
        parsed = urlparse(proxy_url)
        if not parsed.hostname or not parsed.port:
            return None
        server = f"{parsed.scheme or 'http'}://{parsed.hostname}:{parsed.port}"
        out = {"server": server}
        if parsed.username:
            out["username"] = parsed.username
        if parsed.password:
            out["password"] = parsed.password
        return out
    except Exception:
        return None


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
            # requests/urllib ожидает {"http": "...", "https": "..."}
            kwargs["proxy"] = {"http": PROXY, "https": PROXY}
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


async def _get_rate_via_playwright() -> float | None:
    """
    Playwright (headless Chromium): реальный браузер, корректная кодировка и рендер.
    Работает через прокси, даже когда aiohttp/API дают 502 или крякозябры.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.debug("Парсер Playwright: playwright не установлен")
        return None

    try:
        from config import PROXY
    except ImportError:
        PROXY = None

    proxy_config = _parse_proxy_for_playwright(PROXY) if PROXY else None

    try:
        async with async_playwright() as p:
            launch_options = {
                "headless": True,
                "args": ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            }
            if proxy_config:
                launch_options["proxy"] = proxy_config

            browser = await p.chromium.launch(**launch_options)
            try:
                context = await browser.new_context(
                    locale="ru-RU",
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                )
                page = await context.new_page()
                await page.goto(BESTCHANGE_URL, wait_until="domcontentloaded", timeout=20000)
                # Курсы подгружаются через JS — ждём появления шаблона в DOM
                await page.wait_for_function(
                    "() => document.body.innerText.match(/\\d{2,3}[.,]\\d{2,4}\\s*RUB/)",
                    timeout=25000,
                )
                html = await page.content()
            finally:
                await browser.close()

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
        result = min(rates)
        logger.info("Парсер Playwright: курс %s ₽", round(result, 2))
        return round(result, 2)
    except Exception as e:
        logger.warning("Парсер Playwright: %s — %s", type(e).__name__, e)
        return None


async def _get_rate_via_binance() -> float | None:
    """Binance public API — без auth. Прокси — если задан."""
    url = "https://api.binance.com/api/v3/ticker/price?symbol=USDTRUB"
    connector = _get_connector()
    timeout = aiohttp.ClientTimeout(total=10)
    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
        price = float(data.get("price", 0))
        if 70 <= price <= 130:
            logger.info("Парсер Binance: курс %s ₽", round(price, 2))
            return round(price, 2)
    except Exception as e:
        logger.debug("Парсер Binance: %s", e)
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
    Получить курс 1 USDT = X RUB.
    Порядок: Playwright → Binance → bestchange-api → ручной из .env.
    """
    logger.info("Парсер: запрос курса (Playwright → Binance → API)")

    rate = await _get_rate_via_playwright()
    if rate is not None:
        return rate

    rate = await _get_rate_via_binance()
    if rate is not None:
        return rate

    loop = asyncio.get_event_loop()
    rate = await loop.run_in_executor(None, _get_rate_via_api)
    if rate is not None:
        return rate

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
