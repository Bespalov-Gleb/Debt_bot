# Бот учёта долгов (credit/debit)

Telegram-бот для учёта долгов в RUB с:
- `credit`: увеличение долга (в RUB или USDT -> RUB, округление вверх)
- `debit`: уменьшение долга после подтверждения фото чека

## Команды

- `/credit <сумма> <валюта>` (валюта: `USDT` или `RUB`) — создает запрос на ввод “номера перевода” (просто текст). Доступно и тебе, и товарищу
- `/debit <номер_карты_телефона> <банк> <сумма_в_рублях>` — команда из чата товарища, бот отправляет запрос в твой чат и ждет фото чека
- Кнопка “📊 Excel” — выгружает таблицу по текущим и подтвержденным записям в RUB

## Установка

```bash
pip install -r requirements.txt
```

## Настройка

1. Создайте бота в [@BotFather](https://t.me/BotFather), получите токен.
2. Узнайте свой Telegram ID: напишите [@userinfobot](https://t.me/userinfobot).
3. Скопируйте `.env.example` в `.env` и заполните:
   ```
   DEBT_BOT_TOKEN=ваш_токен_от_BotFather
   DEBT_BOT_ALLOWED_IDS=ваш_id,id_партнёра
   ```
4. Добавьте чаты:
   ```
   DEBT_BOT_MY_CHAT_ID=ваш_приватный_chat_id
   DEBT_BOT_PARTNER_CHAT_ID=chat_id_товарища
   ```
   При блокировке api.telegram.org добавьте в `.env`:
   ```
   DEBT_BOT_PROXY=socks5://127.0.0.1:1080
   ```

## Запуск

**Локально:**
```bash
python bot.py
```

**Docker (прод, с авто-рестартом при падении):**
```bash
docker compose up -d --build
```
Логи: `docker compose logs -f`  
Миграция: положите `debt.db` в `./data/` до первого запуска.

## Курс

Курс берётся с [CoinMarketCap](https://coinmarketcap.com/currencies/tether/usdt/rub/).  
Нужен API-ключ (бесплатно): [pro.coinmarketcap.com](https://pro.coinmarketcap.com/) → добавить в .env: `DEBT_BOT_CMC_API_KEY=ваш_ключ`.  
Fallback: Binance API, ручной курс `DEBT_BOT_RATE=83.5`
