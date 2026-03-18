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
_allowed = os.getenv("DEBT_BOT_ALLOWED_IDS", "")
ALLOWED_USER_IDS: list[int] = [
    int(x.strip()) for x in _allowed.split(",") if x.strip().isdigit()
]

# Чаты для маршрутизации
# Важно: обычно это приватные чаты (тогда chat.id = user.id).
DEBT_BOT_MY_CHAT_ID = int(os.getenv("DEBT_BOT_MY_CHAT_ID") or 0)
DEBT_BOT_PARTNER_CHAT_ID = int(os.getenv("DEBT_BOT_PARTNER_CHAT_ID") or 0)

# CoinMarketCap API key (https://pro.coinmarketcap.com/) — для курса USDT/RUB
CMC_API_KEY = os.getenv("DEBT_BOT_CMC_API_KEY") or None

# Ручной курс (fallback): число, например 83.5
MANUAL_RATE = os.getenv("DEBT_BOT_RATE")
