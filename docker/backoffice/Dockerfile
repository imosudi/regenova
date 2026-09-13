# REGENOVA Backoffice Management Microservice — Dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt gunicorn

COPY reamp/ ./reamp/
COPY backend_server.py backend_wsgi.py api_server.py web_server.py ./
COPY backend/ ./backend/

EXPOSE 8002

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://127.0.0.1:8002/ || exit 1

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8002", "backend_wsgi:application"]
