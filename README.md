# Бот учёта долгов (USDT → RUB)

Telegram-бот для фиксации долгов в USDT с конвертацией в рубли по курсу BestChange (Альфа-Банк RUB ↔ TRC-20).

## Возможности

- **Общая сумма долга** (в рублях) — в начале списка
- **Добавление записей**: ввод суммы в USDT → авто-конвертация по курсу BestChange
- **Список долгов**: отметка записей как оплаченных
- **История**: оплаченные записи с возможностью удаления
- **Белый список**: только указанные Telegram ID имеют доступ

## Установка

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

На Linux-сервере может потребоваться установка системных зависимостей:
```bash
python -m playwright install-deps chromium
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

Курс берётся с [BestChange](https://www.bestchange.ru/alfaclick-to-tether-trc20.html): Альфа-Банк RUB → USDT TRC-20 (покупка USDT за рубли).  
Используется Playwright (headless Chromium) — надёжный парсинг через прокси. Резерв: HTML (aiohttp) и bestchange-api.  
Если авто-получение курса не сработает, можно ввести сумму в рублях вручную.
