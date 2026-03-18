FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .

# БД по умолчанию в /app/data (volume)
ENV DEBT_BOT_DB_PATH=/app/data/debt.db

CMD ["python", "-u", "bot.py"]
