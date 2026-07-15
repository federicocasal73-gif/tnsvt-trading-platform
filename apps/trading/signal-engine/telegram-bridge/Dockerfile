# TNSVT V2 - Telegram Bridge
FROM python:3.12-alpine

WORKDIR /app

RUN apk add --no-cache ca-certificates

COPY telegram-bridge/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY telegram-bridge/ /app/

RUN adduser -D -u 1000 tnsvt
USER tnsvt

# Healthcheck no aplica (cliente Telegram, no HTTP)
# Pero podemos exponer un puerto para readiness si lo agregamos luego

CMD ["python", "bridge.py"]