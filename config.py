"""
Конфигурация бота.
Значения загружаются из .env (скопируйте .env.example в .env и заполните).
"""
from dotenv import load_dotenv
import os

load_dotenv()

# Токен бота от @BotFather
BOT_TOKEN = os.getenv("DEBT_BOT_TOKEN", "")

# Прокси для запросов (если api.telegram.org недоступен): socks5://host:port или socks5://user:pass@host:port
PROXY = os.getenv("DEBT_BOT_PROXY") or None

# Белый список: только эти Telegram ID могут пользоваться ботом
# DEBT_BOT_ALLOWED_IDS — строка через запятую, например: 123456789,987654321
_allowed = os.getenv("DEBT_BOT_ALLOWED_IDS", "")
ALLOWED_USER_IDS: list[int] = [
    int(x.strip()) for x in _allowed.split(",") if x.strip().isdigit()
]

# URL BestChange: USDT TRC-20 → Альфа-Банк RUB (продажа USDT за рубли)
BESTCHANGE_URL = "https://www.bestchange.ru/tether-trc20-to-alfabank-cash-in.html"

# Ручной курс (если парсинг не сработал): число, например 83.5
MANUAL_RATE = os.getenv("DEBT_BOT_RATE")
