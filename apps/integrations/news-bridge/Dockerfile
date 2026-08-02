FROM python:3.12-slim

WORKDIR /app

COPY apps/integrations/news-bridge/pyproject.toml .
RUN pip install --no-cache-dir .

COPY apps/integrations/news-bridge/ .

CMD ["python", "main.py"]
