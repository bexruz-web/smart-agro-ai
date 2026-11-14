# Telegram bot — faqat UI; biznes logika backend'ning ichki API'sida.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN useradd --create-home --uid 10001 app
COPY bot/requirements.txt ./
RUN pip install -r requirements.txt
COPY bot/bot /app/bot
USER app
EXPOSE 8081
CMD ["python", "-m", "bot.main"]
