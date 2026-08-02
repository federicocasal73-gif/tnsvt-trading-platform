# TNSVT V2 - news-analyzer
FROM python:3.12-slim

WORKDIR /app

COPY apps/ai/news-analyzer/requirements.txt . 2>/dev/null || true
COPY apps/ai/news-analyzer/pyproject.toml . 2>/dev/null || true

RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; \
    elif [ -f pyproject.toml ]; then pip install --no-cache-dir .; \
    else pip install --no-cache-dir fastapi uvicorn[standard] aiohttp beautifulsoup4 nats-py; \
    fi

COPY apps/ai/news-analyzer/app/ app/

EXPOSE 8051

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8051"]
