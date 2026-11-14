# Backend (API + Celery worker/beat) — bitta image, docker-compose'da turli buyruqlar bilan ishga tushadi.
# Build konteksti — repo ildizi (knowledge/ ham kerak).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    KNOWLEDGE_DIR=/app/knowledge

WORKDIR /app
RUN useradd --create-home --uid 10001 app

COPY backend/requirements.txt backend/requirements-dev.txt ./
ARG INSTALL_DEV=false
RUN pip install --upgrade pip && \
    if [ "$INSTALL_DEV" = "true" ]; then pip install -r requirements-dev.txt; else pip install -r requirements.txt; fi

COPY backend/ /app/
COPY knowledge/ /app/knowledge/

USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
