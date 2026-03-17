# Бот учёта долгов (USDT → RUB)

Telegram-бот для фиксации долгов в USDT с конвертацией в рубли по курсу CoinMarketCap.

## Возможности

- **Общая сумма долга** (в рублях) — в начале списка
- **Добавление записей**: ввод суммы в USDT → авто-конвертация по курсу CoinMarketCap
- **Список долгов**: отметка записей как оплаченных
- **История**: оплаченные записи с возможностью удаления
- **Белый список**: только указанные Telegram ID имеют доступ

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
   При блокировке api.telegram.org добавьте в `.env`:
   ```
   DEBT_BOT_PROXY=socks5://127.0.0.1:1080
   ```

## Запуск

```bash
python bot.py
```

## Курс

Курс берётся с [CoinMarketCap](https://coinmarketcap.com/currencies/tether/usdt/rub/).  
Нужен API-ключ (бесплатно): [pro.coinmarketcap.com](https://pro.coinmarketcap.com/) → добавить в .env: `DEBT_BOT_CMC_API_KEY=ваш_ключ`.  
Fallback: Binance API, ручной курс `DEBT_BOT_RATE=83.5`
