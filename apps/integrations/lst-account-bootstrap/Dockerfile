FROM python:3.12-slim

WORKDIR /app

COPY apps/integrations/lst-account-bootstrap/pyproject.toml .
RUN pip install --no-cache-dir .

COPY apps/integrations/lst-account-bootstrap/ .

CMD ["python", "main.py"]
