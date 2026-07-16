FROM python:3.12-alpine

WORKDIR /app

RUN apk add --no-cache ca-certificates gcc musl-dev linux-headers

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/

RUN adduser -D -u 1000 tnsvt && chown -R tnsvt:tnsvt /app
USER tnsvt

EXPOSE 8200

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8200/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8200", "--workers", "2", "--log-level", "info"]