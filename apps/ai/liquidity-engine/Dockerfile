FROM python:3.12-slim

WORKDIR /app

COPY apps/ai/liquidity-engine/pyproject.toml .
RUN pip install --no-cache-dir .

COPY apps/ai/liquidity-engine/app/ app/

EXPOSE 8050

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8050"]
