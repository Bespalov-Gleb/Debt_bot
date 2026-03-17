# План деплоя на Linux-сервер

## Требования
- Ubuntu/Debian (или другой дистрибутив)
- Python 3.10+
- Доступ по SSH

---

## 1. Подготовка сервера

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Python и зависимости
sudo apt install -y python3 python3-pip python3-venv git
```

---

## 2. Создание директории и клонирование (или копирование)

**Вариант A — через Git (если проект в репозитории):**
```bash
sudo mkdir -p /opt/debt_bot
sudo chown $USER:$USER /opt/debt_bot
cd /opt/debt_bot
git clone <URL_РЕПОЗИТОРИЯ> .
```

**Вариант B — копирование файлов вручную (scp/sftp):**
```bash
sudo mkdir -p /opt/debt_bot
sudo chown $USER:$USER /opt/debt_bot
cd /opt/debt_bot
# Затем скопируйте с локальной машины:
# scp -r debt_bot/* user@SERVER:/opt/debt_bot/
```

---

## 3. Виртуальное окружение и зависимости

```bash
cd /opt/debt_bot

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

---

## 4. Настройка .env

```bash
cp .env.example .env
nano .env
```

Заполните:
```
DEBT_BOT_TOKEN=ваш_токен_от_BotFather
DEBT_BOT_ALLOWED_IDS=123456789,987654321
# При необходимости:
# DEBT_BOT_PROXY=socks5://127.0.0.1:1080
```

---

## 5. Тестовый запуск

```bash
cd /opt/debt_bot
source venv/bin/activate
python bot.py
```

Проверьте работу бота в Telegram. Остановка: `Ctrl+C`.

---

## 6. Systemd-сервис (автозапуск)

Создайте файл сервиса:

```bash
sudo nano /etc/systemd/system/debt-bot.service
```

Содержимое:

```ini
[Unit]
Description=Debt Bot (USDT/RUB)
After=network.target

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=/opt/debt_bot
Environment="PATH=/opt/debt_bot/venv/bin"
ExecStart=/opt/debt_bot/venv/bin/python /opt/debt_bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Замените `User` и `Group` на вашего пользователя (например, `$USER`).

Активация:

```bash
sudo systemctl daemon-reload
sudo systemctl enable debt-bot
sudo systemctl start debt-bot
sudo systemctl status debt-bot
```

---

## 7. Полезные команды

| Команда | Описание |
|---------|----------|
| `sudo systemctl start debt-bot` | Запуск |
| `sudo systemctl stop debt-bot` | Остановка |
| `sudo systemctl restart debt-bot` | Перезапуск |
| `sudo systemctl status debt-bot` | Статус |
| `journalctl -u debt-bot -f` | Логи в реальном времени |

---

## 8. Бэкап БД (опционально)

```bash
# Ручной бэкап
cp /opt/debt_bot/debt.db /opt/debt_bot/backups/debt_$(date +%Y%m%d).db

# Cron: ежедневно в 3:00
echo "0 3 * * * cp /opt/debt_bot/debt.db /opt/debt_bot/backups/debt_\$(date +\%Y\%m\%d).db" | crontab -
```

---

## 9. Обновление бота

```bash
cd /opt/debt_bot

# Через Git:
git pull

# Или заменить файлы вручную

source venv/bin/activate
pip install -r requirements.txt

sudo systemctl restart debt-bot
```
